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
    sql_echo: bool = False
    llm_final_model: str = "claude-opus-5"
    llm_timeout_s: float = 60
    llm_max_retries: int = 3
    tts_fallback: str = "azure"
    navoiy_url: str = "http://tts:8010"
    aisha_api_key: str = ""
    aisha_url: str = "https://api.aisha.group"
    azure_speech_key: str = ""
    azure_speech_region: str = ""
    elevenlabs_api_key: str = ""
    fal_key: str = ""
    public_s3_url: str = "http://localhost:9000"
    flux_draft_tier: str = "schnell"
    flux_final_tier: str = "dev"


settings = Settings()
