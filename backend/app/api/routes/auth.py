"""
AutoSlice — Auth routes: /register and /login.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.auth.service import register_user, login_user, create_access_token, create_reset_token, reset_password
from app.auth.dependencies import get_current_user
from app.database import ADMIN_EMAILS, get_connection
from app.config import settings
from app.email_service import send_password_reset_email

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: str   # accepts email address or username
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    email: str
    is_admin: bool = False


@router.post("/auth/register", response_model=AuthResponse)
def register(req: RegisterRequest) -> AuthResponse:
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    try:
        user = register_user(req.username, req.email, req.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    token = create_access_token(user["id"], user["email"])
    return AuthResponse(access_token=token, username=user["username"], email=user["email"],
                        is_admin=user["email"] in ADMIN_EMAILS)


@router.post("/auth/login", response_model=AuthResponse)
def login(req: LoginRequest) -> AuthResponse:
    from datetime import datetime, timezone
    try:
        user = login_user(req.email, req.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    with get_connection() as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?",
                     (datetime.now(timezone.utc).isoformat(), user["id"]))
        conn.commit()
    token = create_access_token(user["id"], user["email"])
    return AuthResponse(access_token=token, username=user["username"], email=user["email"],
                        is_admin=user["email"] in ADMIN_EMAILS)


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
        send_password_reset_email(req.email, reset_link)
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
            "SELECT id, username, email, created_at, last_login FROM users WHERE id = ?",
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
