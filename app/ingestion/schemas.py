"""Data models produced by document ingestion.

These are the stable hand-off to Milestone 3 (structured extraction): every
piece of text keeps its document ID, page number, extraction method and (for
OCR) confidence, so any later extracted value can be traced back to its source.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

BBox = tuple[float, float, float, float]  # (x0, y0, x1, y1)


class FileType(str, Enum):
    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"


class SourceType(str, Enum):
    DIGITAL_PDF = "digital_pdf"  # every page had a usable text layer
    SCANNED_PDF = "scanned_pdf"  # every page needed OCR
    MIXED_PDF = "mixed_pdf"  # some pages text layer, some OCR
    IMAGE = "image"  # JPG/PNG, always OCR


class ExtractionMethod(str, Enum):
    PDF_TEXT = "pdf_text"  # PyMuPDF native text layer
    OCR = "ocr"  # Tesseract


class TextLine(BaseModel):
    """One visual row of text with its position on the page.

    ``bbox`` is in the page's ``coordinate_unit`` (PDF points for native text,
    pixels of the OCR input image for OCR).
    """

    line_number: int = Field(ge=1)
    text: str
    bbox: BBox


class PageText(BaseModel):
    """Extracted text and provenance for a single page (images have one page)."""

    page_number: int = Field(ge=1, description="1-based page number in the source file")
    method: ExtractionMethod
    # Text as reconstructed from the engine's words, before character cleanup.
    raw_text: str
    # Cleaned text (see app.ingestion.preprocessing). Numbers, decimals, dates,
    # units and column gaps are preserved. Milestone 3 should parse this.
    clean_text: str
    lines: list[TextLine]
    coordinate_unit: Literal["pt", "px"]
    width: float
    height: float
    ocr_confidence: float | None = Field(
        default=None, ge=0, le=100, description="Mean Tesseract word confidence (OCR pages only)"
    )
    ocr_dpi: int | None = Field(default=None, description="Render DPI for OCR'd PDF pages")
    warnings: list[str] = Field(default_factory=list)


class IngestedDocument(BaseModel):
    """Result of ingesting one file."""

    document_id: str
    patient_id: str | None = None
    filename: str
    file_type: FileType
    source_type: SourceType
    sha256: str
    size_bytes: int
    page_count: int
    pages: list[PageText]
    ingested_at: datetime
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _page_count_matches(self) -> IngestedDocument:
        if self.page_count != len(self.pages):
            raise ValueError("page_count must equal len(pages)")
        return self

    @property
    def clean_text(self) -> str:
        """All pages' cleaned text, separated by a blank line (no page markers)."""
        return "\n\n".join(p.clean_text for p in self.pages)
