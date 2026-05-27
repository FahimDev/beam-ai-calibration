# beam-ai

AI-assisted laser beam alignment support tool for semiconductor lithography FSEs.
Offline R&D phase — no hardware, no production deployment.

## Services & ports

| Port | Service | What it is |
|------|---------|------------|
| **8000** | FastAPI (REST API) | Main application API. Docs at `http://localhost:8000/docs` (Swagger UI) and `/redoc`. |
| **5432** | PostgreSQL 16 + pgvector | Primary database. Connect with any Postgres client (user/pass/db all default to `beam_ai`). |
| **5050** | pgAdmin 4 | Web-based DB browser — no login screen required. Useful for inspecting tables, running ad-hoc SQL. |
| **8888** | JupyterLab | Notebooks for synthetic data generation, feature exploration, and ML training runs. |

> Start everything: `docker compose -f docker/docker-compose.yml up -d`
> DB only: `docker compose -f docker/docker-compose.yml up -d postgres`

---

## Project layout

```
beam_ai/
├── docker/
│   ├── docker-compose.yml
│   ├── Dockerfile.api
│   └── postgres/
│       └── init.sql            # enable pgvector extension
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
├── beam_ai/
│   ├── __init__.py
│   ├── config.py               # settings via pydantic-settings
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py             # engine + SessionLocal
│   │   ├── models.py           # SQLAlchemy ORM (9 entities)
│   │   └── schemas.py          # Pydantic request/response models
│   ├── ledger/
│   │   └── calibration.py      # calibration ledger logic
│   ├── synthetic/
│   │   ├── __init__.py
│   │   ├── beam_generator.py   # BP/BD image generator
│   │   ├── output_generator.py # fake Output features
│   │   ├── condition_generator.py
│   │   ├── evaluation_generator.py
│   │   └── session_builder.py  # full synthetic session factory
│   ├── features/
│   │   └── extractor.py        # COG, size, symmetry, ContM
│   ├── ml/
│   │   ├── baseline_rf.py      # Gen 1 RandomForest
│   │   └── embeddings.py       # Gen 2 placeholder
│   ├── api/
│   │   ├── main.py             # FastAPI app
│   │   └── routers/
│   │       ├── sessions.py
│   │       ├── history.py
│   │       └── ai_results.py
│   └── tests/
│       ├── test_schema.py
│       ├── test_calibration.py
│       └── test_synthetic.py
├── notebooks/
│   ├── 01_synthetic_session.ipynb
│   ├── 02_feature_extraction.ipynb
│   ├── 03_rf_baseline.ipynb
│   └── 04_replay_simulator.ipynb
├── pyproject.toml
├── .env.example
└── README.md
```