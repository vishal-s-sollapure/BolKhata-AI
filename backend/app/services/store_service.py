"""Store service managing KiranaStore tenants in BolKhata AI."""

import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.kirana_store import KiranaStore
from app.utils.logger import configure_logger

logger = configure_logger("bolkhata.services.store")

# Default Kirana Store ID for local development and rapid bootstrapping
DEFAULT_DEV_STORE_ID = "00000000-0000-0000-0000-000000000001"


class StoreService:
    """Manages KiranaStore records and local development defaults."""

    @staticmethod
    def get_or_create_default_store(db: Session) -> KiranaStore:
        """Retrieves or creates the seeded default Kirana store for development."""
        store = db.query(KiranaStore).filter(KiranaStore.id == DEFAULT_DEV_STORE_ID).first()
        if not store:
            logger.info("Initializing default KiranaStore [%s] for development...", DEFAULT_DEV_STORE_ID)
            store = KiranaStore(
                id=DEFAULT_DEV_STORE_ID,
                store_name="Sri Manjunatha Kirana & General Store",
                owner_name="Basavaraj Patil",
                phone_number="+919876543210",
                preferred_language="kannada",
                is_active=True,
            )
            db.add(store)
            audit = AuditLog(
                id=str(uuid.uuid4()),
                store_id=store.id,
                actor_type="system",
                action="DEFAULT_STORE_SEEDED",
                entity_type="KiranaStore",
                entity_id=store.id,
            )
            db.add(audit)
            db.commit()
            db.refresh(store)
        return store

    @staticmethod
    def get_store(store_id: str, db: Session) -> Optional[KiranaStore]:
        """Fetches a store by its UUID."""
        return db.query(KiranaStore).filter(KiranaStore.id == store_id).first()

    @staticmethod
    def create_store(
        store_name: str,
        owner_name: str,
        phone_number: Optional[str] = None,
        preferred_language: str = "kannada",
        db: Optional[Session] = None,
    ) -> KiranaStore:
        """Creates a new independent Kirana store tenant."""
        if db is None:
            raise ValueError("Database session required.")
        store = KiranaStore(
            id=str(uuid.uuid4()),
            store_name=store_name.strip(),
            owner_name=owner_name.strip(),
            phone_number=phone_number,
            preferred_language=preferred_language,
            is_active=True,
        )
        db.add(store)
        db.commit()
        db.refresh(store)
        return store
