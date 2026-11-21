"""Application settings and environment validation using Pydantic."""

from functools import lru_cache
from typing import Any, List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


class Settings(BaseSettings):
    """Central configuration for BolKhata AI backend."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application Settings
    APP_NAME: str = "BolKhata AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = "bolkhata-dev-secret-key-change-in-production"

    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Database
    DATABASE_URL: str = "sqlite:///./bolkhata.db"

    # Groq LLM Configuration (Intent parsing only; cannot write to ledger directly)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Gnani Voice Engine (WebSocket Streaming: Prisma v3.0 STT & Timbre v3.0 TTS)
    GNANI_PRISMA_WS_URL: str = "wss://api.gnani.ai/v3/prisma/stream"
    GNANI_TIMBRE_WS_URL: str = "wss://api.gnani.ai/v3/timbre/stream"
    GNANI_API_KEY: str = ""
    GNANI_TOKEN: str = ""
    GNANI_ACCESS_KEY: str = ""

    # Multilingual Voice Settings
    DEFAULT_LANGUAGE: str = "kannada"
    SUPPORTED_LANGUAGES: Union[List[str], str] = ["kannada", "hindi", "english"]

    # Logging
    LOG_LEVEL: str = "INFO"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value: Any) -> bool:
        if isinstance(value, str):
            clean = value.strip().lower()
            if clean in ("release", "prod", "production", "false", "0", "no", "off"):
                return False
            return clean in ("true", "1", "yes", "t", "enable", "enabled", "debug", "dev")
        return bool(value)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("SUPPORTED_LANGUAGES", mode="before")
    @classmethod
    def parse_supported_languages(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                return [lang.strip() for lang in value.split(",") if lang.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
