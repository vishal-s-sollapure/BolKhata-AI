"""Tests for FastAPI health check and root endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """TestClient fixture for FastAPI."""
    with TestClient(app) as test_client:
        yield test_client


def test_root_endpoint(client: TestClient):
    """Verify root endpoint returns correct service metadata and tagline."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "BolKhata AI"
    assert "Your Kirana Store. Your Voice. Your Digital Khata." in data["tagline"]
    assert data["status"] == "online"
    assert data["version"] == "0.1.0"


def test_health_endpoint(client: TestClient):
    """Verify /health endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "bolkhata-backend"
    assert "environment" in data
    assert "timestamp" in data
    assert "languages_supported" in data
    assert "kannada" in data["languages_supported"]
    assert "hindi" in data["languages_supported"]
    assert "english" in data["languages_supported"]


def test_api_health_endpoint(client: TestClient):
    """Verify /api/health endpoint is also mounted and functional."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
