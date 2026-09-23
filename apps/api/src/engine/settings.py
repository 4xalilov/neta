from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    redis_url: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str = "assets"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    llm_draft_model: str = "gemini-2.5-flash"
    llm_critic_model: str = "claude-sonnet-5"
    llm_vision_model: str = "gemini-2.5-flash"
    tts_provider: str = "azure"
    tts_voice: str = "uz-UZ-MadinaNeural"
    telegram_bot_token: str = ""
    owner_tg_id: int = 0


settings = Settings()
