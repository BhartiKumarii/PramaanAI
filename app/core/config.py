from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"

    database_url: str = "postgresql+psycopg2://pramaan:pramaan@localhost:5432/pramaan"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 1440

    # Base64-encoded 32-byte key for AES-256-GCM. No default — must be set
    # explicitly per environment, never hardcoded.
    encryption_key: str

    # Dedicated key for HMAC-signing score records (see app/core/hmac_signing.py).
    # Deliberately separate from jwt_secret_key/encryption_key — no cross-purpose
    # key reuse. No default — must be set explicitly per environment.
    hmac_secret_key: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
