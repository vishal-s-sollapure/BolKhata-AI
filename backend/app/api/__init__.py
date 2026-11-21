"""API package containing route definitions for BolKhata AI."""

from app.api.health import router as health_router
from app.api.intent import router as intent_router
from app.api.customers import router as customers_router
from app.api.ledger import router as ledger_router

__all__ = [
    "health_router",
    "intent_router",
    "customers_router",
    "ledger_router",
]

