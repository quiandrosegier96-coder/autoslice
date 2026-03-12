"""
AutoSlice — Auth service: register, login, JWT tokens.
Uses stdlib hashlib (PBKDF2-SHA256) to avoid passlib/bcrypt Python 3.14 incompatibility.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError

from app.config import settings
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


def create_access_token(user_id: int, email: str) -> str:
    from app.database import ADMIN_EMAILS
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": str(user_id),
        "email": email,
        "is_admin": email in ADMIN_EMAILS,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return {}


def register_user(username: str, email: str, password: str) -> dict:
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


def login_user(email: str, password: str) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, email, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        raise ValueError("Invalid email or password.")
    return {"id": row["id"], "username": row["username"], "email": row["email"]}
