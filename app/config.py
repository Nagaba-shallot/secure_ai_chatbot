from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Secure AI Companion"
    environment: str = "development" 

    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    openai_api_key: str = ""
    model_name: str = "gpt-5.4-mini"  

    max_input_length: int = 4000
    max_output_length: int = 3000

    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60
    register_limit_requests: int = 5
    register_limit_window_seconds: int = 3600
    registration_open: bool = True
    login_limit_requests: int = 10  # per IP
    login_limit_window_seconds: int = 900
    login_email_limit_requests: int = 5  
    session_days: int = 30
    admin_user_ids: str = ""  
    event_retention_days: int = 90

    guest_message_limit: int = 5  
    require_signin: bool = False  
    daily_llm_call_limit: int = 500  
    trusted_proxy_count: int = 0  

    database_path: str = "data/companion.db"
    memory_every_n_messages: int = 5
    max_memories_per_user: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()