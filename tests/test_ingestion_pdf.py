from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path

import pymupdf
import pytest

from app.core.config import Settings
from app.ingestion import (
    CorruptFileError,
    EncryptedPDFError,
    ExtractionMethod,
    FileType,
    OCRUnavailableError,
    SourceType,
    TooManyPagesError,
    ingest_bytes,
    ingest_file,
)
from app.ingestion.pdf_extractor import looks_garbled
from tests import factories as f


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, environment="testing")


# ------------------------------------------------------------------ digital PDFs
def test_digital_pdf_uses_text_layer_and_never_calls_ocr(settings: Settings) -> None:
    ocr = f.FakeOCR()
    doc = ingest_bytes(f.make_digital_pdf(), "report.pdf", settings=settings, ocr=ocr)

    assert doc.file_type is FileType.PDF
    assert doc.source_type is SourceType.DIGITAL_PDF
    assert doc.page_count == 1 and len(doc.pages) == 1
    page = doc.pages[0]
    assert page.page_number == 1
    assert page.method is ExtractionMethod.PDF_TEXT
    assert page.coordinate_unit == "pt"
    assert round(page.width) == 595 and round(page.height) == 842
    assert page.ocr_confidence is None and page.ocr_dpi is None
    assert ocr.recognize_calls == 0


def test_digital_pdf_works_even_if_ocr_is_unavailable(settings: Settings) -> None:
    doc = ingest_bytes(
        f.make_digital_pdf(), "r.pdf", settings=settings, ocr=f.FakeOCR(available=False)
    )
    assert doc.source_type is SourceType.DIGITAL_PDF


@pytest.mark.parametrize("row", f.TABLE_ROWS)
def test_table_rows_keep_their_cells_on_one_line(settings: Settings, row: tuple[str, ...]) -> None:
    doc = ingest_bytes(f.make_digital_pdf(), "r.pdf", settings=settings, ocr=f.FakeOCR())
    matching = [ln.text for ln in doc.pages[0].lines if ln.text.startswith(row[0])]
    assert len(matching) == 1
    assert re.split(r"\s{2,}", matching[0]) == list(row)


def test_header_values_and_dates_preserved(settings: Settings) -> None:
    doc = ingest_bytes(f.make_digital_pdf(), "r.pdf", settings=settings, ocr=f.FakeOCR())
    text = doc.pages[0].clean_text
    assert "Patient ID: P001" in text
    assert "Report Date: 12/08/2026" in text
    assert text.splitlines()[0] == "SYNTHETIC LABORATORY REPORT"


def test_lines_are_numbered_and_inside_the_page(settings: Settings) -> None:
    page = ingest_bytes(f.make_digital_pdf(), "r.pdf", settings=settings, ocr=f.FakeOCR()).pages[0]
    assert [ln.line_number for ln in page.lines] == list(range(1, len(page.lines) + 1))
    assert page.clean_text.splitlines() == [ln.text for ln in page.lines]
    for ln in page.lines:
        x0, y0, x1, y1 = ln.bbox
        assert 0 <= x0 < x1 <= page.width and 0 <= y0 < y1 <= page.height
    ys = [ln.bbox[1] for ln in page.lines]
    assert ys == sorted(ys)  # top-to-bottom reading order


def test_multi_page_numbering_and_document_text(settings: Settings) -> None:
    doc = ingest_bytes(f.make_digital_pdf(pages=3), "r.pdf", settings=settings, ocr=f.FakeOCR())
    assert [p.page_number for p in doc.pages] == [1, 2, 3]
    assert doc.clean_text.count("SYNTHETIC LABORATORY REPORT") == 3


def test_provenance_metadata(settings: Settings) -> None:
    data = f.make_digital_pdf()
    doc = ingest_bytes(
        data,
        r"C:\Users\someone\Downloads\lab report.pdf",
        patient_id="P001",
        document_id="DOC-TEST-1",
        settings=settings,
        ocr=f.FakeOCR(),
    )
    assert doc.filename == "lab report.pdf"  # path stripped
    assert doc.document_id == "DOC-TEST-1"
    assert doc.patient_id == "P001"
    assert doc.sha256 == hashlib.sha256(data).hexdigest()
    assert doc.size_bytes == len(data)
    assert doc.ingested_at.tzinfo is not None and isinstance(doc.ingested_at, datetime)
    assert doc.warnings == []


def test_default_document_id_is_generated_and_unique(settings: Settings) -> None:
    data = f.make_digital_pdf()
    a = ingest_bytes(data, "r.pdf", settings=settings, ocr=f.FakeOCR())
    b = ingest_bytes(data, "r.pdf", settings=settings, ocr=f.FakeOCR())
    assert re.fullmatch(r"DOC-[0-9A-F]{12}", a.document_id)
    assert a.document_id != b.document_id
    assert a.sha256 == b.sha256  # same content, same hash


def test_ingest_file_reads_from_disk(tmp_path: Path, settings: Settings) -> None:
    path = tmp_path / "report.pdf"
    path.write_bytes(f.make_digital_pdf())
    doc = ingest_file(path, settings=settings, ocr=f.FakeOCR())
    assert doc.filename == "report.pdf" and doc.page_count == 1


def test_ingest_file_missing_path(tmp_path: Path, settings: Settings) -> None:
    with pytest.raises(FileNotFoundError):
        ingest_file(tmp_path / "nope.pdf", settings=settings)


def test_ingestion_logs_metadata_but_never_text_or_filename(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        ingest_bytes(
            f.make_digital_pdf(), "jane-doe-report.pdf", settings=settings, ocr=f.FakeOCR()
        )
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "Ingested document_id=" in logged
    for forbidden in ("Hemoglobin", "P001", "13.2", "jane-doe"):
        assert forbidden not in logged


# ------------------------------------------------------------------ scanned / mixed
def test_scanned_pdf_falls_back_to_ocr(settings: Settings) -> None:
    ocr = f.FakeOCR(lines=["Hemoglobin  13.2  g/dL  12.0 - 16.0"], confidence=88.0)
    doc = ingest_bytes(f.make_scanned_pdf(), "scan.pdf", settings=settings, ocr=ocr)

    assert doc.source_type is SourceType.SCANNED_PDF
    page = doc.pages[0]
    assert page.method is ExtractionMethod.OCR
    assert page.ocr_confidence == 88.0
    assert page.ocr_dpi == 300
    assert page.coordinate_unit == "px"
    assert page.width > 2400  # A4 rendered at 300 dpi
    assert ocr.recognize_calls == 1
    assert ocr.last_image_size == (int(page.width), int(page.height))
    assert page.clean_text == "Hemoglobin  13.2  g/dL  12.0 - 16.0"


def test_ocr_dpi_setting_controls_render_resolution() -> None:
    settings = Settings(_env_file=None, ocr_dpi=150)
    page = ingest_bytes(f.make_scanned_pdf(), "s.pdf", settings=settings, ocr=f.FakeOCR()).pages[0]
    assert page.ocr_dpi == 150 and 1200 < page.width < 1300


def test_scanned_pdf_without_ocr_raises_actionable_error(settings: Settings) -> None:
    with pytest.raises(OCRUnavailableError):
        ingest_bytes(
            f.make_scanned_pdf(), "s.pdf", settings=settings, ocr=f.FakeOCR(available=False)
        )


def test_mixed_pdf_per_page_methods_and_blank_page(settings: Settings) -> None:
    ocr = f.FakeOCR()
    doc = ingest_bytes(f.make_mixed_pdf(), "mixed.pdf", settings=settings, ocr=ocr)
    assert doc.source_type is SourceType.MIXED_PDF
    assert [p.method for p in doc.pages] == [
        ExtractionMethod.PDF_TEXT,
        ExtractionMethod.OCR,
        ExtractionMethod.PDF_TEXT,
    ]
    assert ocr.recognize_calls == 1  # blank page 3 is not OCR'd
    blank = doc.pages[2]
    assert blank.clean_text == "" and blank.lines == []
    assert any("blank" in w for w in blank.warnings)


def test_all_blank_pdf_is_ingested_with_warnings_and_no_ocr(settings: Settings) -> None:
    ocr = f.FakeOCR(available=False)
    doc = ingest_bytes(f.make_blank_pdf(pages=2), "blank.pdf", settings=settings, ocr=ocr)
    assert doc.source_type is SourceType.DIGITAL_PDF
    assert all("blank" in p.warnings[0] for p in doc.pages)


def test_low_ocr_confidence_is_flagged(settings: Settings) -> None:
    ocr = f.FakeOCR(confidence=40.0)
    page = ingest_bytes(f.make_scanned_pdf(), "s.pdf", settings=settings, ocr=ocr).pages[0]
    assert any("Low mean OCR confidence" in w for w in page.warnings)


def test_good_ocr_confidence_has_no_warning(settings: Settings) -> None:
    page = ingest_bytes(f.make_scanned_pdf(), "s.pdf", settings=settings, ocr=f.FakeOCR()).pages[0]
    assert page.warnings == []


def test_ocr_that_finds_nothing_is_flagged(settings: Settings) -> None:
    page = ingest_bytes(
        f.make_scanned_pdf(), "s.pdf", settings=settings, ocr=f.FakeOCR(lines=[])
    ).pages[0]
    assert page.clean_text == "" and page.ocr_confidence is None
    assert any("no text" in w for w in page.warnings)


def test_short_text_page_without_images_keeps_text_layer(settings: Settings) -> None:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "See next page", fontsize=12)
    ocr = f.FakeOCR(available=False)
    page = ingest_bytes(doc.tobytes(), "short.pdf", settings=settings, ocr=ocr).pages[0]
    assert page.clean_text == "See next page"
    assert page.method is ExtractionMethod.PDF_TEXT
    assert any("very little text" in w for w in page.warnings)


# ------------------------------------------------------------------ garbled layers
def test_looks_garbled() -> None:
    assert looks_garbled("\ufffd\ufffd\ufffd a")
    assert looks_garbled("\ue001\ue002\ue003\ue004 x")
    assert not looks_garbled("Hemoglobin 13.2 g/dL")
    assert not looks_garbled("")


# ------------------------------------------------------------------ errors
def test_corrupt_pdf_raises(settings: Settings) -> None:
    with pytest.raises(CorruptFileError):
        ingest_bytes(b"%PDF-1.4\nthis is not really a pdf", "bad.pdf", settings=settings)


def test_encrypted_pdf_raises(settings: Settings) -> None:
    with pytest.raises(EncryptedPDFError):
        ingest_bytes(f.make_encrypted_pdf(), "locked.pdf", settings=settings, ocr=f.FakeOCR())


def test_page_limit_enforced() -> None:
    settings = Settings(_env_file=None, ingestion_max_pdf_pages=2)
    with pytest.raises(TooManyPagesError):
        ingest_bytes(f.make_digital_pdf(pages=3), "long.pdf", settings=settings, ocr=f.FakeOCR())
