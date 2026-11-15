"""Text cleanup applied after extraction.

Principles (important for medical data):
* Never change digits, decimal points/commas, signs, comparison operators,
  slashes, percent signs, dates or unit symbols (including ``µ``).
* Never "correct" OCR output - a guessed correction could silently alter a lab
  value. Low-confidence OCR is flagged instead (see the ingestion service).
* Keep horizontal gaps: two or more spaces become exactly two spaces, which
  Milestone 3 can treat as a table-column boundary.
* Keep ZWJ/ZWNJ (U+200C/U+200D): they are meaningful in Devanagari text.
"""

from __future__ import annotations

import re
import unicodedata

from app.ingestion.layout import COLUMN_SEPARATOR, LayoutLine
from app.ingestion.schemas import TextLine

# Characters that carry no visible content and only disturb parsing.
_REMOVE = dict.fromkeys(map(ord, "\u200b\u2060\ufeff\u00ad"), None)
# Exotic spaces -> plain space.
_TO_SPACE = {
    ord(c): " "
    for c in (
        "\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006"
        "\u2007\u2008\u2009\u200a\u202f\u205f\u3000"
    )
}
_LINE_BREAKS = re.compile(r"\r\n|\r|\u2028|\u2029|\x0b|\x0c|\x85")
_SPACE_RUN = re.compile(r"[ \t]+")


def _is_unwanted_control(ch: str) -> bool:
    return unicodedata.category(ch) == "Cc" and ch not in "\n\t"


def clean_line(line: str) -> str:
    """Clean a single line (no newline characters expected)."""
    line = line.translate(_REMOVE).translate(_TO_SPACE)
    line = "".join(ch for ch in line if not _is_unwanted_control(ch))
    line = unicodedata.normalize("NFC", line)
    line = _SPACE_RUN.sub(lambda m: COLUMN_SEPARATOR if len(m.group()) >= 2 else " ", line)
    return line.strip()


def clean_text(text: str) -> str:
    """Clean multi-line text: normalise line breaks, clean each line, collapse blank runs."""
    lines = [clean_line(part) for part in _LINE_BREAKS.sub("\n", text).split("\n")]
    out: list[str] = []
    for line in lines:
        if line == "" and (not out or out[-1] == ""):
            continue
        out.append(line)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def finalize_lines(layout_lines: list[LayoutLine]) -> tuple[str, str, list[TextLine]]:
    """Return ``(raw_text, clean_text, lines)`` for a page from its layout rows.

    Rows that are empty after cleaning are dropped; line numbers refer to the
    cleaned lines, so ``clean_text.splitlines()[n - 1]`` is line ``n``.
    """
    raw_text = "\n".join(line.text for line in layout_lines)
    lines: list[TextLine] = []
    for layout_line in layout_lines:
        cleaned = clean_line(layout_line.text)
        if cleaned:
            lines.append(TextLine(line_number=len(lines) + 1, text=cleaned, bbox=layout_line.bbox))
    return raw_text, "\n".join(line.text for line in lines), lines
