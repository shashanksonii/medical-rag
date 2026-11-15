from __future__ import annotations

import pytest

from app.ingestion.layout import LayoutLine
from app.ingestion.preprocessing import clean_line, clean_text, finalize_lines

# Strings containing values/units/dates that cleaning must never alter.
MEDICAL_STRINGS = [
    "13.2 g/dL",
    "12.0 - 16.0",
    "12.0-16.0",
    "<5.0 mg/L",
    ">=100",
    "\u2265 18.5",
    "10^3/\u00b5L",
    "\u00d710\u00b3/\u00b5L",
    "12/08/2026",
    "2026-08-12",
    "98.6%",
    "-2.5",
    "1,234.5",
    "\u00b5g/dL",
    "pH 7.40",
    "HbA1c 6.1 %",
    "BP 120/80 mmHg",
]


@pytest.mark.parametrize("text", MEDICAL_STRINGS)
def test_values_dates_units_are_preserved(text: str) -> None:
    assert clean_line(text) == text
    assert clean_text(text) == text


def test_micro_sign_is_not_converted_to_greek_mu() -> None:
    assert clean_line("\u00b5g/dL") == "\u00b5g/dL"  # U+00B5 stays U+00B5


def test_exotic_spaces_become_plain_spaces() -> None:
    assert clean_line("Hemoglobin\u00a013.2\u2009g/dL") == "Hemoglobin 13.2 g/dL"


def test_invisible_characters_removed() -> None:
    assert clean_line("Hemo\u200bglo\u00adbin\ufeff 13.2") == "Hemoglobin 13.2"


def test_zwj_and_zwnj_kept_for_devanagari() -> None:
    text = "\u0915\u094d\u200d\u0937"
    assert clean_line(text) == text


def test_control_characters_removed_but_not_text() -> None:
    assert clean_line("Glucose\x00 105\x07 mg/dL") == "Glucose 105 mg/dL"


def test_single_tab_is_a_space_and_runs_become_column_gap() -> None:
    assert clean_line("Glucose\t105") == "Glucose 105"
    assert clean_line("Glucose      105 \t\t mg/dL") == "Glucose  105  mg/dL"


def test_leading_and_trailing_whitespace_stripped() -> None:
    assert clean_line("   Glucose  105   ") == "Glucose  105"


def test_unicode_is_nfc_normalised() -> None:
    assert clean_line("e\u0301") == "\u00e9"


def test_clean_text_normalises_line_breaks() -> None:
    assert clean_text("a\r\nb\rc\u2028d\x0ce") == "a\nb\nc\nd\ne"


def test_clean_text_collapses_blank_runs_and_trims() -> None:
    assert clean_text("\n\nA\n\n\n\nB\n\n") == "A\n\nB"


def test_clean_text_empty() -> None:
    assert clean_text("") == ""
    assert clean_text(" \n\t\n") == ""


def test_finalize_lines_keeps_raw_and_numbers_clean_lines() -> None:
    layout = [
        LayoutLine("Hemoglobin\u00a0 13.2", (0, 0, 10, 10)),
        LayoutLine("   ", (0, 12, 10, 22)),
        LayoutLine("Glucose  105", (0, 24, 10, 34)),
    ]
    raw, clean, lines = finalize_lines(layout)
    assert raw.splitlines()[0] == "Hemoglobin\u00a0 13.2"  # raw untouched
    assert clean == "Hemoglobin  13.2\nGlucose  105"
    assert [line.line_number for line in lines] == [1, 2]
    assert lines[1].bbox == (0, 24, 10, 34)
    assert clean.splitlines()[1] == lines[1].text
