"""Critical safety test verifying architectural isolation between AI Intent Parser and Ledger Engine in BolKhata AI."""

from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import AsyncMock, patch

from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.khata_entry import KhataEntry
from app.models.kirana_store import KiranaStore
from app.schemas.intent import IntentType, ReasoningCode, TransactionProposal


class TestSafetyIsolation:
    """CRITICAL SAFETY INVARIANT:
    The AI Intent Parsing endpoint (/api/v1/intent/parse) NEVER writes to the database.
    Financial mutations ONLY occur when an authorized merchant explicitly calls /api/v1/ledger/commit.
    """

    @pytest.mark.asyncio
    async def test_intent_parsing_alone_creates_zero_database_records(
        self,
        client: TestClient,
        db_session: Session,
        test_store: KiranaStore,
    ):
        """Executing intent parsing MUST leave the database completely untouched."""
        # Record initial table record counts
        initial_entries = db_session.query(KhataEntry).count()
        initial_audits = db_session.query(AuditLog).count()
        initial_customers = db_session.query(Customer).count()

        mock_proposal = TransactionProposal(
            intent=IntentType.ADD_CREDIT,
            customer_name="Ramesh",
            amount=Decimal("340.00"),
            currency="INR",
            confidence=0.98,
            requires_clarification=False,
            summary="Add ₹340.00 credit for Ramesh",
            reasoning_code=ReasoningCode.CUSTOMER_AND_AMOUNT_IDENTIFIED.value,
        )

        with patch(
            "app.services.intent_service.GroqIntentParser.parse",
            new_callable=AsyncMock,
            return_value=mock_proposal,
        ):
            # Merchant speaks: "Add 340 rupees credit for Ramesh"
            res = client.post(
                "/api/v1/intent/parse",
                json={
                    "transcript": "Add 340 rupees credit for Ramesh",
                    "language": "en-IN",
                },
                headers={"X-Store-Id": test_store.id},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True
            assert data["proposal"]["amount"] == "340.00"
            assert data["proposal"]["intent"] == "ADD_CREDIT"

        # Verify database state has NOT changed by even a single byte or row
        final_entries = db_session.query(KhataEntry).count()
        final_audits = db_session.query(AuditLog).count()
        final_customers = db_session.query(Customer).count()

        assert initial_entries == final_entries == 0, (
            "SAFETY VIOLATION: Calling intent parse created a KhataEntry without merchant confirmation!"
        )
        assert initial_audits == final_audits, (
            "SAFETY VIOLATION: Calling intent parse created an AuditLog!"
        )
        assert initial_customers == final_customers, (
            "SAFETY VIOLATION: Calling intent parse created or modified customer records!"
        )

    def test_database_mutates_only_upon_explicit_ledger_commit(
        self,
        client: TestClient,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """The database ONLY changes when explicit merchant confirmation is delivered to /api/v1/ledger/commit."""
        # 1. Verify 0 transactions initially
        assert db_session.query(KhataEntry).count() == 0

        # 2. Stage proposal
        stage_res = client.post(
            "/api/v1/ledger/proposals",
            json={
                "customer_name": test_customer.customer_name,
                "intent": "ADD_CREDIT",
                "amount": "500.00",
                "currency": "INR",
            },
            headers={"X-Store-Id": test_store.id},
        )
        assert stage_res.status_code == 201
        proposal_id = stage_res.json()["proposal_id"]

        # Financial ledger MUST STILL BE EMPTY (only pending proposal was staged)
        assert db_session.query(KhataEntry).count() == 0

        # 3. Explicit merchant confirmation commits to the ledger
        commit_res = client.post(
            "/api/v1/ledger/commit",
            json={
                "proposal_id": proposal_id,
                "confirmed": True,
            },
            headers={"X-Store-Id": test_store.id},
        )
        assert commit_res.status_code == 200

        # Financial ledger NOW HAS EXACTLY 1 RECORD
        assert db_session.query(KhataEntry).count() == 1
        entry = db_session.query(KhataEntry).first()
        assert Decimal(str(entry.amount)) == Decimal("500.00")
        assert entry.entry_type == "CREDIT"
