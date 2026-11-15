from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.config import Settings
from app.ingestion import (
    CorruptFileError,
    ExtractionMethod,
    FileTooLargeError,
    FileType,
    SourceType,
    ingest_bytes,
)
from app.ingestion import ocr as ocr_module
from app.ingestion.ocr import load_image
from tests import factories as f


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, environment="testing")


@pytest.mark.parametrize(
    ("make", "name", "file_type"),
    [
        (lambda: f.png_bytes(f.render_report_image()), "scan.png", FileType.PNG),
        (lambda: f.jpeg_bytes(f.render_report_image()), "scan.jpg", FileType.JPEG),
        (lambda: f.jpeg_bytes(f.render_report_image()), "scan.JPEG", FileType.JPEG),
    ],
)
def test_image_ingested_via_ocr(settings: Settings, make, name: str, file_type: FileType) -> None:
    ocr = f.FakeOCR(lines=["Glucose  105  mg/dL  70 - 99"], confidence=91.0)
    doc = ingest_bytes(make(), name, patient_id="P001", settings=settings, ocr=ocr)

    assert doc.file_type is file_type
    assert doc.source_type is SourceType.IMAGE
    assert doc.page_count == 1 and doc.warnings == []
    page = doc.pages[0]
    assert page.page_number == 1
    assert page.method is ExtractionMethod.OCR
    assert page.ocr_confidence == 91.0
    assert page.coordinate_unit == "px"
    assert (page.width, page.height) == (1240, 1754)
    assert ocr.last_image_size == (1240, 1754)
    assert page.clean_text == "Glucose  105  mg/dL  70 - 99"
    assert doc.patient_id == "P001"


def test_palette_and_grayscale_images_are_accepted(settings: Settings) -> None:
    for mode in ("P", "L", "1"):
        buf = io.BytesIO()
        Image.new("RGB", (300, 200), "white").convert(mode).save(buf, format="PNG")
        doc = ingest_bytes(buf.getvalue(), "x.png", settings=settings, ocr=f.FakeOCR())
        assert doc.pages[0].width == 300


def test_extension_mismatch_warns_and_uses_content_type(settings: Settings) -> None:
    doc = ingest_bytes(
        f.png_bytes(f.render_report_image()),
        "actually-a-png.pdf",
        settings=settings,
        ocr=f.FakeOCR(),
    )
    assert doc.file_type is FileType.PNG
    assert any("does not match" in w for w in doc.warnings)


def test_no_extension_gives_no_warning(settings: Settings) -> None:
    doc = ingest_bytes(
        f.png_bytes(f.render_report_image()), "upload", settings=settings, ocr=f.FakeOCR()
    )
    assert doc.warnings == []


def test_ocr_unavailable_for_image_raises(settings: Settings) -> None:
    from app.ingestion import OCRUnavailableError

    with pytest.raises(OCRUnavailableError):
        ingest_bytes(
            f.png_bytes(f.render_report_image()),
            "a.png",
            settings=settings,
            ocr=f.FakeOCR(available=False),
        )


def test_corrupt_png_raises(settings: Settings) -> None:
    with pytest.raises(CorruptFileError):
        ingest_bytes(b"\x89PNG\r\n\x1a\n" + b"not image data" * 10, "bad.png", settings=settings)


def test_truncated_jpeg_raises(settings: Settings) -> None:
    data = f.jpeg_bytes(f.render_report_image())
    with pytest.raises(CorruptFileError):
        ingest_bytes(data[: len(data) // 2], "cut.jpg", settings=settings, ocr=f.FakeOCR())


def test_oversized_image_rejected(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    monkeypatch.setattr(ocr_module, "MAX_IMAGE_PIXELS", 1000)
    with pytest.raises(FileTooLargeError):
        ingest_bytes(
            f.png_bytes(f.render_report_image()), "big.png", settings=settings, ocr=f.FakeOCR()
        )


# ------------------------------------------------------------------ load_image
def test_transparent_png_is_flattened_onto_white() -> None:
    buf = io.BytesIO()
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(buf, format="PNG")
    image = load_image(buf.getvalue())
    assert image.mode == "RGB"
    assert image.getpixel((5, 5)) == (255, 255, 255)


def test_exif_orientation_is_applied() -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise to display
    buf = io.BytesIO()
    Image.new("RGB", (100, 50), "white").save(buf, format="JPEG", exif=exif)
    assert load_image(buf.getvalue()).size == (50, 100)
