"""
AutoSlice — Auth routes: /register, /login, /verify, /settings.
"""

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.auth.service import register_user, login_user, create_access_token, create_reset_token, reset_password
from app.auth.dependencies import get_current_user
from app.database import ADMIN_EMAILS, get_connection
from app.config import settings
from app.email_service import send_password_reset_email, send_verification_email

router = APIRouter()

# ── Verification helpers ───────────────────────────────────────────────────

def _generate_verification_code(user_id: int) -> str:
    """Generate a 6-digit code, store its SHA-256 hash, return the raw code."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        # Invalidate any previous unused codes for this user
        conn.execute("UPDATE verification_codes SET used = 1 WHERE user_id = ?", (user_id,))
        conn.execute(
            "INSERT INTO verification_codes (user_id, code_hash, created_at) VALUES (?,?,?)",
            (user_id, code_hash, created_at),
        )
        conn.commit()
    return code


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: str   # accepts email address or username
    password: str
    remember: bool = False


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    email: str
    is_admin: bool = False


class RegisterResponse(BaseModel):
    needs_verification: bool = True
    email: str
    username: str


@router.post("/auth/register", response_model=RegisterResponse)
def register(req: RegisterRequest) -> RegisterResponse:
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    try:
        user = register_user(req.username, req.email, req.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # Send verification code — admins are auto-verified
    if req.email not in ADMIN_EMAILS:
        code = _generate_verification_code(user["id"])
        # Send email in background thread so slow SMTP never blocks the HTTP response
        import threading
        threading.Thread(
            target=send_verification_email,
            args=(req.email, code, req.username),
            daemon=True,
        ).start()
    else:
        with get_connection() as conn:
            conn.execute("UPDATE users SET is_verified = 1 WHERE id = ?", (user["id"],))
            conn.commit()
    return RegisterResponse(needs_verification=req.email not in ADMIN_EMAILS,
                            email=req.email, username=req.username)


@router.post("/auth/login", response_model=AuthResponse)
def login(req: LoginRequest) -> AuthResponse:
    try:
        user = login_user(req.email, req.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    with get_connection() as conn:
        row = conn.execute("SELECT is_verified FROM users WHERE id = ?", (user["id"],)).fetchone()
        if row and not row["is_verified"] and user["email"] not in ADMIN_EMAILS:
            raise HTTPException(status_code=403, detail="EMAIL_NOT_VERIFIED")
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?",
                     (datetime.now(timezone.utc).isoformat(), user["id"]))
        conn.commit()
    token = create_access_token(user["id"], user["email"], remember=req.remember)
    return AuthResponse(access_token=token, username=user["username"], email=user["email"],
                        is_admin=user["email"] in ADMIN_EMAILS)


# ── Email verification ─────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    email: str
    code: str


class ResendVerifyRequest(BaseModel):
    email: str


@router.post("/auth/verify-email")
def verify_email(req: VerifyRequest) -> dict:
    code_hash = hashlib.sha256(req.code.strip().encode()).hexdigest()
    with get_connection() as conn:
        user = conn.execute("SELECT id, username, email FROM users WHERE email = ?", (req.email,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Account not found.")
        row = conn.execute(
            "SELECT id, created_at, used FROM verification_codes "
            "WHERE user_id = ? AND code_hash = ? ORDER BY id DESC LIMIT 1",
            (user["id"], code_hash),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Ongeldige code.")
        if row["used"]:
            raise HTTPException(status_code=400, detail="Deze code is al gebruikt.")
        created = datetime.fromisoformat(row["created_at"])
        if datetime.now(timezone.utc) - created > timedelta(hours=24):
            raise HTTPException(status_code=400, detail="Code verlopen. Vraag een nieuwe aan.")
        conn.execute("UPDATE verification_codes SET used = 1 WHERE id = ?", (row["id"],))
        conn.execute("UPDATE users SET is_verified = 1 WHERE id = ?", (user["id"],))
        conn.commit()
    token = create_access_token(user["id"], user["email"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"],
        "email": user["email"],
        "is_admin": user["email"] in ADMIN_EMAILS,
    }


@router.post("/auth/resend-verification")
def resend_verification(req: ResendVerifyRequest) -> dict:
    with get_connection() as conn:
        user = conn.execute(
            "SELECT id, username, email, is_verified FROM users WHERE email = ?", (req.email,)
        ).fetchone()
        if not user:
            return {"message": "Als dit account bestaat, sturen we een nieuwe code."}
        if user["is_verified"]:
            return {"message": "Account is al geverifieerd."}
        # Rate limit: block if a code was sent in the last 60 seconds
        recent = conn.execute(
            "SELECT created_at FROM verification_codes WHERE user_id = ? AND used = 0 "
            "ORDER BY id DESC LIMIT 1", (user["id"],)
        ).fetchone()
        if recent:
            created = datetime.fromisoformat(recent["created_at"])
            if datetime.now(timezone.utc) - created < timedelta(seconds=60):
                raise HTTPException(status_code=429, detail="Wacht even voor je opnieuw verstuurt.")
    code = _generate_verification_code(user["id"])
    import threading
    threading.Thread(
        target=send_verification_email,
        args=(user["email"], code, user["username"]),
        daemon=True,
    ).start()
    return {"message": "Nieuwe verificatiecode verstuurd."}


# ── User settings ──────────────────────────────────────────────────────────

DEFAULT_SETTINGS: dict = {
    # Appearance
    "theme":              "dark",
    "language":           "nl",
    # Viewer
    "viewer_support_preview": True,
    "viewer_wireframe":       False,
    "viewer_bounding_box":    False,
    "viewer_contact_area":    False,
    "viewer_quality":         "medium",
    "viewer_bed_type":        "smooth",
    # Print defaults
    "default_printer":    "",
    "default_filament":   "pla",
    "default_nozzle":     0.4,
    "default_bed_type":   "smooth",
    "speed_quality":      "balanced",   # "speed" | "balanced" | "quality"
    "expert_mode":        False,
    # Advanced
    "beta_features":      False,
    "debug_overlays":     False,
}


class UpdateSettingsRequest(BaseModel):
    settings: dict


@router.get("/auth/settings")
def get_settings(current_user: dict = Depends(get_current_user)) -> dict:
    user_id = int(current_user["sub"])
    with get_connection() as conn:
        row = conn.execute("SELECT settings_json FROM users WHERE id = ?", (user_id,)).fetchone()
    stored = json.loads(row["settings_json"] or "{}") if row else {}
    return {**DEFAULT_SETTINGS, **stored}


@router.patch("/auth/settings")
def update_settings(req: UpdateSettingsRequest, current_user: dict = Depends(get_current_user)) -> dict:
    user_id = int(current_user["sub"])
    # Merge patch — only update keys that exist in DEFAULT_SETTINGS
    allowed_keys = set(DEFAULT_SETTINGS.keys())
    patch = {k: v for k, v in req.settings.items() if k in allowed_keys}
    with get_connection() as conn:
        row = conn.execute("SELECT settings_json FROM users WHERE id = ?", (user_id,)).fetchone()
        stored = json.loads(row["settings_json"] or "{}") if row else {}
        merged = {**stored, **patch}
        conn.execute("UPDATE users SET settings_json = ? WHERE id = ?",
                     (json.dumps(merged), user_id))
        conn.commit()
    return {**DEFAULT_SETTINGS, **merged}


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/auth/forgot-password")
def forgot_password(req: ForgotPasswordRequest) -> dict:
    # Always return the same message — never reveal whether the email exists
    raw_token = create_reset_token(req.email)
    if raw_token:
        reset_link = f"{settings.app_base_url}/reset-password?token={raw_token}"
        import threading
        threading.Thread(
            target=send_password_reset_email,
            args=(req.email, reset_link),
            daemon=True,
        ).start()
    return {"message": "If this email is registered, a reset link has been sent."}


@router.post("/auth/reset-password")
def do_reset_password(req: ResetPasswordRequest) -> dict:
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    try:
        reset_password(req.token, req.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"message": "Password reset successful. You can now log in."}


class HistoryJob(BaseModel):
    job_id: str
    action: str
    filename: str | None
    printer_id: str | None
    created_at: str


class UpdateProfileRequest(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    current_password: str | None = None
    new_password: str | None = None


@router.get("/auth/me")
def get_me(current_user: dict = Depends(get_current_user)) -> dict:
    user_id = int(current_user["sub"])
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, email, created_at, last_login, is_verified FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


@router.patch("/auth/me")
def update_me(req: UpdateProfileRequest, current_user: dict = Depends(get_current_user)) -> dict:
    from app.auth.service import verify_password, hash_password
    user_id = int(current_user["sub"])
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, email, password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        updates: dict = {}

        if req.new_password:
            if not req.current_password:
                raise HTTPException(status_code=400, detail="Current password is required to set a new password.")
            if not verify_password(req.current_password, row["password_hash"]):
                raise HTTPException(status_code=401, detail="Current password is incorrect.")
            if len(req.new_password) < 8:
                raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")
            updates["password_hash"] = hash_password(req.new_password)

        if req.username and req.username != row["username"]:
            updates["username"] = req.username

        if req.email and req.email != row["email"]:
            updates["email"] = req.email

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [user_id]
            try:
                conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
                conn.commit()
            except Exception as exc:
                if "UNIQUE" in str(exc):
                    raise HTTPException(status_code=409, detail="Username or email already in use.")
                raise

    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row)


@router.get("/auth/history", response_model=list[HistoryJob])
def get_history(current_user: dict = Depends(get_current_user)) -> list[HistoryJob]:
    user_id = int(current_user["sub"])
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT job_id, action, filename, printer_id, created_at FROM jobs "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (user_id,),
        ).fetchall()
    return [HistoryJob(**dict(r)) for r in rows]
