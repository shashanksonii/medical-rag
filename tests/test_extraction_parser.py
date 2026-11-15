"""Unit tests for app.extraction.parser and app.extraction.normalizer."""

from __future__ import annotations

from datetime import date

import pytest

from app.extraction.normalizer import normalize_test_name, normalize_unit
from app.extraction.parser import (
    find_dates,
    find_patient_ids,
    parse_date,
    parse_range,
    parse_result_line,
    parse_value,
)
from app.extraction.schemas import DateSource


# ------------------------------------------------------------------ normaliser
@pytest.mark.parametrize("name", ["Hb", "Haemoglobin", "Hemoglobin", "HGB", "hemoglobin:"])
def test_hemoglobin_aliases(name):
    assert normalize_test_name(name) == "hemoglobin"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("SGPT (ALT)", "alt"),
        ("S. Creatinine", "creatinine"),
        ("Fasting Blood Sugar", "glucose_fasting"),
        ("25-OH Vitamin D", "vitamin_d"),
        ("TLC", "wbc"),
        ("Something Unknown", None),
    ],
)
def test_other_names(name, expected):
    assert normalize_test_name(name) == expected


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        ("g/dl", "g/dL"),
        ("gm%", "g/dL"),
        ("10^3/uL", "10^3/µL"),
        ("10³/µL", "10^3/µL"),
        ("x10^3/ul", "10^3/µL"),
        ("/cumm", "/µL"),
        ("µIU/mL", "µIU/mL"),
        ("uIU/ml", "µIU/mL"),
        ("furlongs", None),
        (None, None),
    ],
)
def test_units(unit, expected):
    assert normalize_unit(unit) == expected


# ------------------------------------------------------------------ values
def test_plain_decimal():
    v = parse_value("13.2")
    assert (v.value, v.operator, v.flag) == (13.2, None, None)


def test_operator_is_kept_not_dropped():
    v = parse_value("<5")
    assert v.value == 5 and v.operator == "<"
    assert parse_value("≥ 10").operator == ">="


def test_printed_high_low_flag():
    assert parse_value("105 H").flag == "H"
    assert parse_value("11.4 L").flag == "L"


def test_indian_thousands_grouping():
    assert parse_value("1,50,000").value == 150000


def test_negative_value():
    assert parse_value("-2.5").value == -2.5


def test_text_result():
    v = parse_value("Non Reactive")
    assert v.value is None and v.text == "Non Reactive"


def test_unreadable_value():
    assert parse_value("thirteen") is None


# ------------------------------------------------------------------ reference ranges
@pytest.mark.parametrize(
    ("text", "low", "high"),
    [
        ("12.0 - 16.0", 12.0, 16.0),
        ("12.0–16.0", 12.0, 16.0),
        ("(70-99)", 70, 99),
        ("< 200", None, 200),
        ("Up to 6.0", None, 6.0),
        ("> 40", 40, None),
    ],
)
def test_ranges(text, low, high):
    r = parse_range(text)
    assert (r.low, r.high) == (low, high)


def test_range_with_unit():
    r = parse_range("12.0 - 16.0 g/dL")
    assert (r.low, r.high, r.unit) == (12.0, 16.0, "g/dL")


def test_not_a_range():
    assert parse_range("g/dL") is None


# ------------------------------------------------------------------ whole lines
def test_table_row():
    row = parse_result_line("Hemoglobin  13.2  g/dL  12.0 - 16.0").row
    assert (row.name, row.value.value, row.unit) == ("Hemoglobin", 13.2, "g/dL")
    assert (row.range.low, row.range.high) == (12.0, 16.0)


def test_table_row_without_range():
    row = parse_result_line("Random Blood Sugar  180  mg/dL").row
    assert row.range is None and row.unit == "mg/dL"


def test_single_line_format():
    row = parse_result_line("Hemoglobin: 13.2 g/dL (12.0 - 16.0)").row
    assert (row.value.value, row.unit, row.range.low, row.range.high) == (13.2, "g/dL", 12, 16)


def test_single_line_unit_with_digits():
    row = parse_result_line("WBC Count 7.5 10^3/uL 4.0 - 11.0").row
    assert row.unit == "10^3/uL" and (row.range.low, row.range.high) == (4.0, 11.0)


def test_single_line_text_result():
    row = parse_result_line("HBsAg Non Reactive").row
    assert row.name == "HBsAg" and row.value.text == "Non Reactive"


def test_value_and_unit_in_one_cell():
    row = parse_result_line("Hemoglobin  13.2 g/dL  12.0 - 16.0").row
    assert row.value.value == 13.2 and row.unit == "g/dL"


@pytest.mark.parametrize(
    "line",
    [
        "SYNTHETIC LABORATORY REPORT",
        "Patient ID: P001",
        "Report Date: 12/08/2026",
        "Test  Result  Unit  Reference Range",
        "Page 1 of 2",
        "Age  45  Years",
        "",
    ],
)
def test_non_result_lines_are_ignored(line):
    assert parse_result_line(line) is None


def test_known_test_with_unreadable_value_is_reported():
    result = parse_result_line("Hemoglobin  thirteen  g/dL")
    assert result is not None and result.row is None and result.unparsed_reason


# ------------------------------------------------------------------ dates and IDs
def test_find_dates_with_labels():
    found = find_dates("Collection Date: 10-Aug-2026   Report Date: 12/08/2026")
    assert [(source, text) for _, source, text in found] == [
        (DateSource.COLLECTION, "10-Aug-2026"),
        (DateSource.REPORT, "12/08/2026"),
    ]


def test_date_of_birth_is_not_an_observation_date():
    assert find_dates("Date of Birth: 01/01/1980") == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("12/08/2026", date(2026, 8, 12)),  # DMY by default (Indian convention)
        ("12-08-2026", date(2026, 8, 12)),
        ("2026-01-15", date(2026, 1, 15)),
        ("05-Mar-2026", date(2026, 3, 5)),
        ("March 5, 2026", date(2026, 3, 5)),
        ("12/08/26", date(2026, 8, 12)),
        ("31/02/2026", None),  # impossible date -> None, never a guess
        ("08/13/2026", None),  # month 13 in DMY -> None, not silently swapped
    ],
)
def test_parse_date(text, expected):
    assert parse_date(text) == expected


def test_parse_date_mdy_option():
    assert parse_date("08/13/2026", date_order="MDY") == date(2026, 8, 13)


def test_patient_id():
    assert find_patient_ids("Patient ID: P001") == ["P001"]
