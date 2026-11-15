"""Data models produced by structured extraction (Milestone 3).

Input:  ``app.ingestion.schemas.IngestedDocument`` (Milestone 2).
Output: ``ExtractionResult`` holding one ``Observation`` per laboratory row.

Design rules (important for medical data):
* Never invent a value. Anything the report does not state stays ``None``.
* Keep the original text next to every normalised field (``test_name_original``,
  ``value_raw``, ``unit``, ``reference_text``, ``evidence_snippet``).
* Keep comparison operators: ``<5`` is stored as value 5 with operator ``<``.
* Problems are recorded as ``flags`` and summarised in ``validation_status``
  instead of being silently "fixed".
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

Operator = Literal["<", "<=", ">", ">="]
PrintedFlag = Literal["H", "L"]


class ValidationStatus(str, Enum):
    VALID = "valid"  # no problems found
    NEEDS_REVIEW = "needs_review"  # usable, but a human should check the flags
    INVALID = "invalid"  # must not be used (e.g. value not found in the source text)


class DateSource(str, Enum):
    COLLECTION = "collection_date"  # sample collection date (preferred)
    REPORT = "report_date"  # report generation date
    OTHER = "other_date"  # a generic "Date:" / registration / received label
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"  # several different dates with the same priority


class FoundDate(BaseModel):
    """A labelled date found anywhere in the document."""

    label: str
    source: DateSource
    text: str
    parsed: date | None = None  # None when the text is not a valid date
    page_number: int
    line_number: int


class Observation(BaseModel):
    """One structured laboratory measurement with full provenance."""

    observation_id: str = Field(description="Stable ID: same document/page/line -> same ID")
    patient_id: str | None = None
    document_id: str

    test_name_original: str = Field(description="Test name exactly as printed")
    test_name_normalized: str | None = Field(
        default=None, description="Standard name such as 'hemoglobin'; None if not recognised"
    )

    value: float | None = Field(default=None, description="Numeric result, if numeric")
    value_operator: Operator | None = Field(
        default=None, description="Comparison operator printed with the value, e.g. '<' in '<5'"
    )
    value_text: str | None = Field(
        default=None, description="Textual result such as 'Negative' or 'Non Reactive'"
    )
    value_raw: str = Field(description="The value exactly as printed, e.g. '1,50,000' or '<5'")
    abnormal_flag_as_printed: PrintedFlag | None = Field(
        default=None, description="H/L printed by the lab. Never calculated by us."
    )

    unit: str | None = Field(default=None, description="Unit exactly as printed")
    normalized_unit: str | None = Field(default=None, description="Standard spelling of the unit")

    reference_low: float | None = None
    reference_high: float | None = None
    reference_text: str | None = Field(default=None, description="Reference range as printed")

    observation_date: date | None = None
    date_source: DateSource = DateSource.NOT_FOUND

    source_page: int = Field(ge=1)
    source_line_number: int = Field(ge=1)
    evidence_snippet: str = Field(description="The full source line the values were read from")
    extraction_method: str = Field(description="'pdf_text' or 'ocr' (from ingestion)")
    ocr_confidence: float | None = None

    flags: list[str] = Field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.VALID


class UnparsedLine(BaseModel):
    """A line that looked like a result but could not be parsed (kept for review)."""

    page_number: int
    line_number: int
    text: str
    reason: str


class ExtractionResult(BaseModel):
    """Everything extracted from one ingested document."""

    document_id: str
    patient_id: str | None = None
    report_patient_ids: list[str] = Field(
        default_factory=list, description="Patient IDs printed on the report itself"
    )
    filename: str
    source_type: str
    observation_date: date | None = None
    date_source: DateSource = DateSource.NOT_FOUND
    dates_found: list[FoundDate] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    unparsed_lines: list[UnparsedLine] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def count_by_status(self) -> dict[str, int]:
        counts = {status.value: 0 for status in ValidationStatus}
        for obs in self.observations:
            counts[obs.validation_status.value] += 1
        return counts
