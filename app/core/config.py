import base64
import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


def _generate_key_b64(n_bytes: int = 32) -> str:
    return base64.b64encode(os.urandom(n_bytes)).decode()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: str = "development"

    database_url: str = "postgresql+psycopg2://pramaan:pramaan@localhost:5432/pramaan"

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 1440

    encryption_key: str = ""
    hmac_secret_key: str = ""

    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def default_jwt_secret(cls, v: str) -> str:
        return v or _generate_key_b64()

    @field_validator("encryption_key", mode="before")
    @classmethod
    def default_encryption_key(cls, v: str) -> str:
        return v or _generate_key_b64()

    @field_validator("hmac_secret_key", mode="before")
    @classmethod
    def default_hmac_key(cls, v: str) -> str:
        return v or _generate_key_b64()

    # CORS - comma-separated origins
    cors_origins: str | list[str] = "http://localhost:5173,http://127.0.0.1:5173,https://pramaanai-703j.onrender.com"

    # Directory to store uploaded images for web dashboard review
    images_dir: str = "images"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
