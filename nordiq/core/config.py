"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://nordiq:password@localhost:5432/nordiq"
    sync_database_url: str = "postgresql://nordiq:password@localhost:5432/nordiq"

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    encryption_key: str = ""  # Fernet key for encrypting connector credentials
    access_token_expire_minutes: int = 60

    # Email
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "notifications@uusio.io"
    smtp_tls: bool = True

    # AWS
    aws_region: str = "eu-north-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket: str = ""
    use_s3: bool = False
    use_ses: bool = False
    ses_from: str = ""    # SES verified sender; falls back to smtp_from if empty

    # Storage
    report_storage_path: str = "./reports"

    # App
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    frontend_url: str = "http://localhost:8501"
    api_url: str = "http://localhost:8000"

    @field_validator("encryption_key")
    @classmethod
    def encryption_key_must_be_set_in_production(cls, v: str, info) -> str:
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
