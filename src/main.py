from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from src.bot.max_client import MAXClient
from src.bot.webhook import router as webhook_router
from src.bot.webhook import set_update_processor
from src.config import get_settings

logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def process_update(payload: dict[str, Any]) -> None:
    """Обработчик update. В F05+ будет роутить в handlers."""
    logger.info("processing update: type=%s", payload.get("update_type"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    set_update_processor(process_update)

    if settings.webhook_url:
        async with MAXClient() as client:
            ok = await client.subscribe_webhook(settings.webhook_url)
            if ok:
                logger.info("Webhook subscribed at %s", settings.webhook_url)
            else:
                logger.warning("Failed to subscribe webhook")

    yield

    logger.info("Shutting down...")


app = FastAPI(title="Astralaser MAX Bot v2", lifespan=lifespan)
app.include_router(webhook_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=get_settings().app_port)
