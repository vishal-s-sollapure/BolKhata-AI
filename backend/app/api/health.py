"""Health check API endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter
from app.config.settings import get_settings

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health", summary="Service Health Check")
async def health_check():
    """Returns application health status, service name, version, and active environment."""
    return {
        "status": "healthy",
        "service": "bolkhata-backend",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.APP_ENV,
        "languages_supported": settings.SUPPORTED_LANGUAGES,
    }
