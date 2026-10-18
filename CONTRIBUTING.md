# Contributing to Pramaan AI

Thanks for helping. This is a student project that aims to follow industry practice, so changes should be small, tested and explained.

## Setup
```bash
git clone <your-fork-url> && cd pramaan-ai
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
pre-commit install
make dev                                                # http://localhost:8000
```

## Workflow
1. Create a branch: `feat/short-name`, `fix/short-name` or `docs/short-name`.
2. Make the change. Keep functions small and add type hints and a docstring to anything in `backend/services`.
3. Add or update tests. `make test` must pass. Mock every external service (Claude, SMTP, FHIR, NLM, Google); tests must never need network or keys.
4. `make lint` must be clean (ruff).
5. Open a pull request using the checklist below.

## Commit convention
`type: short summary` where type is one of `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`. Example: `fix: ignore generic appeal standards when extracting criteria`.

## Pull request checklist
- [ ] Tests added or updated, `make test` passes
- [ ] `make lint` passes
- [ ] No secrets, real patient data or `.env` committed
- [ ] Any new setting is documented in `.env.example` and README
- [ ] User-facing text avoids medical or legal claims; estimates are labelled as estimates
- [ ] Database change includes an Alembic migration (`alembic revision -m "..."`)
- [ ] CHANGELOG.md updated

## Rules that protect users
- Never commit real PHI. Demo data must be clearly fictional.
- Anything that sends text to an external API must go through `services/deid.py` first.
- LLM output must pass the citation guard in `services/appeal_gen.py`.
- Do not present synthetic or placeholder numbers as measured results.
