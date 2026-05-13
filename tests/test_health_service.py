import pytest

from src.services import health_service


@pytest.mark.asyncio
async def test_get_health_status_includes_uptime() -> None:
    """Результат содержит uptime как неотрицательное целое (строка)."""
    result = await health_service.get_health_status()
    assert "uptime" in result
    assert int(result["uptime"]) >= 0


@pytest.mark.asyncio
async def test_get_health_status_db_ok() -> None:
    """При работающей БД статус ok и db ok."""
    result = await health_service.get_health_status()
    assert result["status"] == "ok"
    assert result["db"] == "ok"


@pytest.mark.asyncio
async def test_get_health_status_db_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """При ошибке БД статус degraded и db error."""

    async def _fake_check_db() -> str:
        return "error"

    monkeypatch.setattr("src.services.health_service._check_db", _fake_check_db)
    result = await health_service.get_health_status()
    assert result["status"] == "degraded"
    assert result["db"] == "error"
    assert int(result["uptime"]) >= 0
