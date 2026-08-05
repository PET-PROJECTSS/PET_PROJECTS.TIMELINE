from __future__ import annotations

import logging
from collections.abc import Generator

from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.config import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    BASE_DIR,
    DATABASE_URL,
    ENV,
    OBSERVER_PASSWORD,
    OBSERVER_USERNAME,
    ROLE_ADMIN,
    ROLE_OBSERVER,
    SCHEMA_VERSION,
)
from app.models import LoginSession, Roadmap, User
from app.payload import default_payload, migrate_payload
from app.security import hash_password, needs_rehash, now_iso, verify_password

logger = logging.getLogger("roadmap")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def run_migrations() -> None:
    """Единый путь создания/обновления схемы — только через Alembic."""
    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(cfg, "head")


def _has_schema() -> bool:
    tables = set(inspect(engine).get_table_names())
    return {"users", "roadmaps", "sessions", "login_attempts"}.issubset(tables)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _sync_users(session: Session) -> None:
    configured = [
        (ADMIN_USERNAME, ADMIN_PASSWORD, ROLE_ADMIN),
        (OBSERVER_USERNAME, OBSERVER_PASSWORD, ROLE_OBSERVER),
    ]
    seen: set[str] = set()
    for username, password, role in configured:
        if username in seen:
            continue
        seen.add(username)
        user = session.query(User).filter_by(username=username).first()
        if user is None:
            session.add(User(username=username, password_hash=hash_password(password), role=role))
        elif not verify_password(password, user.password_hash) or needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
            user.role = role
            logger.info("Пароль пользователя «%s» синхронизирован с конфигурацией", username)


def seed() -> None:
    if not _has_schema():
        if ENV == "prod":
            raise RuntimeError(
                "Схема БД не создана. В prod миграции выполняет docker-entrypoint (`alembic upgrade head`); "
                "при ручном запуске выполните: alembic upgrade head"
            )
        run_migrations()
    session = SessionLocal()
    try:
        now = now_iso()
        session.query(LoginSession).filter(
            LoginSession.expires_at.isnot(None), LoginSession.expires_at <= now
        ).delete(synchronize_session=False)
        had_users = session.query(User).count() > 0
        for roadmap in session.query(Roadmap).order_by(Roadmap.id).all():
            migrated, changed = migrate_payload(roadmap.payload)
            if changed:
                roadmap.payload = migrated
                logger.info("Roadmap %s мигрирован до schema_version %d", roadmap.id, SCHEMA_VERSION)
        _sync_users(session)
        if not had_users and session.query(Roadmap).count() == 0:
            session.add(Roadmap(name="Купить квартиру", payload=default_payload(), version=0))
        session.commit()
    finally:
        session.close()
