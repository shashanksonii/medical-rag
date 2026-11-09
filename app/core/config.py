"""Application configuration.

Settings are read from environment variables prefixed with ``MEDRAG_`` and,
optionally, from a local ``.env`` file (see ``.env.example``). Secrets and
credentials must never be committed to version control.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

VALID_LOG_LEVELS = ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG")


class Settings(BaseSettings):
    """Typed, validated application settings."""

    model_config = SettingsConfigDict(
        env_prefix="MEDRAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Medical Record RAG API"
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = False

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)

    log_level: str = "INFO"
    # Optional rotating log file. Blank/unset means console-only logging.
    log_file: Path | None = None

    # Root folder for synthetic reports, curated knowledge and evaluation data.
    data_dir: Path = Path("data")

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalise_log_level(cls, value: object) -> str:
        level = str(value).strip().upper()
        if level not in VALID_LOG_LEVELS:
            raise ValueError(f"log_level must be one of {', '.join(VALID_LOG_LEVELS)}")
        return level

    @field_validator("log_file", mode="before")
    @classmethod
    def _blank_log_file_is_none(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (cached)."""
    return Settings()
