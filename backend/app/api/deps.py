"""FastAPI dependency injection utilities for BolKhata AI."""

from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.kirana_store import KiranaStore
from app.services.store_service import DEFAULT_DEV_STORE_ID, StoreService
from app.utils.logger import configure_logger

logger = configure_logger("bolkhata.api.deps")


def get_current_store(
    x_store_id: Optional[str] = Header(
        None,
        alias="X-Store-Id",
        description="Kirana store tenant UUID. Falls back to default store in dev mode.",
    ),
    db: Session = Depends(get_db),
) -> KiranaStore:
    """Resolves the current KiranaStore tenant context.
    
    SECURITY & MULTI-TENANCY ARCHITECTURE NOTE:
    - In this phase, requests identify their store via the 'X-Store-Id' HTTP header.
    - If 'X-Store-Id' is omitted in development mode, the system defaults to the seeded
      developer store to ensure smooth push-to-talk development.
    - In future production phases, this dependency will be superseded by validated
      merchant JWT authentication.
    """
    store_id = x_store_id or DEFAULT_DEV_STORE_ID

    store = StoreService.get_store(store_id, db)
    if not store:
        # If development store is requested but not yet seeded, seed it on the fly
        if store_id == DEFAULT_DEV_STORE_ID:
            store = StoreService.get_or_create_default_store(db)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"KiranaStore '{store_id}' not found.",
            )

    if not store.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"KiranaStore '{store.store_name}' account is inactive.",
        )

    return store
