"""Test-name and unit normalisation.

* Different labs write the same test differently (``Hb``, ``Haemoglobin``, ``HGB``).
  ``normalize_test_name`` maps them to one standard name (``hemoglobin``) so the same
  measurement can be found across reports. The original name is always kept as well.
* Units are only re-spelled (``g/dl`` -> ``g/dL``, ``/cumm`` -> ``/µL``). Values are
  NEVER converted between units (for example mg/dL -> mmol/L) in this milestone.

To support a new test, add its spellings to ``TEST_ALIASES``. Keep aliases lowercase
and written the way ``_name_key`` produces them (punctuation replaced by spaces).
"""

from __future__ import annotations

import re

# standard name -> spellings seen on reports (after _name_key cleaning)
TEST_ALIASES: dict[str, list[str]] = {
    # Complete blood count
    "hemoglobin": ["hemoglobin", "haemoglobin", "hb", "hgb", "hb hemoglobin", "hemoglobin hb"],
    "wbc": [
        "wbc",
        "wbc count",
        "total wbc count",
        "tlc",
        "total leucocyte count",
        "total leukocyte count",
        "white blood cells",
        "white blood cell count",
        "leucocytes",
    ],
    "rbc": ["rbc", "rbc count", "total rbc count", "red blood cell count", "red blood cells"],
    "platelets": ["platelets", "platelet count", "plt", "platelet"],
    "hematocrit": ["hematocrit", "haematocrit", "hct", "pcv", "packed cell volume"],
    "mcv": ["mcv", "mean corpuscular volume"],
    "mch": ["mch", "mean corpuscular hemoglobin"],
    "mchc": ["mchc", "mean corpuscular hemoglobin concentration"],
    "esr": ["esr", "erythrocyte sedimentation rate"],
    # Sugar
    "glucose_fasting": [
        "fasting blood sugar",
        "fbs",
        "fasting glucose",
        "glucose fasting",
        "fasting plasma glucose",
        "blood sugar fasting",
        "fasting blood glucose",
    ],
    "glucose_random": ["random blood sugar", "rbs", "random glucose", "glucose random"],
    "glucose_postprandial": ["post prandial blood sugar", "ppbs", "glucose pp", "pp blood sugar"],
    "glucose": ["glucose", "blood glucose", "blood sugar", "plasma glucose"],
    "hba1c": ["hba1c", "hb a1c", "a1c", "glycated hemoglobin", "glycosylated hemoglobin"],
    # Kidney
    "creatinine": ["creatinine", "serum creatinine", "s creatinine"],
    "urea": ["urea", "blood urea", "serum urea", "s urea"],
    "bun": ["bun", "blood urea nitrogen"],
    "uric_acid": ["uric acid", "serum uric acid", "s uric acid"],
    # Lipids
    "cholesterol_total": [
        "total cholesterol",
        "cholesterol",
        "cholesterol total",
        "serum cholesterol",
    ],
    "hdl": ["hdl", "hdl cholesterol", "cholesterol hdl", "hdl c"],
    "ldl": ["ldl", "ldl cholesterol", "cholesterol ldl", "ldl c"],
    "triglycerides": ["triglycerides", "triglyceride", "tg", "serum triglycerides"],
    # Liver
    "alt": [
        "alt",
        "sgpt",
        "alt sgpt",
        "sgpt alt",
        "alanine aminotransferase",
        "alanine transaminase",
    ],
    "ast": [
        "ast",
        "sgot",
        "ast sgot",
        "sgot ast",
        "aspartate aminotransferase",
        "aspartate transaminase",
    ],
    "alp": ["alp", "alkaline phosphatase"],
    "bilirubin_total": ["total bilirubin", "bilirubin total", "bilirubin", "serum bilirubin"],
    "albumin": ["albumin", "serum albumin"],
    # Thyroid and vitamins
    "tsh": ["tsh", "thyroid stimulating hormone"],
    "t3": ["t3", "total t3", "triiodothyronine"],
    "t4": ["t4", "total t4", "thyroxine"],
    "vitamin_d": ["vitamin d", "vit d", "25 oh vitamin d", "25 hydroxy vitamin d"],
    "vitamin_b12": ["vitamin b12", "vit b12", "b12", "cobalamin"],
    # Electrolytes and minerals
    "sodium": ["sodium", "serum sodium", "na"],
    "potassium": ["potassium", "serum potassium", "k"],
    "chloride": ["chloride", "serum chloride", "cl"],
    "calcium": ["calcium", "serum calcium", "ca"],
    "iron": ["iron", "serum iron"],
    "ferritin": ["ferritin", "serum ferritin"],
    # Inflammation and serology
    "crp": ["crp", "c reactive protein"],
    "hbsag": ["hbsag", "hepatitis b surface antigen"],
    "urine_glucose": ["urine glucose", "urine sugar"],
}

# unit key (see _unit_key) -> standard spelling
UNIT_ALIASES: dict[str, str] = {
    "g/dl": "g/dL",
    "gm/dl": "g/dL",
    "g%": "g/dL",
    "gm%": "g/dL",
    "mg/dl": "mg/dL",
    "mg/l": "mg/L",
    "ug/dl": "µg/dL",
    "mcg/dl": "µg/dL",
    "ng/dl": "ng/dL",
    "ng/ml": "ng/mL",
    "pg/ml": "pg/mL",
    "ug/ml": "µg/mL",
    "mmol/l": "mmol/L",
    "umol/l": "µmol/L",
    "meq/l": "mEq/L",
    "u/l": "U/L",
    "iu/l": "IU/L",
    "uiu/ml": "µIU/mL",
    "miu/l": "mIU/L",
    "10^3/ul": "10^3/µL",
    "10^3/mm3": "10^3/µL",
    "k/ul": "10^3/µL",
    "thou/ul": "10^3/µL",
    "10^6/ul": "10^6/µL",
    "10^6/mm3": "10^6/µL",
    "million/ul": "10^6/µL",
    "mill/cumm": "10^6/µL",
    "million/cumm": "10^6/µL",
    "/cumm": "/µL",
    "cells/cumm": "/µL",
    "/mm3": "/µL",
    "/ul": "/µL",
    "cells/ul": "/µL",
    "%": "%",
    "fl": "fL",
    "pg": "pg",
    "mm/hr": "mm/hr",
    "mm/h": "mm/hr",
    "mm/1sthr": "mm/hr",
}

_NAME_KEY = {name: std for std, names in TEST_ALIASES.items() for name in names}


def _name_key(name: str) -> str:
    key = name.lower()
    key = re.sub(r"[^a-z0-9]+", " ", key)  # punctuation/brackets -> space
    return re.sub(r"\s+", " ", key).strip()


def normalize_test_name(name: str) -> str | None:
    """Return the standard test name, or ``None`` if the name is not recognised."""
    return _NAME_KEY.get(_name_key(name))


def _unit_key(unit: str) -> str:
    key = unit.strip().lower().replace(" ", "")
    key = key.replace("μ", "u").replace("µ", "u")  # Greek mu and micro sign
    key = key.replace("³", "^3").replace("⁶", "^6")
    key = re.sub(r"^(?:x|\*|×)10", "10", key)  # x10^3/uL -> 10^3/uL
    key = re.sub(r"^10e?(\d)", r"10^\1", key)  # 10e3/uL or 103/uL -> 10^3/uL
    key = key.replace("cu.mm", "cumm").replace("cmm", "cumm").replace("cucumm", "cumm")
    return key


def normalize_unit(unit: str | None) -> str | None:
    """Return the standard spelling of a unit, or ``None`` if unknown/missing."""
    if not unit:
        return None
    return UNIT_ALIASES.get(_unit_key(unit))


def looks_like_unit(text: str) -> bool:
    """Heuristic used by the parser to decide whether a table cell is a unit."""
    text = text.strip()
    if not text or len(text) > 20:
        return False
    if normalize_unit(text):
        return True
    # Unknown but unit-shaped: contains '/' or '%' and no spaces between words
    return bool(re.fullmatch(r"[A-Za-zµμ%^0-9*.]+(?:/[A-Za-zµμ0-9^.]+)+|%", text))
