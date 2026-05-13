from __future__ import annotations

import logging
import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.db.engine import engine

logger = logging.getLogger(__name__)

_START_TIME = time.time()


async def get_health_status() -> dict[str, str]:
    """Возвращает статус здоровья: общий статус, состояние БД, аптайм в секундах."""
    uptime_seconds = int(time.time() - _START_TIME)
    db_status = await _check_db()
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
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
