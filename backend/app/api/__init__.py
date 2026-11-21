"""API package containing route definitions for BolKhata AI."""

from app.api.health import router as health_router
from app.api.intent import router as intent_router

__all__ = ["health_router", "intent_router"]
