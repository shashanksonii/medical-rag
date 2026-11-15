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

Milestone 1 (project foundation) is implemented. See [docs/MILESTONES.md](docs/MILESTONES.md)
for the full checklist.

## Technology stack (locked)

Python, FastAPI + Uvicorn, Pydantic, PyMuPDF, Tesseract + Pillow, PostgreSQL, SQLAlchemy, Alembic,
pandas + NumPy, Ollama, Sentence Transformers, FAISS, scikit-learn, pytest, matplotlib.
Only the API-foundation subset is installed in Milestone 1 (FastAPI, Uvicorn, Pydantic,
pydantic-settings, pytest). The rest arrives with the milestone that needs it.

## Project layout

```text
medical-rag/
├── app/
│   ├── __init__.py          # package + __version__
│   ├── main.py              # create_app() factory
│   ├── api/
│   │   └── health.py        # GET /health
│   └── core/
│       ├── config.py        # typed settings (MEDRAG_* env vars / .env)
│       ├── logging.py       # idempotent logging setup
│       └── middleware.py    # request IDs + request logging
├── data/
│   ├── synthetic_reports/   # synthetic test reports (later milestones)
│   ├── curated_knowledge/   # curated medical knowledge base (later milestones)
│   └── evaluation/          # fixed evaluation sets (later milestones)
├── docs/MILESTONES.md       # checklist + documented defaults
├── scripts/
├── tests/
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

## Run the tests and lint checks

```powershell
python -m pytest
ruff check .
ruff format --check .
```

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

`MEDRAG_HOST` and `MEDRAG_PORT` are read into the settings object but uvicorn takes its bind
address from the command line. To use a different port, run
`uvicorn app.main:create_app --factory --reload --port 8100`.

## Privacy and safety conventions

- Use synthetic, de-identified or authorised data only; real data folders are git-ignored.
- Logs contain method, path, status, duration and a request ID - never request bodies, query
  strings or report text. Keep it that way in later milestones.
- Patient identifiers must be pseudonymous (for example `P001`).
- `.env` is git-ignored; never commit credentials..

## Git

```powershell
git init
git add .
git commit -m "Milestone 1: project foundation"
```
