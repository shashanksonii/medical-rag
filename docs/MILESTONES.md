# Project milestone checklist

Status legend: `[x]` implemented and verified, `[~]` in progress, `[ ]` not started.

- [x] **Milestone 1 - Project foundation** (repo structure, dependencies, FastAPI app, config, logging, `/health`, tests, README)
- [ ] Milestone 2 - Document ingestion (PyMuPDF, Tesseract OCR + Pillow, page-level provenance)
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
