"""Database configuration and session management using SQLAlchemy."""

import sqlite3
from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
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


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforces SQLite foreign key constraints on every connection."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db_triggers(target_engine: Engine) -> None:
    """Installs database-level triggers enforcing append-only immutability.
    
    Prevents direct SQL UPDATE/DELETE statements or bulk ORM mutations from
    bypassing application-level event listeners.
    """
    if str(target_engine.url).startswith("sqlite"):
        with target_engine.connect() as conn:
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_prevent_khata_entry_update
                BEFORE UPDATE ON khata_entries
                BEGIN
                    SELECT RAISE(ABORT, 'KhataEntry is append-only and cannot be updated.');
                END;
            """))
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_prevent_khata_entry_delete
                BEFORE DELETE ON khata_entries
                BEGIN
                    SELECT RAISE(ABORT, 'KhataEntry is append-only and cannot be deleted.');
                END;
            """))
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_prevent_audit_log_update
                BEFORE UPDATE ON audit_logs
                BEGIN
                    SELECT RAISE(ABORT, 'AuditLog is append-only and cannot be updated.');
                END;
            """))
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_prevent_audit_log_delete
                BEFORE DELETE ON audit_logs
                BEGIN
                    SELECT RAISE(ABORT, 'AuditLog is append-only and cannot be deleted.');
                END;
            """))
            conn.commit()


@event.listens_for(Base.metadata, "after_create")
def setup_triggers_after_create(target, connection, **kw):
    """Automatically installs SQLite triggers whenever tables are created."""
    if connection.dialect.name == "sqlite":
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_prevent_khata_entry_update
            BEFORE UPDATE ON khata_entries
            BEGIN
                SELECT RAISE(ABORT, 'KhataEntry is append-only and cannot be updated.');
            END;
        """))
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_prevent_khata_entry_delete
            BEFORE DELETE ON khata_entries
            BEGIN
                SELECT RAISE(ABORT, 'KhataEntry is append-only and cannot be deleted.');
            END;
        """))
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_prevent_audit_log_update
            BEFORE UPDATE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'AuditLog is append-only and cannot be updated.');
            END;
        """))
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_prevent_audit_log_delete
            BEFORE DELETE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'AuditLog is append-only and cannot be deleted.');
            END;
        """))


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session and ensures it closes after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


