"""Ingest one file and print what was extracted (manual check of Milestone 2).

Usage (from the project root, virtual environment active):

    python -m scripts.ingest_file data/synthetic_reports/sample_digital.pdf
    python -m scripts.ingest_file scan.png --patient-id P001 --json out.json
    python -m scripts.ingest_file report.pdf --no-text

Use only synthetic, de-identified or authorised files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.ingestion import IngestionError, ingest_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest a PDF/JPG/PNG and show the extraction.")
    parser.add_argument("path", type=Path, help="PDF, JPG/JPEG or PNG file")
    parser.add_argument("--patient-id", default=None, help="pseudonymous patient ID, e.g. P001")
    parser.add_argument(
        "--json", type=Path, default=None, metavar="OUT", help="write full result as JSON"
    )
    parser.add_argument("--no-text", action="store_true", help="omit the extracted text")
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

    print(f"document_id : {doc.document_id}")
    print(f"file        : {doc.filename} ({doc.file_type.value}, {doc.size_bytes:,} bytes)")
    print(f"source type : {doc.source_type.value}")
    print(f"pages       : {doc.page_count}")
    print(f"sha256      : {doc.sha256}")
    for warning in doc.warnings:
        print(f"WARNING     : {warning}")
    for page in doc.pages:
        confidence = (
            f", confidence {page.ocr_confidence:.0f}/100" if page.ocr_confidence is not None else ""
        )
        print(
            f"\n--- page {page.page_number}: {page.method.value}{confidence}, "
            f"{len(page.lines)} lines ---"
        )
        for warning in page.warnings:
            print(f"WARNING: {warning}")
        if not args.no_text:
            print(page.clean_text)

    if args.json:
        args.json.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nFull result written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
