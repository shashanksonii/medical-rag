"""Rebuild visual text rows from positioned words.

Both PyMuPDF (digital PDFs) and Tesseract (OCR) can give us words with
bounding boxes. Native "text" output of PDF libraries often splits table cells
onto separate lines (``Hemoglobin`` / ``13.2`` / ``g/dL``), which destroys the
row relationship a lab table encodes. Grouping words by vertical position
keeps each table row on one line, and a wider gap between neighbouring words
is emitted as a two-space "column gap" so cells stay distinguishable.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import NamedTuple

from app.ingestion.schemas import BBox

# A word joins the current row if its vertical centre is within this fraction
# of the row height from the row centre.
ROW_TOLERANCE = 0.5
# A horizontal gap larger than this multiple of the row's median word height is
# treated as a column boundary (normal inter-word gaps are about 0.25-0.4).
COLUMN_GAP_FACTOR = 0.8
COLUMN_SEPARATOR = "  "


class Word(NamedTuple):
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float | None = None


@dataclass(frozen=True)
class LayoutLine:
    text: str
    bbox: BBox


def _yc(w: Word) -> float:
    return (w.y0 + w.y1) / 2


def words_to_lines(words: list[Word]) -> list[LayoutLine]:
    """Group words into top-to-bottom rows, each ordered left-to-right."""
    usable = [w for w in words if w.text.strip()]
    if not usable:
        return []

    rows: list[list[Word]] = []
    row_centres: list[float] = []
    for w in sorted(usable, key=lambda w: (_yc(w), w.x0)):
        if rows:
            heights = [m.y1 - m.y0 for m in rows[-1]]
            row_h = max(statistics.median(heights), w.y1 - w.y0)
            if abs(_yc(w) - row_centres[-1]) <= ROW_TOLERANCE * row_h:
                rows[-1].append(w)
                row_centres[-1] = statistics.fmean(_yc(m) for m in rows[-1])
                continue
        rows.append([w])
        row_centres.append(_yc(w))

    lines: list[LayoutLine] = []
    for row in rows:
        row.sort(key=lambda w: w.x0)
        ref_h = statistics.median(w.y1 - w.y0 for w in row) or 1.0
        parts = [row[0].text]
        for prev, cur in zip(row, row[1:], strict=False):
            gap = cur.x0 - prev.x1
            parts.append(COLUMN_SEPARATOR if gap > COLUMN_GAP_FACTOR * ref_h else " ")
            parts.append(cur.text)
        bbox = (
            min(w.x0 for w in row),
            min(w.y0 for w in row),
            max(w.x1 for w in row),
            max(w.y1 for w in row),
        )
        lines.append(LayoutLine(text="".join(parts), bbox=bbox))
    return lines
