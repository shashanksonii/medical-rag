"""End-to-end: real ingestion (PyMuPDF / fake OCR) followed by structured extraction."""

from __future__ import annotations

from datetime import date

from app.extraction import ValidationStatus, extract_observations
from app.ingestion import ingest_bytes
from tests import factories as f

TODAY = date(2026, 11, 15)


def test_digital_pdf_to_observations(settings):
    doc = ingest_bytes(
        f.make_digital_pdf(), "report.pdf", patient_id="P001", settings=settings, ocr=f.FakeOCR()
    )
    result = extract_observations(doc, today=TODAY)

    assert [o.test_name_normalized for o in result.observations] == [
        "hemoglobin",
        "wbc",
        "glucose",
        "creatinine",
    ]
    assert all(o.validation_status is ValidationStatus.VALID for o in result.observations)
    assert result.observation_date == date(2026, 8, 12)
    assert result.report_patient_ids == ["P001"]
    hb = result.observations[0]
    assert (hb.value, hb.normalized_unit, hb.reference_low, hb.reference_high) == (
        13.2,
        "g/dL",
        12.0,
        16.0,
    )
    assert hb.extraction_method == "pdf_text"


def test_image_with_fake_ocr_to_observations(settings):
    ocr = f.FakeOCR(
        lines=[
            "Patient ID: P001",
            "Report Date: 12/08/2026",
            "Hemoglobin  13.2  g/dL  12.0 - 16.0",
        ]
    )
    image = f.png_bytes(f.render_report_image())
    doc = ingest_bytes(image, "scan.png", patient_id="P001", settings=settings, ocr=ocr)
    result = extract_observations(doc, today=TODAY)

    assert len(result.observations) == 1
    obs = result.observations[0]
    assert obs.test_name_normalized == "hemoglobin" and obs.value == 13.2
    assert obs.extraction_method == "ocr" and obs.ocr_confidence == 92.0
    assert obs.validation_status is ValidationStatus.VALID
