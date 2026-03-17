"""
AutoSlice — Auth routes: /register and /login.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.auth.service import register_user, login_user, create_access_token, create_reset_token, reset_password
from app.auth.dependencies import get_current_user
from app.database import ADMIN_EMAILS, get_connection

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
    # Always return the same message for security (don't reveal if email exists)
    create_reset_token(req.email)
    return {"message": "If this email is registered, a reset code has been generated. Contact your admin to retrieve it."}


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
