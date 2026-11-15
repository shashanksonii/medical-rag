"""Validation: check every observation and record problems as flags.

Each check adds a flag code to ``Observation.flags``. The status is then:

* ``invalid``      - at least one SERIOUS flag (the value cannot be trusted at all)
* ``needs_review`` - other flags only (usable, but a person should look)
* ``valid``        - no flags

Validation never changes a value. It only reports.
"""

from __future__ import annotations

from datetime import date

from app.extraction.parser import parse_value
from app.extraction.schemas import Observation, ValidationStatus

# ------------------------------------------------------------------ flag codes
EVIDENCE_NOT_IN_SOURCE = "evidence_not_in_source"
VALUE_NOT_IN_EVIDENCE = "value_not_in_evidence"
VALUE_MISMATCH = "value_mismatch"
MISSING_VALUE = "missing_value"
MISSING_UNIT = "missing_unit"
UNRECOGNIZED_UNIT = "unrecognized_unit"
UNRECOGNIZED_TEST = "unrecognized_test"
REFERENCE_RANGE_INVERTED = "reference_range_inverted"
REFERENCE_UNIT_MISMATCH = "reference_unit_mismatch"
MISSING_DATE = "missing_date"
AMBIGUOUS_DATE = "ambiguous_date"
INVALID_DATE = "invalid_date"
FUTURE_DATE = "future_date"
IMPLAUSIBLE_VALUE = "implausible_value"
LOW_OCR_CONFIDENCE = "low_ocr_confidence"
PATIENT_ID_MISMATCH = "patient_id_mismatch"
DUPLICATE_IN_DOCUMENT = "duplicate_in_document"
UNEXPECTED_COLUMN = "unexpected_column"
UNEXPECTED_TEXT = "unexpected_text"

SERIOUS_FLAGS = {EVIDENCE_NOT_IN_SOURCE, VALUE_NOT_IN_EVIDENCE, VALUE_MISMATCH, MISSING_VALUE}

# Same threshold as ingestion (app.ingestion.pdf_extractor.LOW_OCR_CONFIDENCE).
OCR_CONFIDENCE_THRESHOLD = 60.0

# Very wide "is this physically possible?" limits, used ONLY to catch reading errors
# such as a lost decimal point (13.2 read as 132). They are NOT clinical reference
# ranges and must never be shown as normal/abnormal.
PLAUSIBLE_LIMITS: dict[tuple[str, str], tuple[float, float]] = {
    ("hemoglobin", "g/dL"): (1, 25),
    ("hematocrit", "%"): (5, 80),
    ("wbc", "10^3/µL"): (0.1, 500),
    ("wbc", "/µL"): (100, 500_000),
    ("rbc", "10^6/µL"): (0.5, 10),
    ("platelets", "10^3/µL"): (1, 2_000),
    ("platelets", "/µL"): (1_000, 2_000_000),
    ("glucose", "mg/dL"): (10, 2_000),
    ("glucose_fasting", "mg/dL"): (10, 2_000),
    ("glucose_random", "mg/dL"): (10, 2_000),
    ("hba1c", "%"): (2, 25),
    ("creatinine", "mg/dL"): (0.05, 30),
    ("urea", "mg/dL"): (1, 500),
    ("cholesterol_total", "mg/dL"): (20, 1_500),
    ("hdl", "mg/dL"): (2, 300),
    ("ldl", "mg/dL"): (2, 1_000),
    ("triglycerides", "mg/dL"): (5, 10_000),
    ("sodium", "mmol/L"): (90, 200),
    ("sodium", "mEq/L"): (90, 200),
    ("potassium", "mmol/L"): (1, 12),
    ("potassium", "mEq/L"): (1, 12),
    ("tsh", "µIU/mL"): (0.001, 500),
}


def _numbers_equal(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def validate_observation(
    obs: Observation, page_text: str, *, today: date | None = None
) -> Observation:
    """Add flags to ``obs`` (in place) and set its ``validation_status``. Returns ``obs``."""
    today = today or date.today()
    flags = obs.flags

    def add(flag: str) -> None:
        if flag not in flags:
            flags.append(flag)

    # 1. The evidence must really be in the extracted page text.
    if obs.evidence_snippet not in page_text:
        add(EVIDENCE_NOT_IN_SOURCE)

    # 2. The value must be present in the evidence, and re-parse to the same number.
    if obs.value is None and obs.value_text is None:
        add(MISSING_VALUE)
    if obs.value_raw not in obs.evidence_snippet:
        add(VALUE_NOT_IN_EVIDENCE)
    elif obs.value is not None:
        reparsed = parse_value(obs.value_raw)
        if reparsed is None or reparsed.value is None:
            add(VALUE_MISMATCH)
        elif not _numbers_equal(reparsed.value, obs.value):
            add(VALUE_MISMATCH)

    # 3. Unit.
    if obs.value is not None and not obs.unit:
        add(MISSING_UNIT)
    elif obs.unit and obs.normalized_unit is None:
        add(UNRECOGNIZED_UNIT)

    # 4. Test name.
    if obs.test_name_normalized is None:
        add(UNRECOGNIZED_TEST)

    # 5. Reference range.
    if (
        obs.reference_low is not None
        and obs.reference_high is not None
        and obs.reference_low > obs.reference_high
    ):
        add(REFERENCE_RANGE_INVERTED)

    # 6. Date.
    if obs.observation_date is not None:
        if obs.observation_date > today:
            add(FUTURE_DATE)
        elif obs.observation_date.year < 1900:
            add(INVALID_DATE)
    elif not any(f in flags for f in (AMBIGUOUS_DATE, INVALID_DATE)):
        add(MISSING_DATE)

    # 7. Plausibility (catches reading errors, not a medical judgement).
    if obs.value is not None and obs.test_name_normalized and obs.normalized_unit:
        limits = PLAUSIBLE_LIMITS.get((obs.test_name_normalized, obs.normalized_unit))
        if limits and not (limits[0] <= obs.value <= limits[1]):
            add(IMPLAUSIBLE_VALUE)

    # 8. OCR quality.
    if obs.ocr_confidence is not None and obs.ocr_confidence < OCR_CONFIDENCE_THRESHOLD:
        add(LOW_OCR_CONFIDENCE)

    if any(f in SERIOUS_FLAGS for f in flags):
        obs.validation_status = ValidationStatus.INVALID
    elif flags:
        obs.validation_status = ValidationStatus.NEEDS_REVIEW
    else:
        obs.validation_status = ValidationStatus.VALID
    return obs
