# Changelog

All notable changes to Pramaan AI. Format follows [Keep a Changelog](https://keepachangelog.com/) and the project uses [Semantic Versioning](https://semver.org/).

## [2.0.0] - 2026-10-04

### Added
- **Dynamic frontend**: home page content, stats, FAQ, team and feature lists come from `GET /api/site/content`; live counters from `GET /api/public/stats`; payer, denial-code, procedure and ICD-10 dropdowns/autocomplete come from the API.
- **Dashboard** with Chart.js (denied vs recovered, win rate by category, status mix, top codes) and date-range + payer filters.
- **Claims table** with server-side search, filters, sort, pagination, deadline badges and bulk analyse / bulk appeal.
- **Appeal workspace**: letter | cited policy clauses | chart evidence, clickable `[P#]`/`[E#]` citations, autosave, regenerate, win-probability factors.
- **Claim timeline** (audit trail per claim), notifications bell (deadline reminders and status changes), dark mode saved per user.
- **Reference data**: CARC/RARC/EOB dataset (93 / 197 / 1,873 entries), CO/PR/OA/PI/CR group codes, payer appeal deadline rules (`appeal_rules.csv`, unverified rows are labelled).
- **Watermarked PDF packets**: tiled "PRAMAAN AI" watermark on every page, packet ID and footer on every page.
- OCR for scanned PDFs (Tesseract + Poppler, graceful message when missing), `.docx` uploads, FHIR R4 import (feature flag), ICD-10 lookup (NLM API, cached).
- Per-organisation policy libraries with invite codes; shared library is read-only. Honest "no policy found" letter state.
- Optional semantic retrieval (`EMBEDDINGS=true`) blended with TF-IDF.
- CSV exports (claims, outcomes) and ZIP of all PDF packets.
- Outcome learning: `scripts/train_predictor.py` retrains the win model from real outcomes (>= 50); UI labels estimates "synthetic" until then.
- Admin console (users, contact messages, audit log, system health) and `scripts/create_admin.py`.
- Optional TOTP two-factor authentication with QR code; optional email verification (`REQUIRE_VERIFIED`).
- Contact / partner form that stores the message and emails `CONTACT_TO`.
- SQLAlchemy 2.0 + Alembic (SQLite default, PostgreSQL via `DATABASE_URL`), Dockerfile, docker-compose (app + PostgreSQL + optional nginx), `run.sh`, `run.bat`, Makefile, GitHub Actions CI, ruff, pre-commit.
- 53 automated tests (auth, CSRF, refresh rotation/replay, isolation, parser, RAG, evidence, PDF watermark, de-identification, citation guard, exports, admin, mocked Claude/SMTP/FHIR/NLM).

### Changed
- Sessions moved from `localStorage` JWTs to httpOnly cookies: 15-minute access token, rotating 7-day refresh token, double-submit CSRF. Replaying an old refresh token revokes all sessions of that user.
- PHI is de-identified before any text is sent to Claude, and the reply is re-personalised. Letters citing sources that were not retrieved are discarded in favour of the template. Transient API errors retry with exponential backoff.
- Content-Security-Policy, request IDs, configurable per-IP rate limits, strict CORS, SSRF guard on server-side fetches, upload type/size validation, audit log.
- `DEV_MODE` now defaults to `false`.

### Fixed
- Criteria extraction no longer treats generic appeal-standards text as a payer coverage criterion.
- Patient-responsibility and contractual adjustments are never drafted as appeals.

## [1.0.0] - 2026-09-30
- First working version: 835 parser, RAG policy retrieval, evidence mapping, cited appeal letters, patient and billing portals, JWT authentication.
