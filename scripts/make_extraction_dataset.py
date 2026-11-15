"""Generate the SYNTHETIC extraction evaluation set with known correct answers.

    python -m scripts.make_extraction_dataset

Writes, into data/evaluation/extraction/:
* one digital PDF and one PNG image (needs OCR) for every report case below
* ground_truth.json - the correct observations for every file

All values are made up. Each case tests something specific (aliases, '<5' values,
missing ranges, Indian number grouping, several dates, ...). To add a case, append
to CASES; the printed cells and the expected answer are written side by side.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from tests import factories as f

OUT_DIR = Path("data/evaluation/extraction")
TITLE = "SYNTHETIC LABORATORY REPORT"


@dataclass
class Row:
    printed: tuple[str, str, str, str]  # name, result, unit, reference range (as printed)
    test: str  # expected standard name
    value: float | None = None
    op: str | None = None
    text: str | None = None
    unit: str | None = None  # expected normalised unit
    low: float | None = None
    high: float | None = None

    def expected(self) -> dict:
        return {
            "test_name_normalized": self.test,
            "value": self.value,
            "value_operator": self.op,
            "value_text": self.text,
            "normalized_unit": self.unit,
            "reference_low": self.low,
            "reference_high": self.high,
        }


@dataclass
class Case:
    name: str
    patient_id: str
    header: list[str]  # lines after the title
    date: str | None  # expected observation date (ISO) or None
    rows: list[Row]
    note: str = ""


CASES = [
    Case(
        "cbc_basic",
        "P001",
        ["Patient ID: P001", "Collection Date: 10/08/2026", "Report Date: 12/08/2026"],
        "2026-08-10",
        [
            Row(
                ("Hemoglobin", "13.2", "g/dL", "12.0 - 16.0"),
                "hemoglobin",
                13.2,
                unit="g/dL",
                low=12.0,
                high=16.0,
            ),
            Row(
                ("WBC Count", "7.5", "10^3/uL", "4.0 - 11.0"),
                "wbc",
                7.5,
                unit="10^3/µL",
                low=4.0,
                high=11.0,
            ),
            Row(
                ("Platelet Count", "250", "10^3/uL", "150 - 400"),
                "platelets",
                250,
                unit="10^3/µL",
                low=150,
                high=400,
            ),
            Row(
                ("RBC Count", "4.6", "10^6/uL", "4.2 - 5.4"),
                "rbc",
                4.6,
                unit="10^6/µL",
                low=4.2,
                high=5.4,
            ),
            Row(
                ("Hematocrit", "40.1", "%", "36 - 46"),
                "hematocrit",
                40.1,
                unit="%",
                low=36,
                high=46,
            ),
        ],
        "collection date preferred over report date",
    ),
    Case(
        "cbc_aliases",
        "P001",
        ["Patient ID: P001", "Report Date: 15/11/2025"],
        "2025-11-15",
        [
            Row(
                ("Hb", "11.4 L", "g/dL", "12.0 - 16.0"),
                "hemoglobin",
                11.4,
                unit="g/dL",
                low=12.0,
                high=16.0,
            ),
            Row(
                ("TLC", "11500 H", "/cumm", "4000 - 11000"),
                "wbc",
                11500,
                unit="/µL",
                low=4000,
                high=11000,
            ),
            Row(("PCV", "35.2", "%", "36 - 46"), "hematocrit", 35.2, unit="%", low=36, high=46),
            Row(("ESR", "22 H", "mm/hr", "0 - 20"), "esr", 22, unit="mm/hr", low=0, high=20),
        ],
        "short names and printed H/L flags",
    ),
    Case(
        "diabetes",
        "P002",
        ["Patient ID: P002", "Report Date: 03/02/2026"],
        "2026-02-03",
        [
            Row(
                ("Fasting Blood Sugar", "126 H", "mg/dL", "70 - 99"),
                "glucose_fasting",
                126,
                unit="mg/dL",
                low=70,
                high=99,
            ),
            Row(("HbA1c", "6.4", "%", "< 5.7"), "hba1c", 6.4, unit="%", high=5.7),
            Row(("Random Blood Sugar", "180", "mg/dL", ""), "glucose_random", 180, unit="mg/dL"),
        ],
        "one-sided range and a missing range",
    ),
    Case(
        "kidney",
        "P002",
        ["Patient ID: P002", "Report Date: 05-Mar-2026"],
        "2026-03-05",
        [
            Row(
                ("S. Creatinine", "0.9", "mg/dL", "0.6 - 1.2"),
                "creatinine",
                0.9,
                unit="mg/dL",
                low=0.6,
                high=1.2,
            ),
            Row(
                ("Blood Urea", "28", "mg/dL", "15 - 40"), "urea", 28, unit="mg/dL", low=15, high=40
            ),
            Row(
                ("Uric Acid", "5.1", "mg/dL", "Up to 6.0"), "uric_acid", 5.1, unit="mg/dL", high=6.0
            ),
        ],
        "month-name date and 'Up to' range",
    ),
    Case(
        "lipid",
        "P003",
        ["Patient ID: P003", "Sample Collected On: 20/09/2026", "Report Date: 21/09/2026"],
        "2026-09-20",
        [
            Row(
                ("Total Cholesterol", "210 H", "mg/dL", "< 200"),
                "cholesterol_total",
                210,
                unit="mg/dL",
                high=200,
            ),
            Row(("HDL Cholesterol", "45", "mg/dL", "> 40"), "hdl", 45, unit="mg/dL", low=40),
            Row(("LDL Cholesterol", "130 H", "mg/dL", "< 100"), "ldl", 130, unit="mg/dL", high=100),
            Row(
                ("Triglycerides", "150", "mg/dL", "< 150"),
                "triglycerides",
                150,
                unit="mg/dL",
                high=150,
            ),
        ],
        "lipid panel with one-sided ranges",
    ),
    Case(
        "liver",
        "P003",
        ["Patient ID: P003", "Report Date: 2026-01-15"],
        "2026-01-15",
        [
            Row(("SGPT (ALT)", "32", "U/L", "7 - 56"), "alt", 32, unit="U/L", low=7, high=56),
            Row(("SGOT (AST)", "28", "U/L", "5 - 40"), "ast", 28, unit="U/L", low=5, high=40),
            Row(
                ("Total Bilirubin", "0.8", "mg/dL", "0.3 - 1.2"),
                "bilirubin_total",
                0.8,
                unit="mg/dL",
                low=0.3,
                high=1.2,
            ),
            Row(
                ("Alkaline Phosphatase", "95", "U/L", "44 - 147"),
                "alp",
                95,
                unit="U/L",
                low=44,
                high=147,
            ),
        ],
        "ISO date and bracketed names",
    ),
    Case(
        "thyroid_vitamins",
        "P004",
        ["Patient ID: P004", "Report Date: 18/06/2026"],
        "2026-06-18",
        [
            Row(
                ("TSH", "2.5", "µIU/mL", "0.4 - 4.0"), "tsh", 2.5, unit="µIU/mL", low=0.4, high=4.0
            ),
            Row(
                ("Vitamin D", "18 L", "ng/mL", "30 - 100"),
                "vitamin_d",
                18,
                unit="ng/mL",
                low=30,
                high=100,
            ),
            Row(
                ("Vitamin B12", "350", "pg/mL", "200 - 900"),
                "vitamin_b12",
                350,
                unit="pg/mL",
                low=200,
                high=900,
            ),
        ],
        "micro sign in unit",
    ),
    Case(
        "operators",
        "P004",
        ["Patient ID: P004", "Report Date: 22/07/2026"],
        "2026-07-22",
        [
            Row(("CRP", "<5", "mg/L", "0 - 5"), "crp", 5, op="<", unit="mg/L", low=0, high=5),
            Row(
                ("Ferritin", ">1000", "ng/mL", "15 - 150"),
                "ferritin",
                1000,
                op=">",
                unit="ng/mL",
                low=15,
                high=150,
            ),
            Row(
                ("Serum Iron", "60", "µg/dL", "60 - 170"),
                "iron",
                60,
                unit="µg/dL",
                low=60,
                high=170,
            ),
        ],
        "values with comparison operators",
    ),
    Case(
        "serology",
        "P001",
        ["Patient ID: P001", "Report Date: 09/09/2026"],
        "2026-09-09",
        [
            Row(("HBsAg", "Non Reactive", "", ""), "hbsag", text="Non Reactive"),
            Row(("Urine Glucose", "Negative", "", ""), "urine_glucose", text="Negative"),
            Row(
                ("Hemoglobin", "12.9", "g/dL", "12.0 - 16.0"),
                "hemoglobin",
                12.9,
                unit="g/dL",
                low=12.0,
                high=16.0,
            ),
        ],
        "text results",
    ),
    Case(
        "electrolytes",
        "P002",
        ["Patient ID: P002", "Collected On: 14/10/2026"],
        "2026-10-14",
        [
            Row(
                ("Sodium", "138", "mmol/L", "135 - 145"),
                "sodium",
                138,
                unit="mmol/L",
                low=135,
                high=145,
            ),
            Row(
                ("Potassium", "4.2", "mmol/L", "3.5 - 5.1"),
                "potassium",
                4.2,
                unit="mmol/L",
                low=3.5,
                high=5.1,
            ),
            Row(
                ("Chloride", "101", "mmol/L", "98 - 107"),
                "chloride",
                101,
                unit="mmol/L",
                low=98,
                high=107,
            ),
        ],
        "collection date only",
    ),
    Case(
        "indian_numbers",
        "P003",
        ["Patient ID: P003", "Report Date: 30/04/2026"],
        "2026-04-30",
        [
            Row(
                ("Platelet Count", "1,50,000", "/cumm", "150000-450000"),
                "platelets",
                150000,
                unit="/µL",
                low=150000,
                high=450000,
            ),
            Row(
                ("Total WBC Count", "8,200", "/cumm", "4000-11000"),
                "wbc",
                8200,
                unit="/µL",
                low=4000,
                high=11000,
            ),
        ],
        "Indian digit grouping",
    ),
    Case(
        "no_date",
        "P004",
        ["Patient ID: P004"],
        None,
        [
            Row(
                ("Hemoglobin", "12.8", "g/dL", "12.0 - 16.0"),
                "hemoglobin",
                12.8,
                unit="g/dL",
                low=12.0,
                high=16.0,
            ),
            Row(
                ("Glucose", "92", "mg/dL", "70 - 99"), "glucose", 92, unit="mg/dL", low=70, high=99
            ),
        ],
        "no date on the report: must stay empty",
    ),
    Case(
        "ambiguous_date",
        "P001",
        ["Patient ID: P001", "Date: 01/02/2026", "Date: 03/02/2026"],
        None,
        [
            Row(
                ("Creatinine", "1.0", "mg/dL", "0.6 - 1.2"),
                "creatinine",
                1.0,
                unit="mg/dL",
                low=0.6,
                high=1.2,
            ),
            Row(("Urea", "30", "mg/dL", "15 - 40"), "urea", 30, unit="mg/dL", low=15, high=40),
        ],
        "two conflicting dates: must be flagged, not guessed",
    ),
]


def _pdf(case: Case) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=f.A4[0], height=f.A4[1])
    f._write_report_page(page, [r.printed for r in case.rows], [TITLE, *case.header])
    return doc.tobytes()


def _png(case: Case) -> bytes:
    image = f.render_report_image(rows=[r.printed for r in case.rows], header=[TITLE, *case.header])
    return f.png_bytes(image)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    documents = []
    for case in CASES:
        for ext, build in (("pdf", _pdf), ("png", _png)):
            filename = f"{case.name}.{ext}"
            (OUT_DIR / filename).write_bytes(build(case))
            documents.append(
                {
                    "file": filename,
                    "patient_id": case.patient_id,
                    "observation_date": case.date,
                    "note": case.note,
                    "observations": [r.expected() for r in case.rows],
                }
            )
            print(f"wrote {OUT_DIR / filename}")
    truth = {
        "description": "Synthetic extraction ground truth (made-up values, not clinical data).",
        "date_order": "DMY",
        "documents": documents,
    }
    path = OUT_DIR / "ground_truth.json"
    path.write_text(json.dumps(truth, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {path} ({len(documents)} documents)")


if __name__ == "__main__":
    main()
