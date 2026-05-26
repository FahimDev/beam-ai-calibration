from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from beam_ai.config import settings


engine = create_engine(
    settings.database_url,
    echo=settings.env == "development",
    future=True,
    pool_pre_ping=True,       # recover from dropped connections
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,   # safe for FastAPI response-after-commit
)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session and closes it after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()