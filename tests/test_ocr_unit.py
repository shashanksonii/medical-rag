"""OCR helpers that do not need Tesseract installed."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.core.config import Settings
from app.ingestion import OCRUnavailableError
from app.ingestion import ocr as ocr_module
from app.ingestion.ocr import TesseractOCR, find_tesseract, prepare_for_ocr


@pytest.fixture
def no_system_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr_module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(ocr_module, "_WINDOWS_TESSERACT_PATHS", ())
    monkeypatch.delenv("LOCALAPPDATA", raising=False)


def test_find_tesseract_uses_configured_existing_file(tmp_path: Path) -> None:
    exe = tmp_path / "tesseract.exe"
    exe.write_text("x")
    assert find_tesseract(exe) == str(exe)


def test_find_tesseract_configured_missing_file_is_none(tmp_path: Path) -> None:
    assert find_tesseract(tmp_path / "missing.exe") is None


def test_find_tesseract_falls_back_to_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr_module.shutil, "which", lambda _name: "/usr/bin/tesseract")
    assert find_tesseract(None) == "/usr/bin/tesseract"


def test_find_tesseract_none_when_nothing_found(no_system_tesseract: None) -> None:
    assert find_tesseract(None) is None


def test_missing_tesseract_gives_install_instructions(no_system_tesseract: None) -> None:
    engine = TesseractOCR(Settings(_env_file=None))
    with pytest.raises(OCRUnavailableError) as info:
        engine.ensure_available()
    assert "UB-Mannheim" in info.value.message
    assert "MEDRAG_TESSERACT_CMD" in info.value.message


def test_bad_configured_path_is_named_in_error(tmp_path: Path) -> None:
    missing = tmp_path / "nope" / "tesseract.exe"
    engine = TesseractOCR(Settings(_env_file=None, tesseract_cmd=missing))
    with pytest.raises(OCRUnavailableError) as info:
        engine.recognize(Image.new("RGB", (50, 50), "white"))
    assert str(missing) in info.value.message


def test_non_executable_tesseract_path_is_reported(tmp_path: Path) -> None:
    fake = tmp_path / "tesseract.exe"
    fake.write_text("this is not a program")
    engine = TesseractOCR(Settings(_env_file=None, tesseract_cmd=fake))
    with pytest.raises(OCRUnavailableError):
        engine.ensure_available()


def test_small_images_are_upscaled() -> None:
    prepared, scale = prepare_for_ocr(Image.new("RGB", (600, 800), "white"))
    assert scale == 2.0 and prepared.size == (1200, 1600) and prepared.mode == "L"


def test_large_images_are_not_resized() -> None:
    prepared, scale = prepare_for_ocr(Image.new("RGB", (1600, 2000), "white"))
    assert scale == 1.0 and prepared.size == (1600, 2000)
