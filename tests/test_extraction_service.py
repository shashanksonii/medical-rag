"""Tests for extract_observations (service + validator) on text-only documents."""

from __future__ import annotations

from datetime import date

from app.extraction import ValidationStatus, extract_observations
from app.extraction import validator as v
from app.extraction.schemas import DateSource
from app.ingestion.schemas import ExtractionMethod
from tests.extraction_helpers import SAMPLE_LINES, make_doc

TODAY = date(2026, 11, 15)


def _by_name(result):
    return {o.test_name_normalized: o for o in result.observations}


def test_sample_report_gives_four_valid_observations():
    result = extract_observations(make_doc(SAMPLE_LINES), today=TODAY)
    assert len(result.observations) == 4
    assert all(o.validation_status is ValidationStatus.VALID for o in result.observations)
    hb = _by_name(result)["hemoglobin"]
    assert hb.value == 13.2
    assert hb.normalized_unit == "g/dL"
    assert (hb.reference_low, hb.reference_high) == (12.0, 16.0)
    assert hb.observation_date == date(2026, 8, 12)
    assert hb.date_source is DateSource.REPORT
    assert hb.patient_id == "P001" and hb.document_id == "DOC-TEST"
    assert hb.source_page == 1 and hb.source_line_number == 5
    assert hb.evidence_snippet == "Hemoglobin  13.2  g/dL  12.0 - 16.0"


def test_observation_ids_are_stable():
    first = extract_observations(make_doc(SAMPLE_LINES), today=TODAY)
    second = extract_observations(make_doc(SAMPLE_LINES), today=TODAY)
    assert [o.observation_id for o in first.observations] == [
        o.observation_id for o in second.observations
    ]
    assert len({o.observation_id for o in first.observations}) == 4


def test_collection_date_beats_report_date():
    lines = ["Collection Date: 10/08/2026", "Report Date: 12/08/2026", SAMPLE_LINES[4]]
    result = extract_observations(make_doc(lines), today=TODAY)
    assert result.observation_date == date(2026, 8, 10)
    assert result.date_source is DateSource.COLLECTION


def test_conflicting_dates_are_flagged_not_guessed():
    lines = ["Date: 01/02/2026", "Date: 03/02/2026", SAMPLE_LINES[4]]
    result = extract_observations(make_doc(lines), today=TODAY)
    obs = result.observations[0]
    assert obs.observation_date is None
    assert v.AMBIGUOUS_DATE in obs.flags
    assert obs.validation_status is ValidationStatus.NEEDS_REVIEW


def test_missing_date_is_flagged():
    result = extract_observations(make_doc([SAMPLE_LINES[4]]), today=TODAY)
    assert v.MISSING_DATE in result.observations[0].flags


def test_future_date_is_flagged():
    lines = ["Report Date: 12/08/2030", SAMPLE_LINES[4]]
    result = extract_observations(make_doc(lines), today=TODAY)
    assert v.FUTURE_DATE in result.observations[0].flags


def test_missing_range_stays_missing():
    lines = ["Report Date: 12/08/2026", "Random Blood Sugar  180  mg/dL"]
    obs = extract_observations(make_doc(lines), today=TODAY).observations[0]
    assert obs.reference_low is None and obs.reference_high is None
    assert obs.validation_status is ValidationStatus.VALID


def test_less_than_value_keeps_operator():
    lines = ["Report Date: 12/08/2026", "CRP  <5  mg/L  0 - 5"]
    obs = extract_observations(make_doc(lines), today=TODAY).observations[0]
    assert (obs.value, obs.value_operator, obs.value_raw) == (5.0, "<", "<5")


def test_inverted_range_is_flagged():
    lines = ["Report Date: 12/08/2026", "Hemoglobin  13.2  g/dL  16.0 - 12.0"]
    obs = extract_observations(make_doc(lines), today=TODAY).observations[0]
    assert v.REFERENCE_RANGE_INVERTED in obs.flags


def test_unrecognised_test_and_unit_are_flagged():
    lines = ["Report Date: 12/08/2026", "Zorbium  4.2  zz/qq  1 - 5"]
    obs = extract_observations(make_doc(lines), today=TODAY).observations[0]
    assert obs.test_name_normalized is None
    assert v.UNRECOGNIZED_TEST in obs.flags and v.UNRECOGNIZED_UNIT in obs.flags


def test_missing_unit_is_flagged():
    lines = ["Report Date: 12/08/2026", "Hemoglobin  13.2  12.0 - 16.0"]
    obs = extract_observations(make_doc(lines), today=TODAY).observations[0]
    assert v.MISSING_UNIT in obs.flags


def test_lost_decimal_point_is_caught_as_implausible():
    lines = ["Report Date: 12/08/2026", "Hemoglobin  132  g/dL  12.0 - 16.0"]
    obs = extract_observations(make_doc(lines), today=TODAY).observations[0]
    assert v.IMPLAUSIBLE_VALUE in obs.flags


def test_ocr_misread_patient_id_is_flagged():
    lines = ["Patient ID: POO1", "Report Date: 12/08/2026", SAMPLE_LINES[4]]
    result = extract_observations(make_doc(lines, patient_id="P001"), today=TODAY)
    assert v.PATIENT_ID_MISMATCH in result.observations[0].flags
    assert result.report_patient_ids == ["POO1"]


def test_low_ocr_confidence_is_flagged():
    doc = make_doc(SAMPLE_LINES, method=ExtractionMethod.OCR, ocr_confidence=40.0)
    result = extract_observations(doc, today=TODAY)
    assert all(v.LOW_OCR_CONFIDENCE in o.flags for o in result.observations)
    assert result.observations[0].extraction_method == "ocr"


def test_duplicate_test_in_document_is_flagged():
    result = extract_observations(make_doc(SAMPLE_LINES, SAMPLE_LINES), today=TODAY)
    page_two = [o for o in result.observations if o.source_page == 2]
    assert page_two and all(v.DUPLICATE_IN_DOCUMENT in o.flags for o in page_two)


def test_evidence_must_be_in_source():
    result = extract_observations(make_doc(SAMPLE_LINES), today=TODAY)
    obs = result.observations[0].model_copy(update={"flags": []})
    v.validate_observation(obs, "completely different text", today=TODAY)
    assert v.EVIDENCE_NOT_IN_SOURCE in obs.flags
    assert obs.validation_status is ValidationStatus.INVALID


def test_value_mismatch_is_invalid():
    result = extract_observations(make_doc(SAMPLE_LINES), today=TODAY)
    obs = result.observations[0].model_copy(update={"flags": [], "value": 99.0})
    v.validate_observation(obs, "\n".join(SAMPLE_LINES), today=TODAY)
    assert v.VALUE_MISMATCH in obs.flags
    assert obs.validation_status is ValidationStatus.INVALID


def test_unparsed_known_test_is_recorded():
    lines = ["Report Date: 12/08/2026", "Hemoglobin  thirteen  g/dL"]
    result = extract_observations(make_doc(lines), today=TODAY)
    assert result.observations == []
    assert result.unparsed_lines[0].text == "Hemoglobin  thirteen  g/dL"


def test_result_serialises_to_json():
    result = extract_observations(make_doc(SAMPLE_LINES), today=TODAY)
    assert '"test_name_normalized":"hemoglobin"' in result.model_dump_json()
