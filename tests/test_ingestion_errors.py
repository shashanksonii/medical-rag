from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.ingestion import (
    EmptyFileError,
    FileTooLargeError,
    IngestionError,
    OCRLanguageError,
    OCRUnavailableError,
    UnsupportedFileTypeError,
    errors,
    ingest_bytes,
    ingest_file,
)
from app.ingestion.service import detect_file_type
from tests import factories as f

SETTINGS = Settings(_env_file=None, environment="testing")


def test_empty_file() -> None:
    with pytest.raises(EmptyFileError):
        ingest_bytes(b"", "empty.pdf", settings=SETTINGS)


@pytest.mark.parametrize(
    "data",
    [
        b"just some plain text",
        b"PK\x03\x04 pretend this is a docx",
        b"GIF89a....",
        b"%!PS-Adobe-3.0",
        b"<html><body>report</body></html>",
        b"II*\x00 tiff-ish",
    ],
)
def test_unsupported_types_rejected(data: bytes) -> None:
    with pytest.raises(UnsupportedFileTypeError):
        ingest_bytes(data, "report.bin", settings=SETTINGS)


def test_dicom_rejected_with_specific_message() -> None:
    with pytest.raises(UnsupportedFileTypeError, match="DICOM"):
        detect_file_type(bytes(128) + b"DICM" + b"\x00" * 50)


def test_size_limit_applies_before_parsing() -> None:
    settings = Settings(_env_file=None, ingestion_max_file_mb=1)
    with pytest.raises(FileTooLargeError):
        ingest_bytes(b"%PDF-" + b"0" * (2 * 1024 * 1024), "big.pdf", settings=settings)


def test_size_limit_checked_from_disk_without_reading(tmp_path: Path) -> None:
    path = tmp_path / "big.pdf"
    path.write_bytes(b"%PDF-" + b"0" * (2 * 1024 * 1024))
    with pytest.raises(FileTooLargeError):
        ingest_file(path, settings=Settings(_env_file=None, ingestion_max_file_mb=1))


def test_error_hierarchy_and_unique_codes() -> None:
    classes = [
        c
        for c in vars(errors).values()
        if isinstance(c, type) and issubclass(c, IngestionError) and c is not IngestionError
    ]
    assert len(classes) == 9
    assert len({c.code for c in classes}) == len(classes)
    assert issubclass(OCRLanguageError, OCRUnavailableError)


def test_error_messages_never_contain_document_content() -> None:
    try:
        ingest_bytes(b"%PDF-1.4\nSECRET-PATIENT-TEXT Hemoglobin 13.2", "x.pdf", settings=SETTINGS)
    except IngestionError as exc:
        assert "SECRET-PATIENT-TEXT" not in exc.message
    else:  # pragma: no cover
        pytest.fail("expected an IngestionError")


def test_pdf_signature_inside_first_kb_is_accepted_as_pdf() -> None:
    # Some producers prepend a few junk bytes before %PDF-.
    data = b"\xef\xbb\xbf junk " + f.make_digital_pdf()
    doc = ingest_bytes(data, "r.pdf", settings=SETTINGS, ocr=f.FakeOCR())
    assert doc.page_count == 1
