"""Milestone 2 settings."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_ingestion_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.ingestion_max_file_mb == 25
    assert s.ingestion_max_pdf_pages == 200
    assert s.pdf_min_text_chars == 30
    assert s.tesseract_cmd is None
    assert s.ocr_languages == "eng"
    assert s.ocr_dpi == 300
    assert s.ocr_psm == 6


def test_ingestion_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDRAG_OCR_DPI", "200")
    monkeypatch.setenv("MEDRAG_OCR_LANGUAGES", "eng+hin")
    monkeypatch.setenv("MEDRAG_TESSERACT_CMD", r"C:\Tools\tesseract.exe")
    s = Settings(_env_file=None)
    assert s.ocr_dpi == 200
    assert s.ocr_languages == "eng+hin"
    assert s.tesseract_cmd == Path(r"C:\Tools\tesseract.exe")


def test_blank_tesseract_cmd_means_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDRAG_TESSERACT_CMD", "")
    assert Settings(_env_file=None).tesseract_cmd is None


@pytest.mark.parametrize("languages", ["eng hin", "eng+", "+eng", "eng;hin", ""])
def test_invalid_ocr_languages_rejected(languages: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ocr_languages=languages)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ocr_dpi", 50),
        ("ocr_dpi", 1200),
        ("ocr_psm", 2),
        ("ocr_psm", 14),
        ("ingestion_max_file_mb", 0),
    ],
)
def test_out_of_range_values_rejected(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
