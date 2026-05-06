from fastapi.testclient import TestClient

from src.main import app


def test_health():
    with TestClient(app) as c:
        r = c.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_webhook_accepts_post():
    with TestClient(app) as c:
        r = c.post("/webhook", json={"update_type": "message", "message": {}})
        assert r.status_code == 200
        assert r.json() == {"ok": True}
