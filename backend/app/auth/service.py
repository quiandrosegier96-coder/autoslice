"""
AutoSlice — Auth service: register, login, JWT tokens.
Uses stdlib hashlib (PBKDF2-SHA256) to avoid passlib/bcrypt Python 3.14 incompatibility.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError

from app.config import settings, get_jwt_secret
from app.database import get_connection

_ITERATIONS = 260_000
_HASH = "sha256"


def hash_password(password: str) -> str:
    """PBKDF2-SHA256 with a random 32-byte salt. Returns 'salt$hash' hex string."""
    salt = secrets.token_hex(32)
    dk = hashlib.pbkdf2_hmac(_HASH, password.encode(), salt.encode(), _ITERATIONS)
    return f"{salt}${dk.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    """Verify a plain password against the stored 'salt$hash' string."""
    try:
        salt, stored_hash = stored.split("$", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac(_HASH, plain.encode(), salt.encode(), _ITERATIONS)
    return secrets.compare_digest(dk.hex(), stored_hash)


def create_access_token(user_id: int, email: str, remember: bool = False) -> str:
    from app.database import ADMIN_EMAILS, get_connection
    # is_admin = hardcoded email list OR DB column (supports runtime grants)
    db_admin = False
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT COALESCE(is_admin,0) AS is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
            if row:
                db_admin = bool(row["is_admin"])
    except Exception:
        pass
    hours = settings.jwt_expire_hours_remembered if remember else settings.jwt_expire_hours
    expire = datetime.now(timezone.utc) + timedelta(hours=hours)
    payload = {
        "sub": str(user_id),
        "email": email,
        "is_admin": email in ADMIN_EMAILS or db_admin,
        "exp": expire,
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, get_jwt_secret(), algorithms=[settings.jwt_algorithm])
    except JWTError:
        return {}


def register_user(username: str, email: str, password: str) -> dict:
    username = username.strip()
    email = email.strip().lower()
    if not username:
        raise ValueError("Username is required.")
    password_hash = hash_password(password)
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, email, password_hash, created_at) VALUES (?,?,?,?)",
                (username, email, password_hash, created_at),
            )
            conn.commit()
            return {"id": cursor.lastrowid, "username": username, "email": email}
        except Exception as exc:
            if "UNIQUE" in str(exc):
                raise ValueError("Username or email already registered.")
            raise


def create_reset_token(email: str) -> str | None:
    """
    Create a 1h reset token for the given email.
    Stores a SHA-256 hash of the token — never the raw token.
    Returns the raw token (to be emailed) or None if email is unknown.
    """
    from datetime import datetime, timezone
    email = email.strip().lower()
    with get_connection() as conn:
        user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            return None
        raw_token  = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO reset_tokens (email, token, created_at) VALUES (?,?,?)",
            (email, token_hash, created_at),
        )
        conn.commit()
    return raw_token


def reset_password(token: str, new_password: str) -> None:
    """Apply password reset. Raises ValueError on invalid/expired/used token."""
    from datetime import datetime, timedelta, timezone
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT email, created_at, used FROM reset_tokens WHERE token = ?", (token_hash,)
        ).fetchone()
        if not row:
            raise ValueError("Invalid or expired reset link.")
        if row["used"]:
            raise ValueError("This reset link has already been used.")
        created = datetime.fromisoformat(row["created_at"])
        if datetime.now(timezone.utc) - created > timedelta(hours=1):
            raise ValueError("Reset link has expired (valid for 1 hour).")
        new_hash = hash_password(new_password)
        conn.execute("UPDATE users SET password_hash = ? WHERE email = ?", (new_hash, row["email"]))
        conn.execute("UPDATE reset_tokens SET used = 1 WHERE token = ?", (token_hash,))
        conn.commit()


def login_user(identifier: str, password: str) -> dict:
    """Accept either an email address or a username as the login identifier."""
    identifier = identifier.strip()
    email_identifier = identifier.lower()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, email, password_hash FROM users "
            "WHERE lower(email) = ? OR username = ?",
            (email_identifier, identifier),
        ).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        raise ValueError("Invalid email/username or password.")
    return {"id": row["id"], "username": row["username"], "email": row["email"]}
