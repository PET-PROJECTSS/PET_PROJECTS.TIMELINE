from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import ROLE_ADMIN, SESSION_TTL_SECONDS
from app.db import get_db
from app.models import LoginSession, User
from app.security import now_iso


def bearer_token(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    return authorization[len("Bearer "):].strip()


def create_session(session: Session, user_id: int) -> str:
    session.query(LoginSession).filter(
        LoginSession.expires_at.isnot(None), LoginSession.expires_at <= now_iso()
    ).delete(synchronize_session=False)
    token = secrets.token_hex(32)
    expires_at = (datetime.now(UTC) + timedelta(seconds=SESSION_TTL_SECONDS)).isoformat()
    session.add(LoginSession(token=token, user_id=user_id, expires_at=expires_at))
    session.commit()
    return token


def delete_session(session: Session, token: str) -> None:
    session.query(LoginSession).filter(LoginSession.token == token).delete(synchronize_session=False)
    session.commit()


def get_current_user(
    authorization: str | None = Header(None),
    session: Session = Depends(get_db),
) -> User:
    token = bearer_token(authorization)
    user = (
        session.query(User)
        .join(LoginSession, LoginSession.user_id == User.id)
        .filter(LoginSession.token == token, LoginSession.expires_at > now_iso())
        .first()
    )
    if user is None:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return user
