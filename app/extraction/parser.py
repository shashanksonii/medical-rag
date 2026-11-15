"""Turn report text lines into parsed rows, dates and patient IDs.

Two line formats are supported:

1. Table rows from ingestion, where two or more spaces separate the columns::

       Hemoglobin  13.2  g/dL  12.0 - 16.0
       Glucose  105 H  mg/dL  70 - 99

2. Single-line results (common after OCR, which may lose column gaps)::

       Hemoglobin: 13.2 g/dL (12.0 - 16.0)
       HbA1c 6.1 %

Nothing here guesses. A value that cannot be read is reported as unparsed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.extraction.normalizer import looks_like_unit, normalize_test_name, normalize_unit
from app.extraction.schemas import DateSource

# ------------------------------------------------------------------ numbers and values
# 1,50,000 (Indian grouping), 150,000 or plain 13.2 / -2 / .5
_NUMBER = r"[-+]?(?:\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)"
_OPERATOR = r"<=|>=|≤|≥|<|>"
_VALUE_RE = re.compile(
    rf"^(?P<op>{_OPERATOR})?\s*(?P<num>{_NUMBER})\s*(?P<flag>H|L|High|Low|HIGH|LOW)?\s*\*?$"
)
TEXT_RESULTS = {
    "positive",
    "negative",
    "reactive",
    "non reactive",
    "nonreactive",
    "non-reactive",
    "nil",
    "absent",
    "present",
    "trace",
    "detected",
    "not detected",
    "normal",
}
_OP_MAP = {"≤": "<=", "≥": ">="}


@dataclass
class ParsedValue:
    raw: str
    value: float | None = None
    operator: str | None = None
    text: str | None = None
    flag: str | None = None


def parse_number(text: str) -> float:
    """'1,50,000' -> 150000.0, '13.2' -> 13.2 (commas are only thousands separators)."""
    return float(text.replace(",", ""))


def parse_value(cell: str) -> ParsedValue | None:
    """Parse a result cell such as '13.2', '<5', '105 H' or 'Negative'."""
    cell = cell.strip()
    m = _VALUE_RE.match(cell)
    if m:
        flag = m.group("flag")
        op = m.group("op")
        return ParsedValue(
            raw=cell,
            value=parse_number(m.group("num")),
            operator=_OP_MAP.get(op, op) if op else None,
            flag=flag[0].upper() if flag else None,
        )
    if cell.lower() in TEXT_RESULTS:
        return ParsedValue(raw=cell, text=cell)
    return None


# ------------------------------------------------------------------ reference ranges
_DASH = r"\s*(?:-|–|—|to)\s*"
_RANGE_BETWEEN = re.compile(rf"^(?P<low>{_NUMBER}){_DASH}(?P<high>{_NUMBER})\s*(?P<unit>\S+)?$")
_RANGE_UPPER = re.compile(
    rf"^(?:(?P<op><=|≤|<)|up\s*to|upto)\s*(?P<high>{_NUMBER})\s*(?P<unit>\S+)?$", re.I
)
_RANGE_LOWER = re.compile(rf"^(?:>=|≥|>)\s*(?P<low>{_NUMBER})\s*(?P<unit>\S+)?$")


@dataclass
class ParsedRange:
    text: str
    low: float | None = None
    high: float | None = None
    unit: str | None = None


def parse_range(cell: str) -> ParsedRange | None:
    """Parse '12.0 - 16.0', '12.0–16.0', '< 200', 'Up to 5', '> 40' (with optional unit).

    One-sided ranges fill only ``low`` or only ``high``. Nothing is ever filled in from
    "standard" ranges: if the report has no range, there is no range.
    """
    cell = cell.strip().strip("()[]").strip()
    for regex, sides in (
        (_RANGE_BETWEEN, ("low", "high")),
        (_RANGE_UPPER, ("high",)),
        (_RANGE_LOWER, ("low",)),
    ):
        m = regex.match(cell)
        if m:
            unit = m.group("unit")
            if unit and not looks_like_unit(unit):
                return None
            parsed = ParsedRange(text=cell, unit=unit)
            for side in sides:
                setattr(parsed, side, parse_number(m.group(side)))
            return parsed
    return None


# ------------------------------------------------------------------ result rows
# Lines that are labels or table headers, never results.
_SKIP_NAMES = {
    "test",
    "test name",
    "tests",
    "investigation",
    "investigations",
    "parameter",
    "parameters",
    "test description",
    "age",
    "sex",
    "gender",
    "age sex",
    "name",
    "patient name",
    "patient id",
    "patient",
    "page",
    "date",
    "report date",
    "lab no",
    "sample id",
    "uhid",
    "ref by",
    "referred by",
    "mobile",
    "phone",
}
_INLINE_RE = re.compile(
    rf"^(?P<name>(?=[^:]*[A-Za-z])[A-Za-z0-9][A-Za-z0-9 .()/'+-]*?)\s*:?\s+"
    rf"(?P<value>(?:{_OPERATOR})?\s*{_NUMBER}(?:\s+(?:H|L))?)(?=\s|$)\s*(?P<rest>.*)$"
)


@dataclass
class ParsedRow:
    name: str
    value: ParsedValue
    unit: str | None = None
    range: ParsedRange | None = None
    notes: list[str] = field(default_factory=list)  # parser-level flags


@dataclass
class LineParse:
    row: ParsedRow | None = None
    unparsed_reason: str | None = None


def _clean_name(name: str) -> str:
    return name.strip().rstrip(":").strip()


def _is_label(name: str) -> bool:
    key = re.sub(r"[^a-z]+", " ", name.lower()).strip()
    return key in _SKIP_NAMES


def _parse_table_row(cells: list[str]) -> LineParse:
    name = _clean_name(cells[0])
    rest = cells[1:]
    value = parse_value(rest[0])
    if value is None:
        # value and unit stuck in one cell: "13.2 g/dL"
        m = re.match(r"^(.*?\S)\s+(\S+)$", rest[0])
        if m and parse_value(m.group(1)) and looks_like_unit(m.group(2)):
            value = parse_value(m.group(1))
            rest = [m.group(1), m.group(2), *rest[1:]]
    if value is None:
        return LineParse(unparsed_reason="value_not_readable")

    row = ParsedRow(name=name, value=value)
    for cell in rest[1:]:
        if row.range is None and (parsed_range := parse_range(cell)):
            row.range = parsed_range
        elif row.unit is None and looks_like_unit(cell):
            row.unit = cell.strip()
        elif cell.strip() in {"H", "L"} and row.value.flag is None:
            row.value.flag = cell.strip()
        else:
            row.notes.append("unexpected_column")
    return LineParse(row=row)


def _parse_inline(line: str) -> LineParse:
    m = _INLINE_RE.match(line)
    if not m:
        # Text result on one line: "HBsAg Non Reactive", "Urine Glucose: Negative"
        for text in sorted(TEXT_RESULTS, key=len, reverse=True):
            tm = re.match(rf"^(?P<name>.+?)\s*:?\s+(?P<val>{re.escape(text)})$", line, re.I)
            if tm and normalize_test_name(tm.group("name")):
                value = ParsedValue(raw=tm.group("val"), text=tm.group("val"))
                return LineParse(row=ParsedRow(name=_clean_name(tm.group("name")), value=value))
        return LineParse(unparsed_reason="no_result_pattern")
    value = parse_value(m.group("value"))
    if value is None:
        return LineParse(unparsed_reason="value_not_readable")
    row = ParsedRow(name=_clean_name(m.group("name")), value=value)
    tokens = m.group("rest").split()
    # Try every split "unit part | range part": 'g/dL (12.0 - 16.0)', '10^3/uL 4.0 - 11.0', '%'
    for i in range(len(tokens) + 1):
        unit_part = " ".join(tokens[:i]).strip("()[] ")
        range_part = " ".join(tokens[i:])
        parsed_range = parse_range(range_part) if range_part else None
        if (not range_part or parsed_range) and (not unit_part or looks_like_unit(unit_part)):
            row.unit = unit_part or None
            row.range = parsed_range
            break
    else:
        row.notes.append("unexpected_text")
    return LineParse(row=row)


def _is_header_or_label_line(line: str, first_cell: str) -> bool:
    if _is_label(_clean_name(first_cell)):
        return True
    # "Report Date: 12/08/2026", "Patient ID: P001" ...
    looks_like_label = re.match(r"^\s*[\w .]+:\s*\S", first_cell) is not None
    return looks_like_label and bool(find_dates(line) or find_patient_ids(line))


def _is_plausible_row(row: ParsedRow) -> bool:
    """A row must name a known test, or carry a unit or a reference range."""
    return bool(normalize_test_name(row.name) or row.unit or row.range)


def parse_result_line(line: str) -> LineParse | None:
    """Parse one line. Returns ``None`` for lines that are clearly not results."""
    line = line.strip()
    if not line or not re.search(r"[A-Za-z]", line):
        return None
    cells = [c for c in re.split(r"\s{2,}", line) if c.strip()]
    if _is_header_or_label_line(line, cells[0]):
        return None

    if len(cells) >= 2:
        result = _parse_table_row(cells)
        if result.row is not None and _is_plausible_row(result.row):
            return result

    result = _parse_inline(line)
    if result.row is None:
        # Report as unparsed only if it starts with a known test name and has more after it.
        name_guess = re.split(r"\s{2,}|[:\d<>]", line, maxsplit=1)[0]
        has_more = len(cells) >= 2 or re.search(r"\d", line)
        if has_more and normalize_test_name(name_guess):
            return result
        return None
    # Single-line mode is looser, so accept only recognised tests or recognised units.
    # This stops lines such as "Page 1 of 2" from becoming observations.
    row = result.row
    if normalize_test_name(row.name) is None and normalize_unit(row.unit) is None:
        return None
    return result


# ------------------------------------------------------------------ dates
_MONTHS = {
    m: i
    for i, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for m in names
}
_MONTH_RE = r"[A-Za-z]{3,9}"
_DATE_TEXT = (
    rf"\d{{4}}-\d{{1,2}}-\d{{1,2}}"
    rf"|\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}"
    rf"|\d{{1,2}}[ -]{_MONTH_RE}[ ,-]+\d{{2,4}}"
    rf"|{_MONTH_RE} \d{{1,2}},? \d{{4}}"
)
# Order matters: more specific labels first.
_DATE_LABELS: list[tuple[str, DateSource]] = [
    (r"sample\s+collect(?:ed|ion)(?:\s+(?:date|on|at))?", DateSource.COLLECTION),
    (r"collect(?:ed|ion)\s+(?:date|on|at)", DateSource.COLLECTION),
    (r"collected", DateSource.COLLECTION),
    (r"report(?:ed)?\s+(?:date|on)", DateSource.REPORT),
    (r"date\s+of\s+report", DateSource.REPORT),
    (r"reported", DateSource.REPORT),
    (r"regist(?:ered|ration)\s*(?:date|on)?", DateSource.OTHER),
    (r"received\s*(?:date|on)?", DateSource.OTHER),
    (r"date", DateSource.OTHER),
]
_LABELLED_DATE_RE = re.compile(
    r"\b(?P<label>"
    + "|".join(f"(?:{pattern})" for pattern, _ in _DATE_LABELS)
    + rf")\s*[:\-]?\s*(?P<date>{_DATE_TEXT})",
    re.I,
)


def _year(text: str) -> int:
    year = int(text)
    if len(text) == 2:
        year += 2000  # two-digit years are assumed to be 20xx
    return year


def parse_date(text: str, date_order: str = "DMY") -> date | None:
    """Parse a date. Numeric dates use ``date_order`` ('DMY' Indian default, or 'MDY').

    Returns ``None`` for impossible dates (for example 31/02/2026 or a 13th month)
    instead of trying another order - a guess could put a result in the wrong month.
    """
    text = text.strip()
    try:
        if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", text):
            first, second = int(m[1]), int(m[2])
            day, month = (first, second) if date_order == "DMY" else (second, first)
            return date(_year(m[3]), month, day)
        if m := re.fullmatch(rf"(\d{{1,2}})[ -]({_MONTH_RE})[ ,-]+(\d{{2,4}})", text):
            month = _MONTHS.get(m[2].lower())
            return date(_year(m[3]), month, int(m[1])) if month else None
        if m := re.fullmatch(rf"({_MONTH_RE}) (\d{{1,2}}),? (\d{{4}})", text):
            month = _MONTHS.get(m[1].lower())
            return date(int(m[3]), month, int(m[2])) if month else None
    except ValueError:
        return None
    return None


def _label_source(label: str) -> DateSource:
    for pattern, source in _DATE_LABELS:
        if re.fullmatch(pattern, label.strip(), re.I):
            return source
    return DateSource.OTHER


def find_dates(line: str) -> list[tuple[str, DateSource, str]]:
    """Return ``(label, source, date_text)`` for every labelled date in a line."""
    return [
        (m.group("label"), _label_source(m.group("label")), m.group("date"))
        for m in _LABELLED_DATE_RE.finditer(line)
    ]


# ------------------------------------------------------------------ patient IDs
_PATIENT_ID_RE = re.compile(
    r"\b(?:patient\s*id|patient\s*no|pid|uhid)\s*[:.\-]?\s*(?P<id>[A-Za-z0-9][A-Za-z0-9-]*)",
    re.I,
)


def find_patient_ids(line: str) -> list[str]:
    return [m.group("id") for m in _PATIENT_ID_RE.finditer(line)]
