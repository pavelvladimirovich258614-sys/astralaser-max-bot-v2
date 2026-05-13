from __future__ import annotations

import logging

DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s - %(message)s"
DEFAULT_DATEFMT = "%Y-%m-%dT%H:%M:%SZ"


class _UTCFormatter(logging.Formatter):
    """Formatter that uses UTC time for asctime."""

    converter = logging.time.gmtime  # type: ignore[attr-defined]


def setup_logging(log_level: str | int = logging.INFO) -> None:
    """Настраивает глобальное логирование с единым форматом.

    Безопасно вызывать несколько раз — не добавляет дублирующих хендлеров.
    """
    if logging.root.handlers:
        # Уже настроено — только обновляем уровень
        logging.root.setLevel(log_level)
        for handler in logging.root.handlers:
            handler.setLevel(log_level)
        return

    formatter = _UTCFormatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATEFMT)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(log_level)
    logging.root.addHandler(handler)
    logging.root.setLevel(log_level)
