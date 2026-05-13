from __future__ import annotations

import logging
import time

import httpx
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.config import get_settings
from src.db.engine import engine

logger = logging.getLogger(__name__)

_START_TIME = time.time()
_MAX_API_CACHE_TTL = 30.0
_last_max_api_status: str = "unknown"
_last_max_api_check: float = 0.0


async def get_health_status() -> dict[str, str]:
    """Возвращает статус здоровья: общий статус, состояние БД, MAX API, аптайм в секундах."""
    uptime_seconds = int(time.time() - _START_TIME)
    db_status = await _check_db()
    max_api_status = await _check_max_api()
    overall = "ok" if (db_status == "ok" and max_api_status == "ok") else "degraded"
    return {
        "status": overall,
        "db": db_status,
        "max_api": max_api_status,
        "uptime": str(uptime_seconds),
    }


async def _check_db() -> str:
    """Проверяет доступность БД через SELECT 1."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except SQLAlchemyError as exc:
        logger.warning("Health DB check failed: %s", exc)
        return "error"
    except Exception as exc:
        logger.warning("Health DB check failed unexpectedly: %s", exc)
        return "error"


async def _check_max_api() -> str:
    """Проверяет доступность MAX API через GET /me с кэшем и таймаутом."""
    global _last_max_api_status, _last_max_api_check
    now = time.time()
    if now - _last_max_api_check < _MAX_API_CACHE_TTL:
        return _last_max_api_status
    try:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{settings.max_api_base_url}/me",
                headers={"Authorization": settings.max_bot_token},
            )
            r.raise_for_status()
        status = "ok"
    except Exception as exc:
        logger.warning("Health MAX API check failed: %s", exc)
        status = "error"
    _last_max_api_check = now
    _last_max_api_status = status
    return status
