"""Application configuration.

Settings are read from environment variables prefixed with ``MEDRAG_`` and,
optionally, from a local ``.env`` file (see ``.env.example``). Secrets and
credentials must never be committed to version control.
"""

from __future__ import annotations

import re
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

    # --- Document ingestion (Milestone 2) ---
    ingestion_max_file_mb: int = Field(default=25, ge=1, le=500)
    ingestion_max_pdf_pages: int = Field(default=200, ge=1, le=5000)
    # A PDF page with fewer alphanumeric characters than this is treated as
    # "no usable text layer" and sent to OCR (if it contains images/graphics).
    pdf_min_text_chars: int = Field(default=30, ge=0)

    # Path to tesseract(.exe). Blank = look on PATH, then common Windows install folders.
    tesseract_cmd: Path | None = None
    # Tesseract language codes joined by "+", e.g. "eng" or "eng+hin".
    ocr_languages: str = "eng"
    ocr_dpi: int = Field(default=300, ge=72, le=600)  # render resolution for scanned PDF pages
    ocr_psm: int = Field(default=6, ge=3, le=13)  # Tesseract page segmentation mode
    ocr_timeout_seconds: int = Field(default=120, ge=5, le=1800)

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalise_log_level(cls, value: object) -> str:
        level = str(value).strip().upper()
        if level not in VALID_LOG_LEVELS:
            raise ValueError(f"log_level must be one of {', '.join(VALID_LOG_LEVELS)}")
        return level

    @field_validator("ocr_languages")
    @classmethod
    def _validate_ocr_languages(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_]+(\+[A-Za-z_]+)*", value):
            raise ValueError("ocr_languages must look like 'eng' or 'eng+hin'")
        return value

    @field_validator("log_file", "tesseract_cmd", mode="before")
    @classmethod
    def _blank_path_is_none(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (cached)."""
    return Settings()
