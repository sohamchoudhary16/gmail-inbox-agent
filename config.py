from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    # Gmail OAuth2
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_token_file: str = "tokens/gmail_token.json"
    gmail_mailbox_email: str = ""

    # Anthropic API
    anthropic_api_key: str = ""

    # Portal API
    portal_base_url: str = ""
    portal_api_key: str = ""

    # Service Configuration
    database_url: str = "sqlite:///./inbox_automation.db"
    worker_threads: int = 4
    poll_interval_seconds: int = 30
    pending_quote_timeout_hours: int = 24

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
