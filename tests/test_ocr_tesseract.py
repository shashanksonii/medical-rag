"""End-to-end tests with the real Tesseract engine.

These are skipped automatically when Tesseract is not installed. OCR output is
checked only for robust tokens - OCR can misread characters (for example
"P001" as "POO1" or a superscript), which is exactly why Milestone 3 must
validate values and later milestones evaluate extraction accuracy.
"""

from __future__ import annotations

import pytest
from PIL import Image

from app.core.config import Settings
from app.ingestion import (
    ExtractionMethod,
    OCRLanguageError,
    SourceType,
    ingest_bytes,
)
from app.ingestion.ocr import TesseractOCR, find_tesseract
from tests import factories as f

pytestmark = pytest.mark.skipif(
    find_tesseract(None) is None, reason="Tesseract OCR is not installed"
)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, environment="testing")


def _assert_report_content(text: str, lines: list[str]) -> None:
    assert "Hemoglobin" in text
    assert "SYNTHETIC" in text
    hb = next(line for line in lines if "Hemoglobin" in line)
    assert "13.2" in hb and "12.0" in hb  # value and range stay on the same row
    assert "105" in next(line for line in lines if "Glucose" in line)


def test_png_ocr_end_to_end(settings: Settings) -> None:
    doc = ingest_bytes(f.png_bytes(f.render_report_image()), "scan.png", settings=settings)
    page = doc.pages[0]
    assert doc.source_type is SourceType.IMAGE and page.method is ExtractionMethod.OCR
    assert page.ocr_confidence is not None and page.ocr_confidence > 50
    _assert_report_content(page.clean_text, [ln.text for ln in page.lines])
    for ln in page.lines:  # boxes are in original-image pixel coordinates
        assert 0 <= ln.bbox[0] < ln.bbox[2] <= page.width + 2
        assert 0 <= ln.bbox[1] < ln.bbox[3] <= page.height + 2


def test_jpeg_ocr_end_to_end(settings: Settings) -> None:
    doc = ingest_bytes(f.jpeg_bytes(f.render_report_image()), "scan.jpg", settings=settings)
    _assert_report_content(doc.pages[0].clean_text, [ln.text for ln in doc.pages[0].lines])


def test_scanned_pdf_ocr_end_to_end(settings: Settings) -> None:
    doc = ingest_bytes(f.make_scanned_pdf(), "scan.pdf", settings=settings)
    assert doc.source_type is SourceType.SCANNED_PDF
    page = doc.pages[0]
    assert page.method is ExtractionMethod.OCR and page.ocr_dpi == 300
    _assert_report_content(page.clean_text, [ln.text for ln in page.lines])


def test_mixed_pdf_end_to_end(settings: Settings) -> None:
    doc = ingest_bytes(f.make_mixed_pdf(), "mixed.pdf", settings=settings)
    assert doc.source_type is SourceType.MIXED_PDF
    assert [p.method for p in doc.pages] == [
        ExtractionMethod.PDF_TEXT,
        ExtractionMethod.OCR,
        ExtractionMethod.PDF_TEXT,
    ]
    # Digital page is exact; OCR page is checked for robust tokens only.
    assert "Patient ID: P001" in doc.pages[0].clean_text
    _assert_report_content(doc.pages[1].clean_text, [ln.text for ln in doc.pages[1].lines])


def test_small_image_is_upscaled_but_coordinates_stay_in_original_space(settings: Settings) -> None:
    image = f.render_report_image(size=(620, 877), font_size=18)
    doc = ingest_bytes(f.png_bytes(image), "small.png", settings=settings)
    page = doc.pages[0]
    assert (page.width, page.height) == (620, 877)
    assert page.lines, "expected some OCR output"
    assert all(ln.bbox[2] <= 620 + 2 for ln in page.lines)


def test_blank_image_yields_no_text_warning(settings: Settings) -> None:
    import io

    buf = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buf, format="PNG")
    page = ingest_bytes(buf.getvalue(), "blank.png", settings=settings).pages[0]
    assert page.clean_text == "" and any("no text" in w for w in page.warnings)


def test_missing_language_pack_is_reported() -> None:
    engine = TesseractOCR(Settings(_env_file=None, ocr_languages="zzz"))
    with pytest.raises(OCRLanguageError) as info:
        engine.ensure_available()
    assert "zzz" in info.value.message
