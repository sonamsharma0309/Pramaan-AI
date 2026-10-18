# Progress

| Area | Status | Notes |
|---|---|---|
| 835 parser, denial intelligence (CARC/RARC/EOB dataset) | Done | Tested on two bundled fictional sample files |
| Policy RAG (TF-IDF) + optional embeddings | Done | Embeddings path not exercised in CI (large dependency) |
| Evidence mapping, cited letters, honest no-policy state | Done | |
| Claude integration (de-ID, citation guard, retry) | Done | Verified with mocks. Needs a real key for a live run |
| Cookie sessions, refresh rotation, CSRF, 2FA, verification | Done | Covered by tests |
| Patient / Billing / Admin portals | Done | Verified in headless Chromium |
| Watermarked PDF packets, CSV/ZIP export | Done | |
| OCR, DOCX, FHIR, ICD-10 | Done | OCR and FHIR verified with mocks / graceful paths |
| SQLAlchemy + Alembic | Done | SQLite verified. PostgreSQL path not run in the authoring environment |
| Docker / compose / nginx / CI | Written | Docker was not available where this was authored; run `docker compose up --build` once and report issues |
| Win model learns from outcomes | Done | Needs 50 real outcomes (`make train`) |
| Verified payer deadline rules | Open | `appeal_rules.csv` rows must be verified by a human |
| Real payer policies | Open | Bundled policies are fictional |
