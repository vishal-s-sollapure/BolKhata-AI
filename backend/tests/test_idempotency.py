"""Unit tests for idempotency protection and duplicate transaction handling in BolKhata AI."""

import uuid
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.ledger.exceptions import IdempotencyConflictError
from app.ledger.service import LedgerService
from app.models.customer import Customer
from app.models.khata_entry import KhataEntry
from app.models.kirana_store import KiranaStore
from app.schemas.intent import IntentType
from app.schemas.ledger import CommitProposalRequest, StageProposalRequest


class TestIdempotency:
    """Verifies that duplicate requests or repeated proposal commits never mutate balances multiple times."""

    def test_same_direct_transaction_twice(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Replaying identical transaction with same idempotency key returns original without double charge."""
        service = LedgerService()
        key = "idem_retry_test"

        # First attempt
        res1 = service.record_credit(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("340.00"),
            idempotency_key=key,
            db=db_session,
        )
        assert res1.is_duplicate is False
        assert res1.resulting_balance == Decimal("340.00")

        # Second attempt (network retry replay)
        res2 = service.record_credit(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("340.00"),
            idempotency_key=key,
            db=db_session,
        )
        assert res2.is_duplicate is True
        assert res2.transaction_id == res1.transaction_id
        assert res2.resulting_balance == Decimal("340.00")  # Balance unchanged!

        # Total database entries must be exactly 1
        count = (
            db_session.query(KhataEntry)
            .filter(KhataEntry.store_id == test_store.id, KhataEntry.idempotency_key == key)
            .count()
        )
        assert count == 1

    def test_same_proposal_committed_twice(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Committing the same proposal twice safely returns the existing transaction."""
        service = LedgerService()

        # Stage proposal
        staged = service.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name=test_customer.customer_name,
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("250.00"),
            ),
            db=db_session,
        )

        commit_req = CommitProposalRequest(
            proposal_id=staged.proposal_id,
            confirmed=True,
            idempotency_key="commit_idem_1",
        )

        # First commit
        c1 = service.commit_proposal(test_store.id, commit_req, db_session)
        assert c1.is_duplicate is False
        assert c1.resulting_balance == Decimal("250.00")

        # Second commit
        c2 = service.commit_proposal(test_store.id, commit_req, db_session)
        assert c2.is_duplicate is True
        assert c2.transaction_id == c1.transaction_id
        assert c2.resulting_balance == Decimal("250.00")

    def test_conflicting_payload_with_same_idempotency_key_rejected(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Reusing an idempotency key with a different amount or type raises IdempotencyConflictError."""
        service = LedgerService()
        key = "shared_key_conflict"

        # Initial transaction: ₹100 CREDIT
        service.record_credit(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("100.00"),
            idempotency_key=key,
            db=db_session,
        )

        # Conflicting attempt: same key, but ₹200 CREDIT
        with pytest.raises(IdempotencyConflictError, match="conflicting parameters"):
            service.record_credit(
                store_id=test_store.id,
                customer_id=test_customer.id,
                amount=Decimal("200.00"),  # Different amount!
                idempotency_key=key,
                db=db_session,
            )

    def test_idempotency_key_scoped_by_store(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """The same idempotency key CAN be used in two different stores without collision."""
        store_b = KiranaStore(
            id=str(uuid.uuid4()),
            store_name="Store B",
            owner_name="Owner B",
            is_active=True,
        )
        db_session.add(store_b)
        db_session.commit()

        customer_b = Customer(
            id=str(uuid.uuid4()),
            store_id=store_b.id,
            customer_name="Customer B",
            normalized_name="customer b",
            is_active=True,
        )
        db_session.add(customer_b)
        db_session.commit()

        service = LedgerService()
        key = "common_key_123"

        res_a = service.record_credit(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("100.00"),
            idempotency_key=key,
            db=db_session,
        )

        res_b = service.record_credit(
            store_id=store_b.id,
            customer_id=customer_b.id,
            amount=Decimal("100.00"),
            idempotency_key=key,
            db=db_session,
        )

        assert res_a.is_duplicate is False
        assert res_b.is_duplicate is False
        assert res_a.transaction_id != res_b.transaction_id
