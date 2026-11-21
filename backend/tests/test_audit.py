"""Unit tests for audit trail creation and consistency in BolKhata AI."""

import json
import uuid
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.ledger.exceptions import InvalidAmountError
from app.ledger.service import LedgerService
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.khata_entry import KhataEntry
from app.models.kirana_store import KiranaStore
from app.schemas.intent import IntentType
from app.schemas.ledger import CommitProposalRequest, StageProposalRequest


class TestAuditTrail:
    """Verifies that all financial actions and duplicate attempts produce immutable audit logs."""

    def test_successful_commit_creates_audit_log(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        service = LedgerService()
        staged = service.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name=test_customer.customer_name,
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("340.00"),
                proposal_id="prop_audit_01",
            ),
            db=db_session,
        )

        commit_res = service.commit_proposal(
            store_id=test_store.id,
            request=CommitProposalRequest(
                proposal_id=staged.proposal_id,
                confirmed=True,
                actor_type="merchant",
                actor_id="terminal_01",
            ),
            db=db_session,
        )

        # Verify audit log exists
        audit = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.store_id == test_store.id,
                AuditLog.action == "TRANSACTION_COMMITTED",
                AuditLog.entity_id == commit_res.transaction_id,
            )
            .first()
        )

        assert audit is not None
        assert audit.actor_type == "merchant"
        assert audit.actor_id == "terminal_01"
        assert audit.entity_type == "KhataEntry"
        metadata = json.loads(audit.metadata_json)
        assert metadata["amount"] == "340.00"
        assert metadata["entry_type"] == "CREDIT"
        assert "password" not in metadata
        assert "api_key" not in metadata

    def test_duplicate_attempt_creates_duplicate_audit_log(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        service = LedgerService()
        staged = service.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name=test_customer.customer_name,
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("100.00"),
                proposal_id="prop_audit_dup",
            ),
            db=db_session,
        )

        req = CommitProposalRequest(
            proposal_id=staged.proposal_id,
            confirmed=True,
            actor_type="merchant",
            actor_id="terminal_01",
        )

        # First commit
        service.commit_proposal(test_store.id, req, db_session)

        # Duplicate commit attempt
        service.commit_proposal(test_store.id, req, db_session)

        # Check duplicate audit log
        dup_audit = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.store_id == test_store.id,
                AuditLog.action == "DUPLICATE_COMMIT_ATTEMPT",
            )
            .first()
        )
        assert dup_audit is not None

    def test_failed_transaction_leaves_zero_financial_records(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """If transaction parameters fail validation, zero KhataEntry rows are created."""
        initial_entries_count = db_session.query(KhataEntry).count()

        service = LedgerService()
        with pytest.raises(InvalidAmountError):
            service.record_credit(
                store_id=test_store.id,
                customer_id=test_customer.id,
                amount=Decimal("-10.00"),  # Invalid
                idempotency_key="failed_key",
                db=db_session,
            )

        final_entries_count = db_session.query(KhataEntry).count()
        assert initial_entries_count == final_entries_count
