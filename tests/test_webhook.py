import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(autouse=True)
def disable_max_api_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Предотвращает реальные сетевые вызовы MAX API при запуске lifespan в тестах."""
    monkeypatch.setenv("WEBHOOK_URL", "")

    async def _noop(*args: object, **kwargs: object) -> None:
        pass

    monkeypatch.setattr("src.main.MAXClient.subscribe_webhook", _noop)
    monkeypatch.setattr("src.main.MAXClient.set_bot_commands", _noop)


def test_health() -> None:
    with TestClient(app) as c:
        r = c.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["db"] == "ok"
        assert int(data["uptime"]) >= 0


def test_webhook_accepts_post() -> None:
    with TestClient(app) as c:
        r = c.post("/webhook", json={"update_type": "message", "message": {}})
        assert r.status_code == 200
        assert r.json() == {"ok": True}
