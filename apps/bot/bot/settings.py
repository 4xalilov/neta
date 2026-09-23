from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    owner_tg_id: int = 0
    api_url: str = "http://api:8000"
    redis_url: str = "redis://redis:6379/0"

    # Webhook mode is optional; polling is the default (see __main__.py).
    webhook_mode: bool = False
    webhook_url: str = ""
    webhook_path: str = "/webhook"
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8080

    # Brief progress polling.
    brief_poll_interval_s: float = 5.0
    brief_poll_timeout_s: float = 600.0


settings = Settings()
