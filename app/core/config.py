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

    # --- Modular document-verification pipeline (/api/v1/verify/*) ---
    # Versioned reference data (checkpoints, border rules, templates, mock registries).
    pramaan_reference_data_dir: str = "reference_data"
    # Trained YOLO11 weights for region detection. Empty = the classical
    # OpenCV detector is used and every result says so.
    pramaan_yolo_weights: str = ""
    pramaan_yolo_conf: float = 0.35
    # "mock" = fictional synthetic registry; "disabled" = REGISTRY_NOT_AVAILABLE.
    pramaan_dl_registry_mode: str = "mock"
    pramaan_travel_registry_mode: str = "mock"
    # Optional vision-language reasoner (OpenAI-compatible chat endpoint, e.g.
    # a self-hosted Qwen-VL or Gemini's OpenAI-compatible API). Advisory text
    # only — it never changes a check status. Empty base URL = disabled.
    pramaan_vlm_base_url: str = ""
    pramaan_vlm_model: str = ""
    pramaan_vlm_api_key: str = ""
    # Images are only sent to the VLM when this is explicitly enabled.
    pramaan_vlm_send_image: bool = False
    pramaan_vlm_timeout_seconds: float = 20.0
    # Concurrency: pipelines running at once per process (0 = auto: half the
    # CPU cores, capped at 4) and how many more may wait before 503.
    pramaan_max_concurrent_verifications: int = 0
    # ONNX Runtime threads per PP-OCR engine; 0 = auto (half the cores, max 4).
    # Using every core oversubscribes the CPU and measured ~2x slower.
    pramaan_ocr_threads: int = 0
    pramaan_max_queued_verifications: int = 16

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
