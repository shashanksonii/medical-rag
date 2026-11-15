"""Structured extraction service: the single entry point for Milestone 3.

from app.ingestion import ingest_file
from app.extraction import extract_observations

doc = ingest_file("report.pdf", patient_id="P001")
result = extract_observations(doc)
for obs in result.observations:
    print(obs.test_name_normalized, obs.value, obs.unit, obs.validation_status)
"""

from __future__ import annotations

import hashlib
from datetime import date

from app.extraction import validator as v
from app.extraction.normalizer import normalize_test_name, normalize_unit
from app.extraction.parser import (
    find_dates,
    find_patient_ids,
    parse_date,
    parse_result_line,
)
from app.extraction.schemas import (
    DateSource,
    ExtractionResult,
    FoundDate,
    Observation,
    UnparsedLine,
)
from app.ingestion.schemas import IngestedDocument, PageText

# Which date wins when a report shows several (lower number = preferred).
_DATE_PRIORITY = {DateSource.COLLECTION: 0, DateSource.REPORT: 1, DateSource.OTHER: 2}


def _page_lines(page: PageText) -> list[tuple[int, str]]:
    if page.lines:
        return [(line.line_number, line.text) for line in page.lines]
    return list(enumerate(page.clean_text.splitlines(), start=1))


def _observation_id(document_id: str, page: int, line: int) -> str:
    digest = hashlib.sha256(f"{document_id}:{page}:{line}".encode()).hexdigest()
    return f"OBS-{digest[:16]}"


def choose_observation_date(found: list[FoundDate]) -> tuple[date | None, DateSource, list[str]]:
    """Pick the document's observation date. Returns ``(date, source, flags)``.

    Collection date beats report date, which beats any other labelled date. If the
    best label group contains two different dates, the result is ambiguous and no
    date is chosen - we flag it rather than guess.
    """
    if not found:
        return None, DateSource.NOT_FOUND, []
    best = min(_DATE_PRIORITY[d.source] for d in found)
    group = [d for d in found if _DATE_PRIORITY[d.source] == best]
    valid = {d.parsed for d in group if d.parsed is not None}
    if len(valid) > 1:
        return None, DateSource.AMBIGUOUS, [v.AMBIGUOUS_DATE]
    if not valid:
        return None, DateSource.NOT_FOUND, [v.INVALID_DATE]
    return valid.pop(), group[0].source, []


def extract_observations(
    doc: IngestedDocument, *, date_order: str = "DMY", today: date | None = None
) -> ExtractionResult:
    """Convert an ingested document into validated observations.

    ``date_order`` decides how numeric dates are read: 'DMY' (12/08/2026 = 12 August,
    the Indian convention and the project default) or 'MDY'.
    """
    if date_order not in {"DMY", "MDY"}:
        raise ValueError("date_order must be 'DMY' or 'MDY'")

    result = ExtractionResult(
        document_id=doc.document_id,
        patient_id=doc.patient_id,
        filename=doc.filename,
        source_type=doc.source_type.value,
    )

    # Pass 1: document-level facts (dates and printed patient IDs).
    for page in doc.pages:
        for line_number, text in _page_lines(page):
            for label, source, date_text in find_dates(text):
                result.dates_found.append(
                    FoundDate(
                        label=label,
                        source=source,
                        text=date_text,
                        parsed=parse_date(date_text, date_order),
                        page_number=page.page_number,
                        line_number=line_number,
                    )
                )
            for pid in find_patient_ids(text):
                if pid not in result.report_patient_ids:
                    result.report_patient_ids.append(pid)

    obs_date, date_source, date_flags = choose_observation_date(result.dates_found)
    result.observation_date, result.date_source = obs_date, date_source
    if date_flags:
        result.warnings.append(f"Observation date problem: {', '.join(date_flags)}")

    doc_flags = list(date_flags)
    if doc.patient_id is None:
        result.warnings.append("No patient_id was supplied at ingestion.")
    elif result.report_patient_ids and doc.patient_id not in result.report_patient_ids:
        doc_flags.append(v.PATIENT_ID_MISMATCH)
        result.warnings.append(
            "Patient ID printed on the report does not match the supplied patient_id."
        )

    # Pass 2: result rows.
    seen_tests: set[str] = set()
    for page in doc.pages:
        for line_number, text in _page_lines(page):
            parsed = parse_result_line(text)
            if parsed is None:
                continue
            if parsed.row is None:
                result.unparsed_lines.append(
                    UnparsedLine(
                        page_number=page.page_number,
                        line_number=line_number,
                        text=text,
                        reason=parsed.unparsed_reason or "unknown",
                    )
                )
                continue

            row = parsed.row
            unit = row.unit
            flags = list(doc_flags) + list(row.notes)
            if row.range and row.range.unit:
                if unit is None:
                    unit = row.range.unit
                elif normalize_unit(row.range.unit) != normalize_unit(unit):
                    flags.append(v.REFERENCE_UNIT_MISMATCH)

            normalized_name = normalize_test_name(row.name)
            if normalized_name:
                if normalized_name in seen_tests:
                    flags.append(v.DUPLICATE_IN_DOCUMENT)
                seen_tests.add(normalized_name)

            obs = Observation(
                observation_id=_observation_id(doc.document_id, page.page_number, line_number),
                patient_id=doc.patient_id,
                document_id=doc.document_id,
                test_name_original=row.name,
                test_name_normalized=normalized_name,
                value=row.value.value,
                value_operator=row.value.operator,
                value_text=row.value.text,
                value_raw=row.value.raw,
                abnormal_flag_as_printed=row.value.flag,
                unit=unit,
                normalized_unit=normalize_unit(unit),
                reference_low=row.range.low if row.range else None,
                reference_high=row.range.high if row.range else None,
                reference_text=row.range.text if row.range else None,
                observation_date=obs_date,
                date_source=date_source,
                source_page=page.page_number,
                source_line_number=line_number,
                evidence_snippet=text,
                extraction_method=page.method.value,
                ocr_confidence=page.ocr_confidence,
                flags=flags,
            )
            result.observations.append(v.validate_observation(obs, page.clean_text, today=today))

    return result
