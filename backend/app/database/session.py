"""Database configuration and session management using SQLAlchemy."""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config.settings import get_settings

settings = get_settings()

# Configure SQLite engine with thread check disabled for FastAPI async concurrency
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG and not settings.is_production,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session and ensures it closes after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
