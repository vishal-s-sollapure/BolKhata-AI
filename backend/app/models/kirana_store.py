"""KiranaStore database model representing the retail merchant tenant in BolKhata AI."""

import uuid
from sqlalchemy import Boolean, Column, DateTime, String, func
from sqlalchemy.orm import relationship
from app.database.session import Base


class KiranaStore(Base):
    """Represents a Kirana retail store (tenant).
    
    All customer records, ledger transactions, proposals, and audit logs are
    strictly scoped to a specific KiranaStore.
    """
    __tablename__ = "kirana_stores"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
        doc="Unique store UUID identifier",
    )
    store_name = Column(
        String(255),
        nullable=False,
        doc="Business name of the Kirana store",
    )
    owner_name = Column(
        String(255),
        nullable=False,
        doc="Name of the store owner / merchant",
    )
    phone_number = Column(
        String(20),
        nullable=True,
        index=True,
        doc="Contact phone number of the merchant",
    )
    preferred_language = Column(
        String(20),
        nullable=False,
        default="kannada",
        doc="Default merchant language (kannada, hindi, english)",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether the store account is currently active",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Store creation timestamp",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Last updated timestamp",
    )

    # Relationships (NEVER cascade delete financial history)
    customers = relationship(
        "Customer",
        back_populates="store",
        cascade="none",
        doc="Customers belonging to this store",
    )
    khata_entries = relationship(
        "KhataEntry",
        back_populates="store",
        cascade="none",
        doc="Ledger entries recorded by this store",
    )
    audit_logs = relationship(
        "AuditLog",
        back_populates="store",
        cascade="none",
        doc="Audit logs for this store",
    )
    pending_proposals = relationship(
        "PendingProposal",
        back_populates="store",
        cascade="none",
        doc="Pending proposals awaiting merchant confirmation",
    )

    def __repr__(self) -> str:
        return f"<KiranaStore(id='{self.id}', name='{self.store_name}', owner='{self.owner_name}')>"
