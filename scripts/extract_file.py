"""Ingest one file, extract structured observations and print them (Milestone 3 demo).

Usage (from the project root, virtual environment active):

    python -m scripts.extract_file data/synthetic_reports/sample_digital.pdf --patient-id P001
    python -m scripts.extract_file report.png --patient-id P001 --json observations.json

Use only synthetic, de-identified or authorised files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.extraction import extract_observations
from app.ingestion import IngestionError, ingest_file


def _fmt(x: float | None) -> str:
    return "" if x is None else f"{x:g}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract lab observations from a report.")
    parser.add_argument("path", type=Path, help="PDF, JPG/JPEG or PNG file")
    parser.add_argument("--patient-id", default=None, help="pseudonymous patient ID, e.g. P001")
    parser.add_argument("--date-order", choices=["DMY", "MDY"], default="DMY")
    parser.add_argument(
        "--json", type=Path, default=None, metavar="OUT", help="write the full result as JSON"
    )
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to a legacy codepage
        sys.stdout.reconfigure(encoding="utf-8")

    settings = get_settings()
    setup_logging(settings)
    try:
        doc = ingest_file(args.path, patient_id=args.patient_id, settings=settings)
    except (IngestionError, FileNotFoundError) as exc:
        code = getattr(exc, "code", "file_not_found")
        message = getattr(exc, "message", str(exc))
        print(f"ERROR [{code}]: {message}", file=sys.stderr)
        return 2

    result = extract_observations(doc, date_order=args.date_order)

    print(f"document_id      : {result.document_id}")
    print(f"file             : {result.filename} ({result.source_type})")
    print(
        f"patient_id       : {result.patient_id} (printed on report: {result.report_patient_ids})"
    )
    print(f"observation date : {result.observation_date} ({result.date_source.value})")
    for warning in result.warnings:
        print(f"WARNING          : {warning}")
    print(f"observations     : {len(result.observations)} {result.count_by_status()}\n")

    header = (
        f"{'test (normalised)':<20} {'value':>10} {'unit':<10} {'range':<14} {'status':<13} flags"
    )
    print(header)
    print("-" * len(header))
    for o in result.observations:
        value = o.value_text or f"{o.value_operator or ''}{_fmt(o.value)}"
        ref = (
            f"{_fmt(o.reference_low)}-{_fmt(o.reference_high)}"
            if o.reference_low is not None or o.reference_high is not None
            else ""
        )
        name = o.test_name_normalized or f"? {o.test_name_original}"
        print(
            f"{name:<20} {value:>10} {o.normalized_unit or o.unit or '':<10} {ref:<14} "
            f"{o.validation_status.value:<13} {', '.join(o.flags)}"
        )
    for line in result.unparsed_lines:
        print(f"UNPARSED (page {line.page_number}, line {line.line_number}): {line.text}")

    if args.json:
        args.json.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nFull result written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
