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

## Database migrations

Migrations are managed with Alembic. The DB must be running before any migration command.

```bash
uv run alembic upgrade head          # apply all pending migrations (run this after first clone or after pulling new migrations)
uv run alembic current               # show the current revision applied to the DB
uv run alembic history               # list all revisions
uv run alembic revision --autogenerate -m "description"  # generate a new migration from model changes
uv run alembic downgrade -1          # roll back one revision
```

Migration files live in `alembic/versions/`. Every model change must go through a migration — never edit the DB schema by hand.

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

```
Layer A — OpenCV preprocessing + classical features   
          ├─ COG, size, symmetry, ContM, uniformity
          ├─ Output: 11 numerical features
          └─ Feeds into both classical ML and as side info

Layer B — Pretrained encoder + embedding              
          ├─ DINOv2-small or ResNet50 (pretrained)
          ├─ Output: 384-d or 2048-d embedding vector
          └─ Stored in pgvector for Gen 2 retrieval

Layer C — Classifier head                             
          ├─ Option 1: RandomForest (Gen 1 baseline)
          ├─ Option 2: Logistic regression on embedding
          └─ Output: rank S/A/B/C/D/E + confidence
```

After Heat Map we will be extend our work with the given input types: 
- Gigaphoton DTL logs
- AMP/OSC/Twin beam mode
- BP and BD separation
- Energy Sigma
- Dose/HK
- Wavelength
- F2 pressure
- HV logs
- real FSE adjustment decisions
- final Twin Evaluation from BI Tool


| Term                      | Meaning in This Dataset                      | Related to Our Main Project                |
| ------------------------- | -------------------------------------------- | ------------------------------------------ |
| **Beam Image**            | 2D heatmap/image of laser intensity          | Similar to BP/BD beam image concept        |
| **Pixel Intensity**       | Brightness value of each pixel               | Used to calculate beam shape and center    |
| **Centroid**              | Center of beam intensity                     | Similar to COG: Center of Gravity          |
| **Major Axis Beam Width** | Wider dimension of the beam                  | Similar to BP/BD size                      |
| **Minor Axis Beam Width** | Narrower dimension of the beam               | Similar to BP/BD size                      |
| **Effective Diameter**    | Overall beam diameter estimate               | Beam size/quality indicator                |
| **Ellipticity**           | How circular or oval the beam is             | Beam shape distortion indicator            |
| **Gaussian Fit %**        | How well the beam matches Gaussian shape     | Beam quality measurement                   |
| **Iris Position**         | Optical aperture/control position            | Hardware/control variable                  |
| **Z Position**            | Optical stage position                       | Hardware/control variable                  |
| **Pitch Position**        | Angular alignment setting                    | Similar to mirror adjustment axis          |
| **Yaw Position**          | Angular alignment setting                    | Similar to mirror adjustment axis          |
| **Power Measurement**     | Measured beam power                          | Similar to Energy/Power performance metric |
| **Exposure Time**         | Camera capture setting                       | Calibration/preprocessing concern          |
| **Pairwise Data**         | Two samples compared with a difference count | Useful for similarity/retrieval learning   |
