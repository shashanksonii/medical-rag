"""Document ingestion service: the single entry point used by the rest of the app.

    from app.ingestion import ingest_file
    doc = ingest_file("report.pdf", patient_id="P001")

Milestone 2 stops at raw/clean text with provenance. Parsing medical values is
Milestone 3.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import Settings, get_settings
from app.ingestion.errors import (
    EmptyFileError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.ingestion.layout import words_to_lines
from app.ingestion.ocr import OCRBackend, get_default_ocr, load_image
from app.ingestion.pdf_extractor import LOW_OCR_CONFIDENCE, extract_pdf_pages
from app.ingestion.preprocessing import finalize_lines
from app.ingestion.schemas import (
    ExtractionMethod,
    FileType,
    IngestedDocument,
    PageText,
    SourceType,
)

logger = logging.getLogger(__name__)

_EXPECTED_EXTENSIONS = {
    FileType.PDF: {".pdf"},
    FileType.PNG: {".png"},
    FileType.JPEG: {".jpg", ".jpeg"},
}
SUPPORTED_DESCRIPTION = "PDF, JPG/JPEG or PNG"


def detect_file_type(data: bytes) -> FileType:
    """Identify the file from its content (never trust the extension alone)."""
    if b"%PDF-" in data[:1024]:
        return FileType.PDF
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return FileType.PNG
    if data.startswith(b"\xff\xd8\xff"):
        return FileType.JPEG
    if data[128:132] == b"DICM":
        raise UnsupportedFileTypeError(
            "DICOM files are not supported (medical image interpretation is out of project scope)."
        )
    raise UnsupportedFileTypeError(
        f"Unsupported file type. Supported types: {SUPPORTED_DESCRIPTION}."
    )


def _safe_filename(filename: str) -> str:
    """Keep only the final path component (handles both / and \\)."""
    return re.split(r"[\\/]", filename)[-1] or "unnamed"


def _source_type(file_type: FileType, pages: list[PageText]) -> SourceType:
    if file_type is not FileType.PDF:
        return SourceType.IMAGE
    methods = {p.method for p in pages}
    if methods == {ExtractionMethod.PDF_TEXT}:
        return SourceType.DIGITAL_PDF
    if methods == {ExtractionMethod.OCR}:
        return SourceType.SCANNED_PDF
    return SourceType.MIXED_PDF


def _ocr_image_page(data: bytes, ocr: OCRBackend) -> PageText:
    image = load_image(data)
    ocr.ensure_available()
    result = ocr.recognize(image)
    raw, clean, lines = finalize_lines(words_to_lines(result.words))
    warnings: list[str] = []
    if not lines:
        warnings.append("OCR found no text in this image.")
    elif result.mean_confidence is not None and result.mean_confidence < LOW_OCR_CONFIDENCE:
        warnings.append(
            f"Low mean OCR confidence ({result.mean_confidence:.0f}/100); "
            "numeric values need manual verification."
        )
    return PageText(
        page_number=1,
        method=ExtractionMethod.OCR,
        raw_text=raw,
        clean_text=clean,
        lines=lines,
        coordinate_unit="px",
        width=float(image.width),
        height=float(image.height),
        ocr_confidence=result.mean_confidence,
        warnings=warnings,
    )


def ingest_bytes(
    data: bytes,
    filename: str,
    *,
    patient_id: str | None = None,
    document_id: str | None = None,
    settings: Settings | None = None,
    ocr: OCRBackend | None = None,
) -> IngestedDocument:
    """Ingest a PDF/JPG/PNG held in memory.

    ``ocr`` can be injected (tests); by default Tesseract is used, and only
    when a page or image actually needs it - digital PDFs work without
    Tesseract installed.
    """
    settings = settings or get_settings()
    if not data:
        raise EmptyFileError("The file is empty.")
    max_bytes = settings.ingestion_max_file_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise FileTooLargeError(
            f"The file is {len(data) / 1024 / 1024:.1f} MB; "
            f"the limit is {settings.ingestion_max_file_mb} MB."
        )

    file_type = detect_file_type(data)
    name = _safe_filename(filename)
    warnings: list[str] = []
    suffix = Path(name).suffix.lower()
    if suffix and suffix not in _EXPECTED_EXTENSIONS[file_type]:
        warnings.append(
            f"File extension '{suffix}' does not match the detected content type "
            f"'{file_type.value}'; the content type was used."
        )

    engine = ocr if ocr is not None else get_default_ocr(settings)
    if file_type is FileType.PDF:
        pages = extract_pdf_pages(data, settings, engine)
    else:
        pages = [_ocr_image_page(data, engine)]

    document = IngestedDocument(
        document_id=document_id or f"DOC-{uuid.uuid4().hex[:12].upper()}",
        patient_id=patient_id,
        filename=name,
        file_type=file_type,
        source_type=_source_type(file_type, pages),
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        page_count=len(pages),
        pages=pages,
        ingested_at=datetime.now(timezone.utc),
        warnings=warnings,
    )
    # Log metadata only - never filenames or text, which may identify a patient.
    logger.info(
        "Ingested document_id=%s type=%s source=%s pages=%d ocr_pages=%d",
        document.document_id,
        document.file_type.value,
        document.source_type.value,
        document.page_count,
        sum(p.method is ExtractionMethod.OCR for p in pages),
    )
    return document


def ingest_file(
    path: str | Path,
    *,
    patient_id: str | None = None,
    document_id: str | None = None,
    settings: Settings | None = None,
    ocr: OCRBackend | None = None,
) -> IngestedDocument:
    """Ingest a file from disk. Raises ``FileNotFoundError`` if it does not exist."""
    settings = settings or get_settings()
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"No such file: {file_path}")
    if file_path.stat().st_size > settings.ingestion_max_file_mb * 1024 * 1024:
        raise FileTooLargeError(f"The file exceeds the {settings.ingestion_max_file_mb} MB limit.")
    return ingest_bytes(
        file_path.read_bytes(),
        file_path.name,
        patient_id=patient_id,
        document_id=document_id,
        settings=settings,
        ocr=ocr,
    )
