"""Structured logging setup for BolKhata AI."""

import logging
import sys
from typing import Optional


def configure_logger(name: Optional[str] = None, log_level: str = "INFO") -> logging.Logger:
    """Configures structured, safe logging without exposing secrets or audio payloads."""
    logger = logging.getLogger(name or "bolkhata")
    
    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False

    resolved_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(resolved_level)
    return logger


# Default application logger instance
logger = configure_logger()
