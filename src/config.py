from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    max_bot_token: str
    max_api_base_url: str = "https://platform-api.max.ru"
    webhook_url: str = ""
    app_port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./astralaser.db"
    max_admin_user_ids: str = ""
    max_admin_chat_ids: str = ""
    manager_name: str = "Менеджер"
    manager_phone: str = ""
    manager_vk_link: str = ""
    max_manager_link: str = ""
    max_channel_link: str = ""
    ozon_link: str = ""
    wildberries_link: str = ""
    max_required_channel: str = ""
    max_required_channel_url: str = ""
    log_level: str = "INFO"
    http_timeout: int = 30
    working_hours: str = "пн–сб 10:00–18:00 МСК"

    @property
    def admin_ids_list(self) -> list[str]:
        return [x.strip() for x in self.max_admin_user_ids.split(",") if x.strip()]

    @property
    def admin_chat_ids_list(self) -> list[str]:
        return [x.strip() for x in self.max_admin_chat_ids.split(",") if x.strip()]


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
