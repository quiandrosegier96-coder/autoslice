"""
AutoSlice — Auth routes: /register and /login.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.auth.service import register_user, login_user, create_access_token
from app.auth.dependencies import get_current_user
from app.database import ADMIN_EMAILS, get_connection

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
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
    try:
        user = login_user(req.email, req.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    token = create_access_token(user["id"], user["email"])
    return AuthResponse(access_token=token, username=user["username"], email=user["email"],
                        is_admin=user["email"] in ADMIN_EMAILS)


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
