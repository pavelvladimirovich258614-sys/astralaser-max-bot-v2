from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request

logger = logging.getLogger(__name__)
router = APIRouter()

# Глобальная переменная для router'а handlers (заполняется в main.py при старте)
_update_processor: Callable[[dict[str, Any]], Any] | None = None


def set_update_processor(processor: Callable[[dict[str, Any]], Any]) -> None:
    """Регистрирует обработчик updates от MAX. Вызывается из main.py."""
    global _update_processor
    _update_processor = processor


@router.post("/webhook")
async def receive_update(request: Request, background: BackgroundTasks) -> dict[str, Any]:
    """MAX доставляет update сюда. Отвечаем 200 OK мгновенно, обработка — в фоне."""
    payload = await request.json()
    logger.info("webhook received update: %s", payload.get("update_type", "unknown"))

    if _update_processor is not None:
        background.add_task(_update_processor, payload)

    return {"ok": True}


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
