from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.config import LOGIN_LOCKOUT_SECONDS, LOGIN_MAX_ATTEMPTS
from app.models import LoginAttempt


class LoginRateLimiter:
    """Ограничение попыток входа, общее для всех воркеров (хранится в БД)."""

    def __init__(self, max_attempts: int, window: float, lockout: float):
        self.max_attempts = max_attempts
        self.window = window
        self.lockout = lockout

    def is_blocked(self, session: Session, key: str) -> bool:
        row = session.get(LoginAttempt, key)
        if row is None:
            return False
        now = time.time()
        if now - row.window_start > self.window:
            session.delete(row)
            session.commit()
            return False
        return row.blocked_until is not None and now < row.blocked_until

    def failure(self, session: Session, key: str) -> None:
        now = time.time()
        row = session.get(LoginAttempt, key)
        if row is None or now - row.window_start > self.window:
            row = LoginAttempt(key=key, count=0, window_start=now, blocked_until=None)
            session.add(row)
        row.count += 1
        if row.count >= self.max_attempts:
            row.blocked_until = now + self.lockout
        session.commit()

    def success(self, session: Session, key: str) -> None:
        session.query(LoginAttempt).filter(LoginAttempt.key == key).delete(synchronize_session=False)
        session.commit()


login_limiter = LoginRateLimiter(LOGIN_MAX_ATTEMPTS, 60.0, LOGIN_LOCKOUT_SECONDS)
