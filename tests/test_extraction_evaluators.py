"""Tests for the extraction evaluation metrics."""

from __future__ import annotations

from datetime import date

from app.extraction import extract_observations
from app.extraction.evaluators import (
    ExpectedDocument,
    ExpectedObservation,
    evaluate_document,
    summarize,
)
from tests.extraction_helpers import SAMPLE_LINES, make_doc

TODAY = date(2026, 11, 15)


def _expected(**overrides) -> ExpectedDocument:
    data = {
        "file": "sample.pdf",
        "patient_id": "P001",
        "observation_date": date(2026, 8, 12),
        "observations": [
            ExpectedObservation(
                test_name_normalized="hemoglobin",
                value=13.2,
                normalized_unit="g/dL",
                reference_low=12.0,
                reference_high=16.0,
            ),
            ExpectedObservation(
                test_name_normalized="wbc",
                value=7.5,
                normalized_unit="10^3/µL",
                reference_low=4.0,
                reference_high=11.0,
            ),
            ExpectedObservation(
                test_name_normalized="glucose",
                value=105,
                normalized_unit="mg/dL",
                reference_low=70,
                reference_high=99,
            ),
            ExpectedObservation(
                test_name_normalized="creatinine",
                value=0.9,
                normalized_unit="mg/dL",
                reference_low=0.6,
                reference_high=1.2,
            ),
        ],
    }
    data.update(overrides)
    return ExpectedDocument(**data)


def test_perfect_extraction_scores_one():
    result = extract_observations(make_doc(SAMPLE_LINES), today=TODAY)
    score = evaluate_document(result, _expected())
    assert (score.tp, score.fp, score.fn) == (4, 0, 0)
    assert score.date_correct and score.errors == []
    overall = summarize([score])["all"]
    assert overall["precision"] == overall["recall"] == overall["f1"] == 1.0
    assert overall["numeric_accuracy"] == overall["unit_accuracy"] == 1.0


def test_missed_and_wrong_values_are_counted():
    lines = [*SAMPLE_LINES[:4], "Hemoglobin  13.5  g/dL  12.0 - 16.0", "Zorbium  1  mg/dL  0 - 2"]
    result = extract_observations(make_doc(lines), today=TODAY)
    score = evaluate_document(result, _expected())
    assert (score.tp, score.fp, score.fn) == (1, 1, 3)
    assert score.value_correct == 0
    summary = summarize([score])["all"]
    assert summary["precision"] == 0.5 and summary["recall"] == 0.25


def test_summary_is_grouped_by_source_type():
    result = extract_observations(make_doc(SAMPLE_LINES), today=TODAY)
    summary = summarize([evaluate_document(result, _expected())])
    assert set(summary) == {"all", "digital_pdf"}
