"""PendingProposal database model for HITL confirmation workflow in BolKhata AI."""

import uuid
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from app.database.session import Base


class PendingProposal(Base):
    """Server-side persisted transaction proposal awaiting merchant confirmation.
    
    HUMAN-IN-THE-LOOP (HITL) INTEGRITY GUARANTEES:
    1. Generated from Groq intent parser output and stored server-side.
    2. Has a strict time-to-live (e.g. 15 minutes) after which it automatically expires.
    3. The ledger engine retrieves this authoritative record on commit; client-supplied
       amounts are NEVER trusted.
    4. Enforces single-commit transitions: PENDING -> COMMITTED or REJECTED.
    """
    __tablename__ = "pending_proposals"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
        doc="Primary key UUID",
    )
    store_id = Column(
        String(36),
        ForeignKey("kirana_stores.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Store scoping foreign key",
    )
    proposal_id = Column(
        String(100),
        nullable=False,
        index=True,
        doc="Authoritative proposal identifier UUID",
    )
    customer_name = Column(
        String(255),
        nullable=False,
        doc="Identified customer name",
    )
    customer_id = Column(
        String(36),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        doc="Resolved customer ID if already linked",
    )
    intent = Column(
        String(50),
        nullable=False,
        doc="Target intent: ADD_CREDIT or RECORD_PAYMENT / LOG_PAYMENT",
    )
    amount = Column(
        Numeric(12, 2),
        nullable=False,
        doc="Monetary amount in INR",
    )
    currency = Column(
        String(3),
        nullable=False,
        default="INR",
        doc="Currency code (INR)",
    )
    summary = Column(
        String(500),
        nullable=False,
        doc="Human-readable description shown to the merchant for confirmation",
    )
    status = Column(
        String(20),
        nullable=False,
        default="PENDING",
        index=True,
        doc="Status: 'PENDING', 'COMMITTED', 'REJECTED', 'EXPIRED'",
    )
    requires_confirmation = Column(
        Boolean,
        nullable=False,
        default=True,
        doc="Always True: requires explicit merchant confirmation",
    )
    khata_entry_id = Column(
        String(36),
        ForeignKey("khata_entries.id", ondelete="SET NULL"),
        nullable=True,
        doc="Associated KhataEntry once committed",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Proposal creation timestamp",
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        doc="Proposal expiration timestamp",
    )
    committed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when merchant confirmed and committed the transaction",
    )
    raw_transcript = Column(
        String(1000),
        nullable=True,
        doc="Original sanitized voice transcription text",
    )

    # Relationships
    store = relationship("KiranaStore", back_populates="pending_proposals")

    __table_args__ = (
        UniqueConstraint("store_id", "proposal_id", name="uq_pending_store_proposal"),
        CheckConstraint("amount > 0", name="chk_pending_positive_amount"),
        CheckConstraint("currency = 'INR'", name="chk_pending_currency_inr"),
        Index("ix_pending_proposals_status_expires", "status", "expires_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<PendingProposal(id='{self.id}', store_id='{self.store_id}', "
            f"proposal_id='{self.proposal_id}', status='{self.status}', amount={self.amount})>"
        )
