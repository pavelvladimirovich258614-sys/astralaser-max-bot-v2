import logging

import pytest

from src.utils.logging_config import DEFAULT_DATEFMT, _UTCFormatter, setup_logging


class TestSetupLogging:
    def test_sets_root_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """setup_logging устанавливает уровень root logger."""
        # Очистка предыдущих хендлеров
        logging.root.handlers.clear()
        setup_logging("DEBUG")
        assert logging.root.level == logging.DEBUG

    def test_sets_root_level_from_int(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """setup_logging принимает int level."""
        logging.root.handlers.clear()
        setup_logging(logging.WARNING)
        assert logging.root.level == logging.WARNING

    def test_idempotent_no_duplicate_handlers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Повторный вызов не добавляет дублирующих хендлеров."""
        logging.root.handlers.clear()
        setup_logging("INFO")
        first_count = len(logging.root.handlers)
        setup_logging("DEBUG")
        assert len(logging.root.handlers) == first_count
        assert logging.root.level == logging.DEBUG

    def test_formatter_pattern(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Форматтер содержит asctime, levelname, name, message."""
        logging.root.handlers.clear()
        setup_logging("INFO")
        handler = logging.root.handlers[0]
        fmt = handler.formatter._fmt  # type: ignore[union-attr]
        assert "%(asctime)s" in fmt
        assert "%(levelname)s" in fmt
        assert "%(name)s" in fmt
        assert "%(message)s" in fmt

    def test_datefmt_iso_like(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """datefmt использует ISO-like формат."""
        logging.root.handlers.clear()
        setup_logging("INFO")
        handler = logging.root.handlers[0]
        assert handler.formatter.datefmt == DEFAULT_DATEFMT


class TestUTCFormatter:
    def test_uses_gmtime(self) -> None:
        """_UTCFormatter.converter указывает на gmtime."""
        assert _UTCFormatter.converter is logging.time.gmtime
