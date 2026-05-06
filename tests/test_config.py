from src.config import Settings


def test_settings_load_with_token(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "test_token")
    s = Settings()
    assert s.max_bot_token == "test_token"
    assert s.max_api_base_url == "https://platform-api.max.ru"


def test_admin_ids_parsing(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "t")
    monkeypatch.setenv("MAX_ADMIN_USER_IDS", "111,222 , 333")
    s = Settings()
    assert s.admin_ids_list == ["111", "222", "333"]
