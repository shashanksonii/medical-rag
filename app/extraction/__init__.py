"""Structured extraction (Milestone 3): report text -> validated medical observations."""

from app.extraction.schemas import (
    DateSource,
    ExtractionResult,
    FoundDate,
    Observation,
    UnparsedLine,
    ValidationStatus,
)
from app.extraction.service import extract_observations

__all__ = [
    "DateSource",
    "ExtractionResult",
    "FoundDate",
    "Observation",
    "UnparsedLine",
    "ValidationStatus",
    "extract_observations",
]
