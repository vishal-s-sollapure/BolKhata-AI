"""Customer database model representing store clients in BolKhata AI."""

import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import relationship
from app.database.session import Base


class Customer(Base):
    """Represents a customer of a Kirana store.
    
    A customer strictly belongs to exactly one KiranaStore.
    Financial history associated with a customer is NEVER cascade deleted.
    """
    __tablename__ = "customers"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
        doc="Customer UUID identifier",
    )
    store_id = Column(
        String(36),
        ForeignKey("kirana_stores.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="KiranaStore foreign key",
    )
    customer_name = Column(
        String(255),
        nullable=False,
        doc="Original customer name as entered or recognized",
    )
    normalized_name = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Lowercased, stripped, canonical customer name for searching",
    )
    phone_number = Column(
        String(20),
        nullable=True,
        index=True,
        doc="Customer mobile number",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        doc="Soft-deletion flag. False indicates an inactive customer.",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Creation timestamp",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Last updated timestamp",
    )

    # Relationships
    store = relationship(
        "KiranaStore",
        back_populates="customers",
    )
    khata_entries = relationship(
        "KhataEntry",
        back_populates="customer",
        cascade="none",
        doc="Append-only ledger entries for this customer",
    )

    __table_args__ = (
        Index("ix_customers_store_normalized", "store_id", "normalized_name"),
        Index("ix_customers_store_phone", "store_id", "phone_number"),
    )

    def __repr__(self) -> str:
        return f"<Customer(id='{self.id}', store_id='{self.store_id}', name='{self.customer_name}', active={self.is_active})>"
