# Project milestone checklist

Status legend: `[x]` implemented and verified, `[~]` in progress, `[ ]` not started.

- [x] **Milestone 1 - Project foundation** (repo structure, dependencies, FastAPI app, config, logging, `/health`, tests, README)
- [x] **Milestone 2 - Document ingestion** (PyMuPDF, Tesseract OCR + Pillow, page-level provenance)
- [~] **Milestone 3 - Structured extraction** (Pydantic schemas, parsing, normalisation, validation, evaluation script) - implemented; tick `[x]` after local verification
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

## Documented defaults (Milestone 3)

| Decision | Choice | Reason |
|---|---|---|
| Extraction approach | Rule-based (regex + Pydantic), no LLM | Deterministic and testable; an LLM must never invent missing values. Ollama arrives in Milestone 8. |
| New dependencies | None | Standard library + Pydantic are enough. |
| Table cells | Split on two or more spaces | Matches the Milestone 2 column-gap convention. A single-line fallback handles `Hemoglobin: 13.2 g/dL (12.0-16.0)` and OCR output that lost its gaps. |
| Numeric dates | Day/month/year (`12/08/2026` = 12 August) | Indian convention. `date_order="MDY"` is available. Impossible dates become `None`; the order is never swapped silently. |
| Which date | Collection date > report date > other labelled date | Collection date is when the sample was taken. Conflicting dates in the best group -> `ambiguous_date`, no date chosen. |
| Comparison operators | Kept in `value_operator` (`<5` -> 5 with `<`) | Dropping the operator changes the meaning. |
| Reference ranges | Only as printed; one-sided ranges fill one side | Never insert a "standard" range. |
| Units | Spelling normalised only (`g/dl` -> `g/dL`, `/cumm` -> `/µL`) | No unit conversion in this milestone - conversions are a source of silent errors. |
| H/L flags | Stored as printed (`abnormal_flag_as_printed`) | We never calculate normal/abnormal ourselves. |
| Plausibility limits | Very wide physical limits per test+unit | Only to catch reading errors (lost decimal point). Not clinical ranges. |
| Validation result | `valid` / `needs_review` / `invalid` + flag codes | Problems are reported, never auto-corrected. |
| Observation ID | Hash of document ID + page + line | Re-running extraction gives the same IDs. |

## Handed to Milestone 4

`app.extraction.extract_observations(doc) -> ExtractionResult`, whose `observations` are
`Observation` models (see `app/extraction/schemas.py`) with patient/document IDs, original and
normalised test names, value/operator/text, units, reference range, observation date and its
source, page/line/evidence provenance, flags and `validation_status`. Suggested rule for storage:
store every observation with its status and flags, but only use `valid` ones for trends and answers
unless a person has reviewed the others. A `patient_id_mismatch` flag must never be ignored.
