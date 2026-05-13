import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import delete, func, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.logging_config import setup_logging

setup_logging(logging.INFO)
logger = logging.getLogger(__name__)


async def wipe_product_photos() -> int:
    from src.db.engine import async_session_maker
    from src.db.models import ProductPhoto

    async with async_session_maker() as session:
        result = await session.execute(select(func.count()).select_from(ProductPhoto))
        before_count = result.scalar_one()
        logger.info("Found %s rows in product_photos", before_count)

        if before_count == 0:
            logger.info("Already empty, nothing to do")
            return 0

        await session.execute(delete(ProductPhoto))
        await session.commit()

        result = await session.execute(select(func.count()).select_from(ProductPhoto))
        after_count = result.scalar_one()
        logger.info("After wipe: %s rows", after_count)

        return after_count


if __name__ == "__main__":
    asyncio.run(wipe_product_photos())
