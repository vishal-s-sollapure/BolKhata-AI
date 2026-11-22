"""Main FastAPI application entrypoint for BolKhata AI."""

import os
import sys

# Ensure backend directory is in sys.path so 'app' can be imported from any working directory (e.g. Render/Docker root)
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import get_settings
from app.database.session import Base, SessionLocal, engine, init_db_triggers
import app.models  # Registers all SQLAlchemy models with Base.metadata
from app.services.store_service import StoreService
from app.api.health import router as health_router
from app.api.intent import router as intent_router
from app.api.customers import router as customers_router
from app.api.ledger import router as ledger_router
from app.api.voice import router as voice_router
from app.utils.logger import configure_logger

settings = get_settings()
logger = configure_logger("bolkhata.main", log_level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    logger.info("Starting %s in [%s] mode...", settings.APP_NAME, settings.APP_ENV)
    logger.info("Host: %s:%d", settings.APP_HOST, settings.APP_PORT)

    # Initialize database tables, immutability triggers, and seed development store
    try:
        Base.metadata.create_all(bind=engine)
        init_db_triggers(engine)
        with SessionLocal() as db:
            StoreService.get_or_create_default_store(db)
        logger.info("Database initialized successfully with immutability triggers.")
    except Exception as e:
        logger.error("Failed to initialize database tables: %s", str(e))

    yield
    logger.info("Shutting down %s...", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description="Multilingual voice-based digital ledger for Indian kirana stores. "
                "Tagline: 'Your Kirana Store. Your Voice. Your Digital Khata.'",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health_router, prefix="")
app.include_router(health_router, prefix="/api")
app.include_router(intent_router, prefix="/api")
app.include_router(intent_router, prefix="/api/v1")
app.include_router(customers_router, prefix="/api/v1")
app.include_router(ledger_router, prefix="/api/v1")
app.include_router(voice_router, prefix="/api")
app.include_router(voice_router, prefix="/api/v1")


@app.get("/", summary="Root API Information")
async def root():
    """Returns basic service identification and links to documentation and health status."""
    return {
        "service": settings.APP_NAME,
        "tagline": "Your Kirana Store. Your Voice. Your Digital Khata.",
        "status": "online",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }



@app.get("/", summary="Root API Information")
async def root():
    """Returns basic service identification and links to documentation and health status."""
    return {
        "service": settings.APP_NAME,
        "tagline": "Your Kirana Store. Your Voice. Your Digital Khata.",
        "status": "online",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
