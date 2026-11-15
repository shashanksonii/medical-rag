# Project milestone checklist

Status legend: `[x]` implemented and verified, `[~]` in progress, `[ ]` not started.

- [x] **Milestone 1 - Project foundation** (repo structure, dependencies, FastAPI app, config, logging, `/health`, tests, README)
- [x] **Milestone 2 - Document ingestion** (PyMuPDF, Tesseract OCR + Pillow, page-level provenance)
- [ ] Milestone 3 - Structured extraction (Pydantic schemas, parsing, normalisation, validation, evaluation script)
- [ ] Milestone 4 - Database (PostgreSQL, SQLAlchemy, Alembic, repositories, endpoints)
- [ ] Milestone 5 - Longitudinal analysis (descriptive trends, insufficient-data handling)
- [ ] Milestone 6 - General medical knowledge retrieval (chunking, embeddings, FAISS)
- [ ] Milestone 7 - Patient-history retrieval (patient-level filtering, provenance)
- [ ] Milestone 8 - Three RAG configurations (general / patient / dual) via one interface, Ollama
- [ ] Milestone 9 - Evidence-grounded answers and multilingual support (English, Hindi, Hinglish)
- [ ] Milestone 10 - Research evaluation (metrics, tables, plots, failure cases)
- [ ] Milestone 11 - Final integration (integration tests, diagrams, demo, report support)

## Documented defaults (Milestone 1)

| Decision | Choice | Reason |
|---|---|---|
| Config library | `pydantic-settings` | Official Pydantic companion; typed, validated settings. Only dependency added beyond the locked stack table. |
| Env var prefix | `MEDRAG_` | Avoids collisions with generic `HOST` / `PORT` variables. |
| App entry point | `uvicorn app.main:create_app --factory` | No import-time side effects, so tests never load a developer's `.env`. |
| Logging | stdlib `logging`, optional rotating file | No extra dependency. Logs method/path/status/duration/request-ID only - never bodies, query strings or report text. |
| Python version | 3.10+ (3.11 or 3.12 recommended) | Matches the stack; all pinned libraries support it. |
| Test client dependency | `httpx2` | Starlette 1.x deprecates `httpx` for its `TestClient`. |
| PyMuPDF version | `>=1.26,<2` | PyMuPDF 2.x adds onnxruntime, networkx, pymupdf-layout, pymupdf4llm and more; the core 1.x library has no dependencies and ships `abi3` wheels for Python 3.10+. |
| OCR wrapper | `pytesseract` | Thin wrapper over the Tesseract executable (stack: Tesseract + Pillow). |
| OCR page segmentation | `--psm 6` | In calibration `--psm 4` dropped a decimal point (`7.5` -> `75`); 3 and 6 kept it. |
| Text row reconstruction | Words grouped by vertical position | Native PDF/OCR text splits table cells onto separate lines; grouping keeps value, unit and range in one row. |
| Column gaps | Two spaces | Preserved through cleaning so Milestone 3 can split table cells. |
| OCR "correction" | None | A guessed fix could silently change a clinical value. Low confidence is flagged instead. |
| Scanned-page detection | < 30 letters/digits **and** page has images/graphics | Blank pages are not OCR'd; short digital cover pages keep their text layer. |
| Upload endpoint | Not in Milestone 2 | Needs patient/document storage (Milestone 4). Ingestion is a Python API + CLI for now. |

## Handed to Milestone 3

`IngestedDocument.pages[i].clean_text` (and `.lines` with bounding boxes), plus `document_id`,
`patient_id`, `filename`, `sha256`, `page_number`, `method` and `ocr_confidence` as provenance.
