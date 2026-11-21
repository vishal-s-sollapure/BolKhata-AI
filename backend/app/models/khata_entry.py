"""KhataEntry database model representing the immutable financial ledger in BolKhata AI."""

import uuid
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import relationship
from app.database.session import Base


class ImmutabilityViolationError(Exception):
    """Raised when an attempt is made to update or delete an immutable ledger entry or audit record."""
    pass


class KhataEntry(Base):
    """Immutable, append-only financial ledger entry.
    
    CRITICAL FINANCIAL SAFETY INVARIANTS:
    1. Financial amounts must NEVER use float; Numeric(12, 2) is enforced.
    2. CREDIT strictly increases outstanding customer credit.
    3. PAYMENT strictly decreases outstanding customer credit.
    4. Amounts must be strictly greater than zero (positive).
    5. Currency must be strictly 'INR'.
    6. Entries are immutable once written; updates and deletes are forbidden.
    7. Idempotency key is unique per store scope.
    """
    __tablename__ = "khata_entries"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
        doc="Ledger transaction UUID",
    )
    store_id = Column(
        String(36),
        ForeignKey("kirana_stores.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Tenant KiranaStore UUID",
    )
    customer_id = Column(
        String(36),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Customer UUID",
    )
    entry_type = Column(
        String(20),
        nullable=False,
        index=True,
        doc="Transaction type: 'CREDIT' or 'PAYMENT'",
    )
    amount = Column(
        Numeric(12, 2),
        nullable=False,
        doc="Monetary amount in INR (strictly positive, 2 decimal places)",
    )
    currency = Column(
        String(3),
        nullable=False,
        default="INR",
        doc="Currency code (strictly 'INR')",
    )
    description = Column(
        String(500),
        nullable=True,
        doc="Optional merchant notes or purchased items description",
    )
    reference_id = Column(
        String(100),
        nullable=True,
        doc="External invoice, bill number, or receipt reference",
    )
    idempotency_key = Column(
        String(100),
        nullable=False,
        index=True,
        doc="Unique idempotency key preventing duplicate ledger commits",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        doc="Immutable creation timestamp",
    )
    created_by = Column(
        String(100),
        nullable=False,
        default="merchant",
        doc="Actor responsible for creating the entry",
    )
    proposal_id = Column(
        String(100),
        nullable=True,
        index=True,
        doc="Associated HITL TransactionProposal UUID (if originating from voice intent)",
    )
    metadata_json = Column(
        Text,
        nullable=True,
        doc="Restricted, non-sensitive JSON metadata (e.g. speech language, confidence)",
    )

    # Relationships
    store = relationship("KiranaStore", back_populates="khata_entries")
    customer = relationship("Customer", back_populates="khata_entries")

    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_khata_positive_amount"),
        CheckConstraint("currency = 'INR'", name="chk_khata_currency_inr"),
        CheckConstraint("entry_type IN ('CREDIT', 'PAYMENT')", name="chk_khata_entry_type"),
        UniqueConstraint("store_id", "idempotency_key", name="uq_khata_store_idempotency"),
        Index("ix_khata_store_customer_created", "store_id", "customer_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<KhataEntry(id='{self.id}', store_id='{self.store_id}', "
            f"customer_id='{self.customer_id}', type='{self.entry_type}', amount={self.amount})>"
        )


# Immutability Protection: Block ORM-level updates and deletes
@event.listens_for(KhataEntry, "before_update")
def prevent_khata_entry_update(mapper, connection, target):
    """Enforces append-only immutability by blocking any updates to KhataEntry."""
    raise ImmutabilityViolationError(
        f"KhataEntry '{target.id}' is immutable and cannot be updated. "
        "Financial ledger records are append-only."
    )


@event.listens_for(KhataEntry, "before_delete")
def prevent_khata_entry_delete(mapper, connection, target):
    """Enforces append-only immutability by blocking any deletes of KhataEntry."""
    raise ImmutabilityViolationError(
        f"KhataEntry '{target.id}' is immutable and cannot be deleted. "
        "Financial ledger records are append-only."
    )
