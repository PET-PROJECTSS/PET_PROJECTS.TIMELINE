from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime

PBKDF2_ITERATIONS = 600_000
_HASH_PREFIX = "pbkdf2_sha256"
_LEGACY_ITERATIONS = 100_000


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"{_HASH_PREFIX}${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def _parse_hash(stored: str) -> tuple[str, int] | None:
    """Возвращает (salt, iterations) для текущего или legacy-формата хэша."""
    parts = stored.split("$")
    if len(parts) == 2:
        salt, digest = parts
        iterations = _LEGACY_ITERATIONS
    elif len(parts) == 4 and parts[0] == _HASH_PREFIX:
        try:
            iterations = int(parts[1])
        except ValueError:
            return None
        salt, digest = parts[2], parts[3]
    else:
        return None
    try:
        bytes.fromhex(salt)
        bytes.fromhex(digest)
    except ValueError:
        return None
    return salt, iterations, digest


def verify_password(password: str, stored: str) -> bool:
    try:
        parsed = _parse_hash(stored)
        if parsed is None:
            return False
        salt, iterations, digest = parsed
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
        return hmac.compare_digest(check.hex(), digest)
    except Exception:
        return False


def needs_rehash(stored: str) -> bool:
    """True, если хэш в legacy-формате или с устаревшим числом итераций."""
    parts = stored.split("$")
    return not (
        len(parts) == 4
        and parts[0] == _HASH_PREFIX
        and parts[1] == str(PBKDF2_ITERATIONS)
    )


_DUMMY_HASH: str | None = None


def dummy_hash() -> str:
    """Возвращает хэш заведомо неверного пароля (для имитации проверки при несуществующем пользователе)."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("__dummy__")
    return _DUMMY_HASH
