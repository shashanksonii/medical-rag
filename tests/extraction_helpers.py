"""Build ``IngestedDocument`` objects from plain text lines (no PDF/OCR needed)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.ingestion.schemas import (
    ExtractionMethod,
    FileType,
    IngestedDocument,
    PageText,
    SourceType,
    TextLine,
)


def make_page(
    lines: list[str],
    page_number: int = 1,
    method: ExtractionMethod = ExtractionMethod.PDF_TEXT,
    ocr_confidence: float | None = None,
) -> PageText:
    text_lines = [
        TextLine(line_number=i, text=text, bbox=(50.0, 20.0 * i, 500.0, 20.0 * i + 12))
        for i, text in enumerate(lines, start=1)
    ]
    text = "\n".join(lines)
    return PageText(
        page_number=page_number,
        method=method,
        raw_text=text,
        clean_text=text,
        lines=text_lines,
        coordinate_unit="pt" if method is ExtractionMethod.PDF_TEXT else "px",
        width=595,
        height=842,
        ocr_confidence=ocr_confidence,
    )


def make_doc(
    *pages_lines: list[str],
    patient_id: str | None = "P001",
    method: ExtractionMethod = ExtractionMethod.PDF_TEXT,
    ocr_confidence: float | None = None,
    document_id: str = "DOC-TEST",
) -> IngestedDocument:
    pages = [
        make_page(lines, i, method, ocr_confidence) for i, lines in enumerate(pages_lines, start=1)
    ]
    return IngestedDocument(
        document_id=document_id,
        patient_id=patient_id,
        filename="synthetic.pdf",
        file_type=FileType.PDF,
        source_type=(
            SourceType.DIGITAL_PDF
            if method is ExtractionMethod.PDF_TEXT
            else SourceType.SCANNED_PDF
        ),
        sha256="0" * 64,
        size_bytes=1000,
        page_count=len(pages),
        pages=pages,
        ingested_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
    )


SAMPLE_LINES = [
    "SYNTHETIC LABORATORY REPORT",
    "Patient ID: P001",
    "Report Date: 12/08/2026",
    "Test  Result  Unit  Reference Range",
    "Hemoglobin  13.2  g/dL  12.0 - 16.0",
    "WBC Count  7.5  10^3/uL  4.0 - 11.0",
    "Glucose  105  mg/dL  70 - 99",
    "Creatinine  0.9  mg/dL  0.6 - 1.2",
]
