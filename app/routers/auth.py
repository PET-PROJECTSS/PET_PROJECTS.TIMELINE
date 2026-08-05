from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import bearer_token, create_session, delete_session, get_current_user
from app.db import get_db
from app.limiter import login_limiter
from app.models import User
from app.schemas import LoginRequest
from app.security import DUMMY_HASH, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(data: LoginRequest, request: Request, session: Session = Depends(get_db)) -> JSONResponse:
    client_ip = request.client.host if request.client else "unknown"
    if login_limiter.is_blocked(session, client_ip):
        raise HTTPException(status_code=429, detail="Слишком много попыток входа, попробуйте позже")
    username = data.username.strip()
    if not username:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    user = session.query(User).filter_by(username=username).first()
    if user is None:
        verify_password(data.password, DUMMY_HASH)
        login_limiter.failure(session, client_ip)
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    if not verify_password(data.password, user.password_hash):
        login_limiter.failure(session, client_ip)
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    login_limiter.success(session, client_ip)
    token = create_session(session, user.id)
    return JSONResponse({"token": token, "username": user.username, "role": user.role})


@router.post("/logout")
def logout(authorization: str | None = Header(None), session: Session = Depends(get_db)) -> JSONResponse:
    token = bearer_token(authorization)
    delete_session(session, token)
    return JSONResponse({"ok": True})


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> JSONResponse:
    return JSONResponse({"username": user.username, "role": user.role})
