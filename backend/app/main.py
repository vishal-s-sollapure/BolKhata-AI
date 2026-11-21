"""Main FastAPI application entrypoint for BolKhata AI."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import get_settings
from app.api.health import router as health_router
from app.utils.logger import configure_logger

settings = get_settings()
logger = configure_logger("bolkhata.main", log_level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    logger.info("Starting %s in [%s] mode...", settings.APP_NAME, settings.APP_ENV)
    logger.info("Host: %s:%d", settings.APP_HOST, settings.APP_PORT)
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
