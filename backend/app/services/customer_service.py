"""Customer service managing customer lifecycle and lookup in BolKhata AI."""

import uuid
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ledger.exceptions import CustomerNotFoundError, InactiveCustomerError, StoreNotFoundError
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.kirana_store import KiranaStore
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.utils.logger import configure_logger

logger = configure_logger("bolkhata.services.customer")


class CustomerService:
    """Manages customer records under a store tenant."""

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalizes customer name for consistent searching."""
        return name.strip().lower()

    def get_customer(self, store_id: str, customer_id: str, db: Session) -> Customer:
        """Fetches a customer verifying store ownership."""
        customer = (
            db.query(Customer)
            .filter(Customer.id == customer_id, Customer.store_id == store_id)
            .first()
        )
        if not customer:
            raise CustomerNotFoundError(
                f"Customer '{customer_id}' not found in store '{store_id}'."
            )
        return customer

    def create_customer(
        self,
        store_id: str,
        data: CustomerCreate,
        db: Session,
    ) -> Customer:
        """Creates a new customer record under a store."""
        # Verify store exists
        store = db.query(KiranaStore).filter(KiranaStore.id == store_id).first()
        if not store:
            raise StoreNotFoundError(f"Store '{store_id}' does not exist.")

        normalized = self.normalize_name(data.customer_name)

        # Check for potential accidental duplicate (same normalized name and same phone)
        existing_query = db.query(Customer).filter(
            Customer.store_id == store_id,
            Customer.normalized_name == normalized,
        )
        if data.phone_number:
            existing_query = existing_query.filter(Customer.phone_number == data.phone_number)
            existing = existing_query.first()
            if existing:
                if not existing.is_active:
                    # Reactivate customer
                    existing.is_active = True
                    db.commit()
                    db.refresh(existing)
                    return existing
                return existing

        customer = Customer(
            id=str(uuid.uuid4()),
            store_id=store_id,
            customer_name=data.customer_name.strip(),
            normalized_name=normalized,
            phone_number=data.phone_number,
            is_active=True,
        )
        db.add(customer)

        audit = AuditLog(
            id=str(uuid.uuid4()),
            store_id=store_id,
            actor_type="merchant",
            action="CUSTOMER_CREATED",
            entity_type="Customer",
            entity_id=customer.id,
        )
        db.add(audit)
        db.commit()
        db.refresh(customer)
        return customer

    def list_customers(
        self,
        store_id: str,
        db: Session,
        query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        include_inactive: bool = False,
    ) -> List[Customer]:
        """Lists customers in a store with optional search."""
        q = db.query(Customer).filter(Customer.store_id == store_id)
        if not include_inactive:
            q = q.filter(Customer.is_active == True)
        if query and query.strip():
            term = f"%{query.strip().lower()}%"
            q = q.filter(
                (Customer.normalized_name.ilike(term)) | (Customer.phone_number.ilike(term))
            )
        return q.order_by(Customer.customer_name.asc()).offset(offset).limit(limit).all()

    def update_customer(
        self,
        store_id: str,
        customer_id: str,
        data: CustomerUpdate,
        db: Session,
    ) -> Customer:
        """Updates customer metadata (soft-deletes if is_active=False)."""
        customer = self.get_customer(store_id, customer_id, db)
        if data.customer_name is not None:
            customer.customer_name = data.customer_name.strip()
            customer.normalized_name = self.normalize_name(data.customer_name)
        if data.phone_number is not None:
            customer.phone_number = data.phone_number
        if data.is_active is not None:
            customer.is_active = data.is_active

        audit = AuditLog(
            id=str(uuid.uuid4()),
            store_id=store_id,
            actor_type="merchant",
            action="CUSTOMER_UPDATED",
            entity_type="Customer",
            entity_id=customer.id,
        )
        db.add(audit)
        db.commit()
        db.refresh(customer)
        return customer
