"""Unit tests for Human-In-The-Loop (HITL) proposal verification and commit safety in BolKhata AI."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.ledger.exceptions import (
    LedgerError,
    ProposalAlreadyCommittedError,
    ProposalExpiredError,
    ProposalNotExecutableError,
    ProposalNotFoundError,
    StoreMismatchError,
)
from app.ledger.service import LedgerService
from app.models.customer import Customer
from app.models.kirana_store import KiranaStore
from app.models.pending_proposal import PendingProposal
from app.schemas.intent import IntentType
from app.schemas.ledger import CommitProposalRequest, StageProposalRequest


class TestHITLProposalCommit:
    """Verifies that proposals require explicit confirmation, cannot be tampered with, and non-financial intents are blocked."""

    def test_confirmed_proposal_accepted(
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
                proposal_id="prop_hitl_01",
            ),
            db=db_session,
        )

        commit_res = service.commit_proposal(
            store_id=test_store.id,
            request=CommitProposalRequest(
                proposal_id=staged.proposal_id,
                confirmed=True,
            ),
            db=db_session,
        )

        assert commit_res.entry_type == "CREDIT"
        assert commit_res.amount == Decimal("340.00")
        assert commit_res.resulting_balance == Decimal("340.00")
        assert commit_res.is_duplicate is False

    def test_unconfirmed_proposal_rejected(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Proposal where merchant pressed cancel or confirmed=False must be rejected."""
        service = LedgerService()
        staged = service.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name=test_customer.customer_name,
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("150.00"),
                proposal_id="prop_unconfirmed",
            ),
            db=db_session,
        )

        with pytest.raises(LedgerError, match="explicitly confirmed"):
            service.commit_proposal(
                store_id=test_store.id,
                request=CommitProposalRequest(
                    proposal_id=staged.proposal_id,
                    confirmed=False,  # Unconfirmed!
                ),
                db=db_session,
            )

    def test_unknown_proposal_cannot_be_staged(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """IntentType.UNKNOWN must never be accepted for ledger staging."""
        service = LedgerService()
        with pytest.raises(ProposalNotExecutableError, match="cannot be staged for ledger mutation"):
            service.stage_proposal(
                store_id=test_store.id,
                request=StageProposalRequest(
                    customer_name=test_customer.customer_name,
                    intent=IntentType.UNKNOWN,
                    amount=Decimal("100.00"),
                ),
                db=db_session,
            )

    def test_query_balance_cannot_be_staged(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """CHECK_BALANCE / QUERY_BALANCE must never be accepted for ledger mutation."""
        service = LedgerService()
        with pytest.raises(ProposalNotExecutableError):
            service.stage_proposal(
                store_id=test_store.id,
                request=StageProposalRequest(
                    customer_name=test_customer.customer_name,
                    intent=IntentType.CHECK_BALANCE,
                    amount=Decimal("100.00"),
                ),
                db=db_session,
            )

    def test_list_dues_cannot_be_staged(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """LIST_RECENT_TRANSACTIONS / LIST_DUES must never be accepted for ledger mutation."""
        service = LedgerService()
        with pytest.raises(ProposalNotExecutableError):
            service.stage_proposal(
                store_id=test_store.id,
                request=StageProposalRequest(
                    customer_name=test_customer.customer_name,
                    intent=IntentType.LIST_RECENT_TRANSACTIONS,
                    amount=Decimal("100.00"),
                ),
                db=db_session,
            )

    def test_expired_proposal_rejected(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Proposals older than TTL must be rejected."""
        # Create an already expired pending proposal directly in DB
        expired_proposal = PendingProposal(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            proposal_id="prop_expired_1",
            customer_name=test_customer.customer_name,
            customer_id=test_customer.id,
            intent="ADD_CREDIT",
            amount=Decimal("100.00"),
            currency="INR",
            summary="Expired credit",
            status="PENDING",
            requires_confirmation=True,
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=30),  # Expired!
        )
        db_session.add(expired_proposal)
        db_session.commit()

        service = LedgerService()
        with pytest.raises(ProposalExpiredError, match="expired"):
            service.commit_proposal(
                store_id=test_store.id,
                request=CommitProposalRequest(
                    proposal_id="prop_expired_1",
                    confirmed=True,
                ),
                db=db_session,
            )

    def test_nonexistent_proposal_rejected(
        self,
        db_session: Session,
        test_store: KiranaStore,
    ):
        service = LedgerService()
        with pytest.raises(ProposalNotFoundError):
            service.commit_proposal(
                store_id=test_store.id,
                request=CommitProposalRequest(
                    proposal_id="nonexistent_uuid",
                    confirmed=True,
                ),
                db=db_session,
            )

    def test_cross_store_proposal_commit_blocked(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Store B cannot commit a proposal belonging to Store A."""
        store_b = KiranaStore(
            id=str(uuid.uuid4()),
            store_name="Store B",
            owner_name="Owner B",
            is_active=True,
        )
        db_session.add(store_b)
        db_session.commit()

        service = LedgerService()
        staged = service.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name=test_customer.customer_name,
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("200.00"),
                proposal_id="prop_cross_test",
            ),
            db=db_session,
        )

        # Store B tries to commit Store A's proposal
        with pytest.raises(StoreMismatchError, match="does not belong to store"):
            service.commit_proposal(
                store_id=store_b.id,
                request=CommitProposalRequest(
                    proposal_id=staged.proposal_id,
                    confirmed=True,
                ),
                db=db_session,
            )
