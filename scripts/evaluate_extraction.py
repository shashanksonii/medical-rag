"""Measure extraction quality on the synthetic ground-truth set.

    python -m scripts.make_extraction_dataset      # once, creates the files
    python -m scripts.evaluate_extraction          # digital PDFs + images (images need Tesseract)
    python -m scripts.evaluate_extraction --skip-ocr

Prints per-file problems and a summary table (precision, recall, F1, numeric,
unit, range and date accuracy), overall and per source type, and saves everything to
data/evaluation/results/extraction_results.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.extraction import extract_observations
from app.extraction.evaluators import evaluate_document, load_ground_truth, summarize
from app.ingestion import IngestionError, OCRUnavailableError, ingest_file

DEFAULT_TRUTH = Path("data/evaluation/extraction/ground_truth.json")
DEFAULT_OUT = Path("data/evaluation/results/extraction_results.json")
METRICS = [
    "documents",
    "tp",
    "fp",
    "fn",
    "precision",
    "recall",
    "f1",
    "numeric_accuracy",
    "unit_accuracy",
    "range_accuracy",
    "date_accuracy",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate structured extraction.")
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_TRUTH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--skip-ocr", action="store_true", help="only evaluate PDF files")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not args.ground_truth.exists():
        print(
            f"ERROR: {args.ground_truth} not found. Run: python -m scripts.make_extraction_dataset",
            file=sys.stderr,
        )
        return 2

    settings = get_settings()
    setup_logging(settings)
    base = args.ground_truth.parent
    scores, skipped = [], []
    for expected in load_ground_truth(args.ground_truth):
        if args.skip_ocr and not expected.file.lower().endswith(".pdf"):
            continue
        try:
            doc = ingest_file(
                base / expected.file, patient_id=expected.patient_id, settings=settings
            )
        except OCRUnavailableError:
            skipped.append(f"{expected.file} (Tesseract not installed)")
            continue
        except (IngestionError, FileNotFoundError) as exc:
            skipped.append(f"{expected.file} ({exc})")
            continue
        result = extract_observations(doc, today=date.today())
        score = evaluate_document(result, expected)
        scores.append(score)
        status = "OK " if not score.errors else "ERR"
        print(f"[{status}] {expected.file:<28} TP={score.tp} FP={score.fp} FN={score.fn}")
        for error in score.errors:
            print(f"        - {error}")

    for item in skipped:
        print(f"[SKIP] {item}")
    if not scores:
        print("Nothing was evaluated.", file=sys.stderr)
        return 1

    summary = summarize(scores)
    print("\n" + f"{'metric':<18}" + "".join(f"{group:>14}" for group in summary))
    for metric in METRICS:
        row = "".join(
            f"{'-' if summary[g][metric] is None else summary[g][metric]:>14}" for g in summary
        )
        print(f"{metric:<18}{row}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "summary": summary,
                "documents": [s.model_dump() for s in scores],
                "skipped": skipped,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nResults written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
