"""Generate small SYNTHETIC sample files in data/synthetic_reports/.

    python -m scripts.make_sample_reports

The files contain obviously fake data (patient "P001") and exist only so the
ingestion pipeline can be tried by hand. They reuse the test factories.
"""

from __future__ import annotations

from pathlib import Path

from tests import factories as f

OUT_DIR = Path("data/synthetic_reports")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    image = f.render_report_image()
    files = {
        "sample_digital.pdf": f.make_digital_pdf(pages=2),
        "sample_scanned.pdf": f.make_scanned_pdf(),
        "sample_mixed.pdf": f.make_mixed_pdf(),
        "sample_report.png": f.png_bytes(image),
        "sample_report.jpg": f.jpeg_bytes(image),
    }
    for name, data in files.items():
        (OUT_DIR / name).write_bytes(data)
        print(f"wrote {OUT_DIR / name} ({len(data):,} bytes)")


if __name__ == "__main__":
    main()
