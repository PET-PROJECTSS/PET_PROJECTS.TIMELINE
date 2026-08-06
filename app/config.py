from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

logger = logging.getLogger("roadmap")

BASE_DIR = Path(__file__).resolve().parent.parent
ENV = os.getenv("ENV", "dev")
SCHEMA_VERSION = 3

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///" + str(BASE_DIR / "roadmaps.db").replace("\\", "/"),
)

SESSION_TTL_SECONDS = int(os.getenv("TIMELINE_SESSION_TTL_SECONDS", str(30 * 24 * 3600)))
LOGIN_MAX_ATTEMPTS = int(os.getenv("TIMELINE_LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_LOCKOUT_SECONDS = int(os.getenv("TIMELINE_LOGIN_LOCKOUT_SECONDS", "30"))
MAX_PAYLOAD_BYTES = int(os.getenv("TIMELINE_MAX_PAYLOAD_BYTES", str(2 * 1024 * 1024)))

ROLE_ADMIN = "admin"
ROLE_OBSERVER = "observer"

ADMIN_USERNAME = os.getenv("TIMELINE_ADMIN_USER", "admin")
OBSERVER_USERNAME = os.getenv("TIMELINE_OBSERVER_USER", "observer")


def _resolve_password(var: str, label: str) -> str:
    password = os.getenv(var)
    if password:
        return password
    if ENV == "prod":
        raise RuntimeError(f"{var} обязателен в prod-окружении")
    password = secrets.token_urlsafe(12)
    logger.warning(
        "Переменная %s не задана, сгенерирован разовый пароль для «%s»: %s "
        "(задайте её в .env, чтобы пароль сохранялся между запусками)",
        var,
        label,
        password,
    )
    return password


ADMIN_PASSWORD = _resolve_password("TIMELINE_ADMIN_PASSWORD", ADMIN_USERNAME)
OBSERVER_PASSWORD = _resolve_password("TIMELINE_OBSERVER_PASSWORD", OBSERVER_USERNAME)
