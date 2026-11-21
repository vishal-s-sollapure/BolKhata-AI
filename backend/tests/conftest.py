"""Shared Pytest fixtures for BolKhata AI backend test suite."""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import sqlite3

from app.database.session import Base, get_db
import app.models  # Ensure all models are registered
from app.main import app
from app.models.kirana_store import KiranaStore
from app.models.customer import Customer
from app.services.store_service import DEFAULT_DEV_STORE_ID


@pytest.fixture(scope="function")
def db_session():
    """Provides an isolated, in-memory SQLite database session for each test function."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)
    from app.database.session import init_db_triggers
    init_db_triggers(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def test_store(db_session: Session) -> KiranaStore:
    """Creates an active test KiranaStore."""
    store = KiranaStore(
        id=DEFAULT_DEV_STORE_ID,
        store_name="Sri Manjunatha Kirana Store",
        owner_name="Basavaraj Patil",
        phone_number="+919876543210",
        preferred_language="kannada",
        is_active=True,
    )
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)
    return store


@pytest.fixture(scope="function")
def test_customer(db_session: Session, test_store: KiranaStore) -> Customer:
    """Creates a sample active customer under the test store."""
    customer = Customer(
        id=str(uuid.uuid4()),
        store_id=test_store.id,
        customer_name="Ramesh Kumar",
        normalized_name="ramesh kumar",
        phone_number="+919988776655",
        is_active=True,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture(scope="function")
def client(db_session: Session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
