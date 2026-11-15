"""Synthetic document factories and a fake OCR engine for tests and sample data.

Everything here is SYNTHETIC: obviously fake patient ID and made-up lab values.
No real patient data may ever be added to this repository.
"""

from __future__ import annotations

import io

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from app.ingestion.errors import OCRUnavailableError
from app.ingestion.layout import Word
from app.ingestion.ocr import OCRResult

HEADER_LINES = [
    "SYNTHETIC LABORATORY REPORT",
    "Patient ID: P001",
    "Report Date: 12/08/2026",
]
TABLE_HEADER = ("Test", "Result", "Unit", "Reference Range")
TABLE_ROWS = [
    ("Hemoglobin", "13.2", "g/dL", "12.0 - 16.0"),
    ("WBC Count", "7.5", "10^3/uL", "4.0 - 11.0"),
    ("Glucose", "105", "mg/dL", "70 - 99"),
    ("Creatinine", "0.9", "mg/dL", "0.6 - 1.2"),
]
COLUMN_X = (50, 230, 330, 440)  # PDF points
A4 = (595, 842)


# ------------------------------------------------------------------ digital PDFs
def _write_report_page(page: pymupdf.Page, rows=TABLE_ROWS, header=HEADER_LINES) -> None:
    y = 60.0
    for i, line in enumerate(header):
        page.insert_text((50, y), line, fontsize=14 if i == 0 else 11, fontname="helv")
        y += 22
    y += 20
    for cells in (TABLE_HEADER, *rows):
        for x, cell in zip(COLUMN_X, cells, strict=True):
            page.insert_text((x, y), cell, fontsize=11, fontname="helv")
        y += 22


def make_digital_pdf(pages: int = 1, rows=TABLE_ROWS) -> bytes:
    doc = pymupdf.open()
    for _ in range(pages):
        _write_report_page(doc.new_page(width=A4[0], height=A4[1]), rows)
    return doc.tobytes()


def make_blank_pdf(pages: int = 1) -> bytes:
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page(width=A4[0], height=A4[1])
    return doc.tobytes()


def make_encrypted_pdf() -> bytes:
    doc = pymupdf.open()
    _write_report_page(doc.new_page(width=A4[0], height=A4[1]))
    return doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner-secret"
    )


# ------------------------------------------------------------------ images / scans
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def render_report_image(
    rows=TABLE_ROWS, header=HEADER_LINES, size=(1240, 1754), font_size=36
) -> Image.Image:
    """Render the report as a clean 150-dpi A4 page image (no text layer)."""
    scale = size[0] / A4[0]
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    y = 60.0 * scale
    for i, line in enumerate(header):
        draw.text((50 * scale, y), line, fill="black", font=_font(font_size + (4 if i == 0 else 0)))
        y += 22 * scale * 1.4
    y += 20 * scale
    for cells in (TABLE_HEADER, *rows):
        for x, cell in zip(COLUMN_X, cells, strict=True):
            draw.text((x * scale, y), cell, fill="black", font=_font(font_size))
        y += 22 * scale * 1.4
    return image


def png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def jpeg_bytes(image: Image.Image, quality: int = 90) -> bytes:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def make_scanned_pdf(pages: int = 1) -> bytes:
    """PDF whose pages are only an embedded picture - no text layer."""
    doc = pymupdf.open()
    stream = png_bytes(render_report_image())
    for _ in range(pages):
        page = doc.new_page(width=A4[0], height=A4[1])
        page.insert_image(page.rect, stream=stream)
    return doc.tobytes(garbage=3, deflate=True)


def make_mixed_pdf() -> bytes:
    """Page 1 digital, page 2 scanned, page 3 blank."""
    doc = pymupdf.open()
    _write_report_page(doc.new_page(width=A4[0], height=A4[1]))
    scanned = doc.new_page(width=A4[0], height=A4[1])
    scanned.insert_image(scanned.rect, stream=png_bytes(render_report_image()))
    doc.new_page(width=A4[0], height=A4[1])
    return doc.tobytes(garbage=3, deflate=True)


# ------------------------------------------------------------------ fake OCR
def words_from_lines(lines: list[str], char_w: float = 14, height: float = 30) -> list[Word]:
    """Lay text out as positioned words (two+ spaces -> a visible column gap)."""
    words: list[Word] = []
    for row, line in enumerate(lines):
        y0 = 50 + row * 50.0
        x = 50.0
        for token in line.split(" "):
            if token == "":
                x += char_w
                continue
            width = char_w * len(token)
            words.append(Word(token, x, y0, x + width, y0 + height, 90.0))
            x += width + char_w
    return words


class FakeOCR:
    """Deterministic stand-in for Tesseract; counts how often it is used."""

    def __init__(
        self,
        lines: list[str] | None = None,
        confidence: float | None = 92.0,
        available: bool = True,
    ) -> None:
        self.lines = lines if lines is not None else ["Hemoglobin  13.2  g/dL  12.0 - 16.0"]
        self.confidence = confidence
        self.available = available
        self.recognize_calls = 0
        self.last_image_size: tuple[int, int] | None = None

    def ensure_available(self) -> None:
        if not self.available:
            raise OCRUnavailableError("Fake OCR is unavailable.")

    def recognize(self, image: Image.Image) -> OCRResult:
        self.ensure_available()
        self.recognize_calls += 1
        self.last_image_size = image.size
        words = words_from_lines(self.lines)
        return OCRResult(words=words, mean_confidence=self.confidence if words else None)
