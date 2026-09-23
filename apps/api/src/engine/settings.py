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
    langgraph_checkpointer: str = "memory"  # memory | postgres
    render_queue: str = "render"
    render_poll_interval_s: float = 5.0
    render_timeout_s: float = 900.0
    taste_top_k: int = 5
    crm_provider: str = "memory"
    twenty_url: str = "http://twenty:3000"
    twenty_api_key: str = ""
    chatwoot_url: str = "http://chatwoot:3000"
    chatwoot_api_token: str = ""
    chatwoot_account_id: int = 1
    chatwoot_webhook_secret: str = ""
    vault_dir: str = "/app/vault"
    vault_reindex_minutes: int = 10
    embedding_provider: str = "hash"
    # CRM dashboard (docs/06 "CRM web-sahifa", roadmap 5.8) "Demo ma'lumot yuklash"
    # tugmasi/POST /v1/crm/demo-seed uchun. DIQQAT: productionda albatta ``false``
    # bo'lishi kerak — aks holda ega haqiqiy workspace'iga soxta lid/sotuv yozilishi
    # mumkin (endpoint "workspace'da lid yo'q bo'lsagina" ishlaydi, lekin baribir
    # ishlab chiqarishda ochiq qoldirilmasin).
    crm_demo_seed_enabled: bool = True


settings = Settings()
