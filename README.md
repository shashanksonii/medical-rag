# Intelligent Longitudinal Medical Record Analysis and Evidence-Grounded Clinical RAG

Final-year B.Tech CSE project (Delhi Technological University).


A Python-first, CPU-friendly system that ingests medical reports, extracts structured
observations with provenance, analyses repeated measurements descriptively over time, and
answers questions with evidence from both a patient's own history and a curated medical
knowledge base. Three RAG configurations (General, Patient-History, Dual-Source Longitudinal)
are compared in a controlled experiment, in English, Hindi and Hinglish.

> **Disclaimer.** This software is for medical-information organisation and educational support
> only. It does not diagnose, recommend treatment, or replace a qualified medical professional.
> Use only synthetic, de-identified or properly authorised data.

## Status

Milestones 1 (project foundation) and 2 (document ingestion) are implemented. See
[docs/MILESTONES.md](docs/MILESTONES.md) for the full checklist.

## Technology stack (locked)

Python, FastAPI + Uvicorn, Pydantic, PyMuPDF, Tesseract + Pillow, PostgreSQL, SQLAlchemy, Alembic,
pandas + NumPy, Ollama, Sentence Transformers, FAISS, scikit-learn, pytest, matplotlib.
Installed so far: FastAPI, Uvicorn, Pydantic, pydantic-settings (Milestone 1) and PyMuPDF,
Pillow, pytesseract (Milestone 2; `pytesseract` is a thin wrapper, the Tesseract program is a
separate Windows install - see below). The rest arrives with the milestone that needs it.

## Project layout

```text
medical-rag/
├── app/
│   ├── __init__.py          # package + __version__
│   ├── main.py              # create_app() factory
│   ├── api/
│   │   └── health.py        # GET /health
│   ├── core/
│   │   ├── config.py        # typed settings (MEDRAG_* env vars / .env)
│   │   ├── logging.py       # idempotent logging setup
│   │   └── middleware.py    # request IDs + request logging
│   └── ingestion/           # Milestone 2
│       ├── service.py       # ingest_file() / ingest_bytes() - the entry point
│       ├── pdf_extractor.py # PyMuPDF text layer + per-page OCR fallback
│       ├── ocr.py           # Tesseract engine, image loading/preparation
│       ├── layout.py        # words -> table-preserving text rows
│       ├── preprocessing.py # number/unit-safe text cleanup
│       ├── schemas.py       # IngestedDocument / PageText / TextLine
│       └── errors.py        # typed errors with stable codes
├── data/
│   ├── synthetic_reports/   # synthetic test reports (later milestones)
│   ├── curated_knowledge/   # curated medical knowledge base (later milestones)
│   └── evaluation/          # fixed evaluation sets (later milestones)
├── docs/MILESTONES.md       # checklist + documented defaults
├── scripts/
│   ├── ingest_file.py       # CLI: python -m scripts.ingest_file <file>
│   └── make_sample_reports.py  # regenerates the synthetic samples
├── tests/
│   └── factories.py         # synthetic PDFs/images + FakeOCR (no binary fixtures needed)
├── .env.example
├── pyproject.toml           # pytest + ruff configuration
├── requirements.txt         # runtime dependencies
└── requirements-dev.txt     # runtime + test/lint dependencies
```

## Setup (Windows PowerShell)

Requires Python 3.10 or newer (3.11/3.12 recommended). Check with `py --version`.

```powershell
cd medical-rag

# 1. Create and activate a virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1
# If activation is blocked, allow scripts for this session only, then retry:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 2. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

# 3. Create your local configuration (optional - defaults work without it)
Copy-Item .env.example .env
```

## Install Tesseract OCR (Windows) - needed for scanned PDFs and images

Digital PDFs work without it; scanned PDFs and JPG/PNG images need the Tesseract program.

1. Download the 64-bit Windows installer from <https://github.com/UB-Mannheim/tesseract/wiki>
   and run it. Keep the default folder `C:\Program Files\Tesseract-OCR` and make sure the
   English language data (`eng`) is selected.
2. Open a **new** PowerShell window and check: `& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version`
3. Either add `C:\Program Files\Tesseract-OCR` to your `PATH`, or set the full path in `.env`:
   `MEDRAG_TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`
   (the app also auto-detects the default install folder).
4. Optional, for later Hindi work: tick the Hindi (`hin`) language data in the installer and set
   `MEDRAG_OCR_LANGUAGES=eng+hin`.

If Tesseract is missing, the app raises `OCRUnavailableError` with these instructions instead of
failing silently.

## Run the API

```powershell
uvicorn app.main:create_app --factory --reload
```

Then open:

- Interactive API docs (Swagger UI): <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/health>

or from a second PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "Medical Record RAG API",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-01-01T12:00:00.000000Z"
}
```

## Try document ingestion (Milestone 2)

```powershell
pip install -r requirements-dev.txt          # once, to pick up the new libraries
python -m scripts.make_sample_reports        # optional: regenerate synthetic samples
python -m scripts.ingest_file data\synthetic_reports\sample_digital.pdf
python -m scripts.ingest_file data\synthetic_reports\sample_scanned.pdf   # needs Tesseract
python -m scripts.ingest_file data\synthetic_reports\sample_report.png --json out.json
```

From Python:

```python
from app.ingestion import ingest_file

doc = ingest_file("report.pdf", patient_id="P001")
for page in doc.pages:
    print(page.page_number, page.method, page.ocr_confidence)
    print(page.clean_text)  # cleaned text, table rows kept on one line
    # page.raw_text, page.lines[i].bbox, doc.sha256, doc.document_id ... = provenance
```

How it works: each PDF page is read from its text layer with PyMuPDF. A page with fewer than
`MEDRAG_PDF_MIN_TEXT_CHARS` letters/digits that contains images or graphics is rendered at
`MEDRAG_OCR_DPI` and OCR'd. JPG/PNG files are always OCR'd. Words are regrouped into visual rows,
so a table row such as `Hemoglobin  13.2  g/dL  12.0 - 16.0` stays on one line, with two spaces
marking column gaps. Cleaning never changes digits, decimal points, dates, signs, units or `µ`.

**OCR can misread characters** (for example `P001` -> `POO1`, or a lost decimal point under some
Tesseract settings). The pipeline never "corrects" text; it records a per-page confidence and warns
when it is low. Structured extraction (Milestone 3) must validate values, and the research
evaluation (Milestone 10) measures OCR-induced errors.

## Run the tests and lint checks

```powershell
python -m pytest
ruff check .
ruff format --check .
```

Tests that run real Tesseract are skipped automatically when it is not installed
(`python -m pytest -rs` shows which). Install Tesseract and run again to execute them.

## Configuration

All settings are environment variables with the `MEDRAG_` prefix, or entries in `.env`
(see `.env.example`).

| Variable | Default | Description |
|---|---|---|
| `MEDRAG_APP_NAME` | `Medical Record RAG API` | Service name shown in docs and `/health` |
| `MEDRAG_ENVIRONMENT` | `development` | `development`, `testing` or `production` |
| `MEDRAG_DEBUG` | `false` | FastAPI debug mode |
| `MEDRAG_HOST` / `MEDRAG_PORT` | `127.0.0.1` / `8000` | Bind address (used by your run command, see below) |
| `MEDRAG_LOG_LEVEL` | `INFO` | `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG` |
| `MEDRAG_LOG_FILE` | *(blank)* | Optional rotating log file path; blank = console only |
| `MEDRAG_DATA_DIR` | `data` | Root folder for datasets |
| `MEDRAG_INGESTION_MAX_FILE_MB` | `25` | Maximum upload size |
| `MEDRAG_INGESTION_MAX_PDF_PAGES` | `200` | Maximum PDF pages |
| `MEDRAG_PDF_MIN_TEXT_CHARS` | `30` | Below this many letters/digits a page is considered to lack a text layer |
| `MEDRAG_TESSERACT_CMD` | *(blank)* | Full path to `tesseract.exe`; blank = PATH, then default Windows folders |
| `MEDRAG_OCR_LANGUAGES` | `eng` | Tesseract languages, e.g. `eng+hin` |
| `MEDRAG_OCR_DPI` | `300` | Render resolution for scanned PDF pages |
| `MEDRAG_OCR_PSM` | `6` | Tesseract page segmentation mode (6 kept decimals reliably in testing) |
| `MEDRAG_OCR_TIMEOUT_SECONDS` | `120` | Per-page OCR time limit |

`MEDRAG_HOST` and `MEDRAG_PORT` are read into the settings object but uvicorn takes its bind
address from the command line. To use a different port, run
`uvicorn app.main:create_app --factory --reload --port 8100`.

## Privacy and safety conventions

- Use synthetic, de-identified or authorised data only; real data folders are git-ignored.
- Logs contain method, path, status, duration and a request ID - never request bodies, query
  strings or report text. Keep it that way in later milestones.
- Ingestion logs only the document ID, type and page counts - never filenames or text.
- Patient identifiers must be pseudonymous (for example `P001`).
- `.env` is git-ignored; never commit credentials..

## Git

```powershell
git init
git add .
git commit -m "Milestone 1: project foundation"
```
