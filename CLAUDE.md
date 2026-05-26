# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project identity
AI-assisted laser beam alignment support tool for semiconductor lithography FSEs.
Offline R&D phase. No hardware. No production deployment yet.

## Commands

### Environment setup
```bash
uv sync                        # install all deps (including dev)
cp .env.example .env           # first-time setup
```

### Docker services
```bash
docker compose -f docker/docker-compose.yml up -d postgres     # DB only
docker compose -f docker/docker-compose.yml up -d              # full stack (postgres + api + jupyter)
docker compose -f docker/docker-compose.yml down
```

### Database migrations
```bash
uv run alembic upgrade head                                     # apply all migrations
uv run alembic revision --autogenerate -m "description"        # generate new migration
uv run alembic downgrade -1                                     # roll back one step
```

### Running the API locally (DB must be running)
```bash
uv run uvicorn beam_ai.api.main:app --reload
```

### Lint and format
```bash
uv run ruff check .            # lint
uv run ruff format .           # format (Black-compatible, line length 100)
```

### Tests
```bash
uv run pytest                              # all tests
uv run pytest beam_ai/tests/test_foo.py   # single file
uv run pytest beam_ai/tests/test_foo.py::test_bar_function   # single test
uv run pytest -x                           # stop on first failure
```

## Architecture

### Stack
- FastAPI + SQLAlchemy 2.0 + PostgreSQL 16 + pgvector
- Pydantic v2 for all validation, pydantic-settings for config
- uv for package management; Docker Compose for services; Alembic for migrations

### Settings
`beam_ai/config.py` exposes a singleton `settings` object (pydantic-settings). It reads from `.env` and provides `DATABASE_URL`, `IMAGE_STORE_PATH`, `DEFAULT_CALIBRATION_VALIDITY_DAYS`, and `AI_MODEL_VERSION`. All modules import from here — never hardcode these values.

### Data model (entity relationships)
The central record is **HistoryItem** — every snapshot of beam state hangs off it:

```
MeasuringDevice ──< CameraCalibration

Session ──< HistoryItem ──< BeamImage   (one per camera type: BP / BD)
                        ──< Output      (extracted numeric features per camera)
                        ──  Condition   (camera settings at capture time; 1:1)
                        ──  Evaluation  (OK/NG score; only exists when beam_mode == TWIN)
                        ──  AIAnalysisResult  (model output; 1:1)
```

All PKs are ULIDs (strings). Alembic's `env.py` imports `beam_ai.db.models` to register models for autogenerate — any new model must be importable from that module.

### Calibration gate
`gate_ai_result()` in `beam_ai/ledger/calibration.py` must be called before committing any `AIAnalysisResult`. It sets `recommendation_mode` and `safety_status` based on the current `CalibrationStatus`. Never write to `AIAnalysisResult` without going through this gate.

### AI output lifecycle
All AI outputs default to `recommendation_mode=SHADOW_ONLY`. The mode can only reach `FSE_REVIEW` via an explicit human action in the UI — code must never set it. Recommendations are suppressed (`mode=NONE`) whenever `calibration_status` is not `VALID`.

### Synthetic data pipeline
`beam_ai/synthetic/` generates fake sessions for offline training:
- `beam_generator.py` → synthetic BP/BD images
- `output_generator.py` + `condition_generator.py` + `evaluation_generator.py` → fake feature rows
- `session_builder.py` → orchestrates a full synthetic session

Synthetic rows must always carry `session_type=synthetic` or `save_trigger=synthetic`. Never mix synthetic and real data without this tag.

### ML
Gen 1 is a single RandomForest in `beam_ai/ml/baseline_rf.py`. `beam_ai/ml/embeddings.py` is a Gen 2 placeholder — do not implement until Gen 1 is validated. No LLM calls or vector DB until then.

## Spec-Driven Development workflow
All features follow: **spec → review → implement → test → commit**

1. Every feature starts with a spec file in `specs/` (subdirs: `entities/`, `features/`, `api/`, `ml/`).
2. Spec is reviewed and approved before implementation starts.
3. Implementation must match the spec exactly. No scope creep.
4. Tests are written alongside implementation, not after.
5. Commit only when tests pass.

Each spec must include: Purpose, Inputs/Outputs, Constraints, Assumptions, Acceptance criteria, Out of scope.

## Critical rules — never break these

### Data rules
- Evaluation rows only exist when `beam_mode == TWIN`. Reject all others.
- `AIAnalysisResult.recommendation_mode` is never set to `FSE_REVIEW` by code — only by a human FSE action in the UI.
- `gate_ai_result()` in `beam_ai/ledger/calibration.py` MUST be called before any `AIAnalysisResult` is committed.
- All image writes go to `IMAGE_STORE_PATH` (from settings), never hardcoded paths.
- All IDs use ULID (`python-ulid`). Never use sequential integers as IDs.

### Safety rules
- No hardware control code. Ever. This tool is advisory only.
- No adjustment recommendation may be shown unless `calibration_status == VALID`.
- `recommendation_mode=NONE` when calibration is expired or unknown.
- All AI outputs are `SHADOW_ONLY` until explicit FSE review flag is set.

### ML rules
- Gen 1 model: RandomForest from `beam_ai/ml/baseline_rf.py` only.
- Do not add LLM calls or Vector DB until Gen 1 baseline is validated.
- Synthetic data must be clearly tagged: `session_type=synthetic` or `save_trigger=synthetic`.

### Code style
- Black-compatible formatting via ruff (line length 100).
- Type hints on all public functions.
- Docstrings only on public API functions and complex logic.
- No `print()` — use Python `logging`.
- Tests required for: all ledger logic, all schema invariants, all synthetic generators, all feature extractors.

## Confirmed unknowns — do not invent these
- Exact BP/BD image resolution and format
- Exact formula for COG, size, ContM
- Exact calibration validity period (using 90 days as placeholder)
- Safe AFM/OBS movement limits
- S/A/B/C/D/E scoring thresholds from real data
- BI Tool export format

## Do not rebuild these (already exist in BI Tool)
Session model, History model, Compare, Restore, Beam Mode switching,
Camera Calibration alert flow, Best Practices, Summary/BP/BD views.
