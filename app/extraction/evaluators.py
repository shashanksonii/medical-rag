"""Extraction evaluation against hand-written ground truth.

For each document we know the correct observations ("expected"). We compare them
with what ``extract_observations`` produced ("extracted"):

* Matching is by standard test name. A matched pair is a true positive (TP).
* Extracted with no expected partner -> false positive (FP).
* Expected with no extracted partner -> false negative (FN).
* precision = TP / (TP + FP), recall = TP / (TP + FN), F1 = harmonic mean.
* For TPs we also check: numeric value (+ operator / text), unit, reference range.
* Date accuracy is per document: was the chosen observation date correct?

Plain Python only; scikit-learn arrives with the research evaluation milestone.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

from app.extraction.schemas import ExtractionResult, Observation


class ExpectedObservation(BaseModel):
    test_name_normalized: str
    value: float | None = None
    value_operator: str | None = None
    value_text: str | None = None
    normalized_unit: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None


class ExpectedDocument(BaseModel):
    file: str = Field(description="Path relative to the ground-truth file's folder")
    patient_id: str
    observation_date: date | None = None
    observations: list[ExpectedObservation]
    note: str = ""


class DocumentScore(BaseModel):
    file: str
    source_type: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    value_correct: int = 0
    unit_correct: int = 0
    range_correct: int = 0
    date_correct: bool = False
    errors: list[str] = Field(default_factory=list)


def load_ground_truth(path: str | Path) -> list[ExpectedDocument]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [ExpectedDocument.model_validate(item) for item in data["documents"]]


def _close(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is b
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def _value_ok(got: Observation, exp: ExpectedObservation) -> bool:
    if exp.value_text is not None:
        return (got.value_text or "").lower() == exp.value_text.lower()
    return _close(got.value, exp.value) and got.value_operator == exp.value_operator


def evaluate_document(result: ExtractionResult, expected: ExpectedDocument) -> DocumentScore:
    score = DocumentScore(file=expected.file, source_type=result.source_type)
    unmatched = list(result.observations)
    for exp in expected.observations:
        match = next(
            (o for o in unmatched if o.test_name_normalized == exp.test_name_normalized), None
        )
        if match is None:
            score.fn += 1
            score.errors.append(f"missed {exp.test_name_normalized}")
            continue
        unmatched.remove(match)
        score.tp += 1
        if _value_ok(match, exp):
            score.value_correct += 1
        else:
            score.errors.append(
                f"{exp.test_name_normalized}: value {match.value_operator or ''}"
                f"{match.value if match.value is not None else match.value_text} "
                f"!= expected {exp.value_operator or ''}"
                f"{exp.value if exp.value is not None else exp.value_text}"
            )
        if match.normalized_unit == exp.normalized_unit:
            score.unit_correct += 1
        else:
            score.errors.append(
                f"{exp.test_name_normalized}: unit {match.normalized_unit!r} "
                f"!= expected {exp.normalized_unit!r}"
            )
        if _close(match.reference_low, exp.reference_low) and _close(
            match.reference_high, exp.reference_high
        ):
            score.range_correct += 1
        else:
            score.errors.append(
                f"{exp.test_name_normalized}: range {match.reference_low}-"
                f"{match.reference_high} != expected {exp.reference_low}-{exp.reference_high}"
            )
    for extra in unmatched:
        score.fp += 1
        score.errors.append(f"extra {extra.test_name_original!r}")
    score.date_correct = result.observation_date == expected.observation_date
    if not score.date_correct:
        score.errors.append(
            f"date {result.observation_date} != expected {expected.observation_date}"
        )
    return score


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def summarize(scores: list[DocumentScore]) -> dict:
    """Overall metrics (key 'all') plus one block per source type (digital_pdf, image...)."""
    groups: dict[str, list[DocumentScore]] = {"all": scores}
    for s in scores:
        groups.setdefault(s.source_type, []).append(s)

    summary: dict[str, dict] = {}
    for name, group in groups.items():
        tp = sum(s.tp for s in group)
        fp = sum(s.fp for s in group)
        fn = sum(s.fn for s in group)
        precision = _ratio(tp, tp + fp)
        recall = _ratio(tp, tp + fn)
        f1 = (
            round(2 * precision * recall / (precision + recall), 4)
            if precision and recall
            else None
        )
        summary[name] = {
            "documents": len(group),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "numeric_accuracy": _ratio(sum(s.value_correct for s in group), tp),
            "unit_accuracy": _ratio(sum(s.unit_correct for s in group), tp),
            "range_accuracy": _ratio(sum(s.range_correct for s in group), tp),
            "date_accuracy": _ratio(sum(s.date_correct for s in group), len(group)),
        }
    return summary
