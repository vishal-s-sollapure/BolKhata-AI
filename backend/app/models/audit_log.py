"""AuditLog database model for tracking operations in BolKhata AI."""

import uuid
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    event,
    func,
)
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.models.khata_entry import ImmutabilityViolationError


class AuditLog(Base):
    """Immutable audit trail recording financial and administrative ledger events.
    
    SECURITY & COMPLIANCE REQUIREMENTS:
    1. Records transaction creation, duplicate attempts, customer actions, and proposal states.
    2. Does NOT store API keys, credentials, tokens, or raw unverified voice tokens.
    3. Audit logs cannot be modified or deleted once recorded.
    """
    __tablename__ = "audit_logs"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
        doc="Audit log entry UUID",
    )
    store_id = Column(
        String(36),
        ForeignKey("kirana_stores.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Tenant KiranaStore UUID",
    )
    actor_type = Column(
        String(50),
        nullable=False,
        doc="Actor category: 'merchant', 'system', 'api'",
    )
    actor_id = Column(
        String(100),
        nullable=True,
        doc="Optional identifier of the user or terminal performing the action",
    )
    action = Column(
        String(100),
        nullable=False,
        doc="Action name (e.g. TRANSACTION_COMMITTED, DUPLICATE_COMMIT_BLOCKED, CUSTOMER_CREATED)",
    )
    entity_type = Column(
        String(50),
        nullable=False,
        doc="Target entity type (e.g. KhataEntry, Customer, PendingProposal)",
    )
    entity_id = Column(
        String(100),
        nullable=False,
        index=True,
        doc="ID of the affected entity",
    )
    request_id = Column(
        String(100),
        nullable=True,
        doc="Correlated HTTP or client request ID",
    )
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        doc="Timestamp of the audit event",
    )
    metadata_json = Column(
        Text,
        nullable=True,
        doc="Restricted, non-sensitive JSON payload detailing the event",
    )

    # Relationships
    store = relationship("KiranaStore", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_store_timestamp", "store_id", "timestamp"),
        Index("ix_audit_logs_action", "action"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id='{self.id}', store_id='{self.store_id}', "
            f"action='{self.action}', entity='{self.entity_type}:{self.entity_id}')>"
        )


# Immutability Protection: Block ORM-level updates and deletes of audit records
@event.listens_for(AuditLog, "before_update")
def prevent_audit_log_update(mapper, connection, target):
    """Prevents updating audit logs."""
    raise ImmutabilityViolationError(
        f"AuditLog '{target.id}' is immutable and cannot be modified."
    )


@event.listens_for(AuditLog, "before_delete")
def prevent_audit_log_delete(mapper, connection, target):
    """Prevents deleting audit logs."""
    raise ImmutabilityViolationError(
        f"AuditLog '{target.id}' is immutable and cannot be deleted."
    )
