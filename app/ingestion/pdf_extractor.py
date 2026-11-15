"""PDF extraction: native text layer first, OCR fallback per page."""

from __future__ import annotations

import logging
import math

import pymupdf
from PIL import Image

from app.core.config import Settings
from app.ingestion.errors import (
    CorruptFileError,
    EncryptedPDFError,
    IngestionError,
    OCRProcessingError,
    TooManyPagesError,
)
from app.ingestion.layout import Word, words_to_lines
from app.ingestion.ocr import OCRBackend
from app.ingestion.preprocessing import finalize_lines
from app.ingestion.schemas import ExtractionMethod, PageText

logger = logging.getLogger(__name__)

LOW_OCR_CONFIDENCE = 60.0
MAX_RENDER_PIXELS = 50_000_000  # protects memory on oversized pages (A4@300dpi is ~8.7M)
_GARBLED_RATIO = 0.2


def looks_garbled(text: str) -> bool:
    """True when a text layer is mostly replacement/private-use characters.

    Happens with broken font encodings; such a layer is worse than none, so the
    page is OCR'd instead.
    """
    visible = [ch for ch in text if not ch.isspace()]
    if not visible:
        return False
    bad = sum(1 for ch in visible if ch == "\ufffd" or "\ue000" <= ch <= "\uf8ff")
    return bad / len(visible) >= _GARBLED_RATIO


def _alnum_count(text: str) -> int:
    return sum(ch.isalnum() for ch in text)


def _render_page(page: pymupdf.Page, dpi: int) -> tuple[Image.Image, int]:
    rect = page.rect
    pixels = (rect.width / 72 * dpi) * (rect.height / 72 * dpi)
    if pixels > MAX_RENDER_PIXELS:
        dpi = max(72, int(dpi * math.sqrt(MAX_RENDER_PIXELS / pixels)))
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples), dpi


def _native_page(page: pymupdf.Page, page_number: int, warnings: list[str]) -> PageText:
    words = [Word(w[4], w[0], w[1], w[2], w[3]) for w in page.get_text("words")]
    raw, clean, lines = finalize_lines(words_to_lines(words))
    return PageText(
        page_number=page_number,
        method=ExtractionMethod.PDF_TEXT,
        raw_text=raw,
        clean_text=clean,
        lines=lines,
        coordinate_unit="pt",
        width=float(page.rect.width),
        height=float(page.rect.height),
        warnings=warnings,
    )


def _ocr_page(
    page: pymupdf.Page, page_number: int, settings: Settings, ocr: OCRBackend
) -> PageText:
    ocr.ensure_available()  # fail with an actionable message before rendering
    image, dpi = _render_page(page, settings.ocr_dpi)
    result = ocr.recognize(image)
    raw, clean, lines = finalize_lines(words_to_lines(result.words))

    warnings: list[str] = []
    if dpi != settings.ocr_dpi:
        warnings.append(f"Page is very large; rendered at {dpi} dpi instead of {settings.ocr_dpi}.")
    if not lines:
        warnings.append("OCR found no text on this page.")
    elif result.mean_confidence is not None and result.mean_confidence < LOW_OCR_CONFIDENCE:
        warnings.append(
            f"Low mean OCR confidence ({result.mean_confidence:.0f}/100); "
            "numeric values on this page need manual verification."
        )
    return PageText(
        page_number=page_number,
        method=ExtractionMethod.OCR,
        raw_text=raw,
        clean_text=clean,
        lines=lines,
        coordinate_unit="px",
        width=float(image.width),
        height=float(image.height),
        ocr_confidence=result.mean_confidence,
        ocr_dpi=dpi,
        warnings=warnings,
    )


def extract_pdf_pages(data: bytes, settings: Settings, ocr: OCRBackend) -> list[PageText]:
    """Extract every page of a PDF, using OCR only for pages without usable text."""
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # pymupdf raises FileDataError/RuntimeError/ValueError
        raise CorruptFileError("The PDF is corrupt or cannot be opened.") from exc

    with doc:
        if doc.needs_pass:
            raise EncryptedPDFError(
                "The PDF is password-protected; password-protected files are not supported."
            )
        if doc.page_count == 0:
            raise CorruptFileError("The PDF contains no pages.")
        if doc.page_count > settings.ingestion_max_pdf_pages:
            raise TooManyPagesError(
                f"The PDF has {doc.page_count} pages; "
                f"the limit is {settings.ingestion_max_pdf_pages}."
            )

        pages: list[PageText] = []
        for index in range(doc.page_count):
            page_number = index + 1
            try:
                pages.append(_extract_one(doc.load_page(index), page_number, settings, ocr))
            except IngestionError:
                raise
            except (RuntimeError, ValueError) as exc:
                raise CorruptFileError(f"Page {page_number} of the PDF could not be read.") from exc
        return pages


def _extract_one(
    page: pymupdf.Page, page_number: int, settings: Settings, ocr: OCRBackend
) -> PageText:
    native = _native_page(page, page_number, [])
    alnum = _alnum_count(native.clean_text)
    low_text = alnum < settings.pdf_min_text_chars or looks_garbled(native.raw_text)
    if not low_text:
        return native

    has_visual = bool(page.get_images()) or bool(page.get_drawings())
    if has_visual:
        try:
            return _ocr_page(page, page_number, settings, ocr)
        except OCRProcessingError:
            raise
    if alnum == 0:
        native.warnings.append("Page has no text, images or graphics; treated as blank.")
    else:
        native.warnings.append(
            f"Page has very little text ({alnum} characters) and no images; kept the text layer."
        )
    return native
