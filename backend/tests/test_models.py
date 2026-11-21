"""Unit tests for SQLAlchemy models, constraints, and immutability in BolKhata AI."""

import uuid
from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.khata_entry import ImmutabilityViolationError, KhataEntry
from app.models.kirana_store import KiranaStore
from app.models.pending_proposal import PendingProposal


class TestDatabaseModels:
    """Tests for model creation, constraints, foreign keys, and immutability."""

    def test_kirana_store_creation(self, db_session: Session):
        store = KiranaStore(
            id=str(uuid.uuid4()),
            store_name="Lakshmi Provision Store",
            owner_name="Suresh Gowda",
            phone_number="+919845012345",
            preferred_language="kannada",
            is_active=True,
        )
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)

        assert store.id is not None
        assert store.store_name == "Lakshmi Provision Store"
        assert store.is_active is True
        assert store.created_at is not None

    def test_customer_creation_with_foreign_key(self, db_session: Session, test_store: KiranaStore):
        customer = Customer(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            customer_name="Anand Sharma",
            normalized_name="anand sharma",
            phone_number="+919876543210",
            is_active=True,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        assert customer.id is not None
        assert customer.store_id == test_store.id
        assert customer.customer_name == "Anand Sharma"
        assert customer.is_active is True

    def test_customer_foreign_key_violation(self, db_session: Session):
        """Creating customer with invalid store_id fails due to foreign key constraint."""
        invalid_store_id = str(uuid.uuid4())
        customer = Customer(
            id=str(uuid.uuid4()),
            store_id=invalid_store_id,
            customer_name="Orphan Customer",
            normalized_name="orphan customer",
        )
        db_session.add(customer)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_khata_entry_creation_credit(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        entry = KhataEntry(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            customer_id=test_customer.id,
            entry_type="CREDIT",
            amount=Decimal("340.00"),
            currency="INR",
            idempotency_key="idem_001",
            created_by="merchant",
        )
        db_session.add(entry)
        db_session.commit()
        db_session.refresh(entry)

        assert entry.id is not None
        assert entry.entry_type == "CREDIT"
        assert Decimal(str(entry.amount)) == Decimal("340.00")
        assert entry.currency == "INR"

    def test_khata_entry_creation_payment(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        entry = KhataEntry(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            customer_id=test_customer.id,
            entry_type="PAYMENT",
            amount=Decimal("200.00"),
            currency="INR",
            idempotency_key="idem_002",
            created_by="merchant",
        )
        db_session.add(entry)
        db_session.commit()
        db_session.refresh(entry)

        assert entry.entry_type == "PAYMENT"
        assert Decimal(str(entry.amount)) == Decimal("200.00")

    def test_khata_entry_zero_amount_rejected(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Zero amount must violate CheckConstraint 'chk_khata_positive_amount'."""
        entry = KhataEntry(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            customer_id=test_customer.id,
            entry_type="CREDIT",
            amount=Decimal("0.00"),
            currency="INR",
            idempotency_key="idem_zero",
        )
        db_session.add(entry)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_khata_entry_negative_amount_rejected(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Negative amount must violate CheckConstraint."""
        entry = KhataEntry(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            customer_id=test_customer.id,
            entry_type="CREDIT",
            amount=Decimal("-50.00"),
            currency="INR",
            idempotency_key="idem_negative",
        )
        db_session.add(entry)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_khata_entry_invalid_currency_rejected(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Non-INR currency must violate CheckConstraint 'chk_khata_currency_inr'."""
        entry = KhataEntry(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            customer_id=test_customer.id,
            entry_type="CREDIT",
            amount=Decimal("100.00"),
            currency="USD",
            idempotency_key="idem_usd",
        )
        db_session.add(entry)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_khata_entry_duplicate_idempotency_key_rejected(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Duplicate (store_id, idempotency_key) must violate UniqueConstraint."""
        key = "idem_unique_test"
        entry1 = KhataEntry(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            customer_id=test_customer.id,
            entry_type="CREDIT",
            amount=Decimal("100.00"),
            currency="INR",
            idempotency_key=key,
        )
        db_session.add(entry1)
        db_session.commit()

        entry2 = KhataEntry(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            customer_id=test_customer.id,
            entry_type="CREDIT",
            amount=Decimal("200.00"),
            currency="INR",
            idempotency_key=key,
        )
        db_session.add(entry2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_khata_entry_immutability_update_prevented(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Modifying an existing KhataEntry must be blocked by ImmutabilityViolationError."""
        entry = KhataEntry(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            customer_id=test_customer.id,
            entry_type="CREDIT",
            amount=Decimal("150.00"),
            currency="INR",
            idempotency_key="idem_immutable_upd",
        )
        db_session.add(entry)
        db_session.commit()

        # Attempt to modify amount
        entry.amount = Decimal("300.00")
        with pytest.raises(ImmutabilityViolationError, match="immutable and cannot be updated"):
            db_session.commit()
        db_session.rollback()

    def test_khata_entry_immutability_delete_prevented(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Deleting an existing KhataEntry must be blocked by ImmutabilityViolationError."""
        entry = KhataEntry(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            customer_id=test_customer.id,
            entry_type="CREDIT",
            amount=Decimal("250.00"),
            currency="INR",
            idempotency_key="idem_immutable_del",
        )
        db_session.add(entry)
        db_session.commit()

        # Attempt to delete
        db_session.delete(entry)
        with pytest.raises(ImmutabilityViolationError, match="immutable and cannot be deleted"):
            db_session.commit()
        db_session.rollback()

    def test_audit_log_creation_and_immutability(
        self,
        db_session: Session,
        test_store: KiranaStore,
    ):
        audit = AuditLog(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            actor_type="merchant",
            action="TEST_ACTION",
            entity_type="TestEntity",
            entity_id="entity_123",
        )
        db_session.add(audit)
        db_session.commit()
        db_session.refresh(audit)

        assert audit.id is not None
        assert audit.action == "TEST_ACTION"

        # Attempt to update audit log
        audit.action = "ALTERED_ACTION"
        with pytest.raises(ImmutabilityViolationError, match="immutable and cannot be modified"):
            db_session.commit()
        db_session.rollback()

        # Attempt to delete audit log
        audit_fresh = db_session.query(AuditLog).filter(AuditLog.id == audit.id).first()
        db_session.delete(audit_fresh)
        with pytest.raises(ImmutabilityViolationError, match="immutable and cannot be deleted"):
            db_session.commit()
        db_session.rollback()
