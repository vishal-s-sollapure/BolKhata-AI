"""Comprehensive automated verification suite for BolKhata AI Phase 5.1 Independent Audit.

Covers:
- Task 3: Financial Safety Audit (speech never auto-commits, Groq decoupled, idempotency, rejected/expired/cross-store blocks, read-only queries)
- Task 4: Audio Quality & Framing (16-bit alignment, odd byte handling, oversized buffer rejection)
- Task 5: Security & Privacy (credential isolation, stack trace sanitization, store tenant isolation)
- Task 6: Full multi-step financial scenario on isolated test database
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent.intent_parser import GroqIntentParser
from app.ledger.exceptions import (
    CustomerAmbiguityError,
    CustomerNotFoundError,
    IdempotencyConflictError,
    LedgerError,
    ProposalAlreadyCommittedError,
    ProposalExpiredError,
    ProposalNotExecutableError,
    ProposalNotFoundError,
    StoreMismatchError,
)
from app.ledger.service import LedgerService
from app.models.customer import Customer
from app.models.khata_entry import KhataEntry
from app.models.kirana_store import KiranaStore
from app.models.pending_proposal import PendingProposal
from app.schemas.intent import IntentType, TransactionProposal
from app.schemas.ledger import CommitProposalRequest, RejectProposalRequest, StageProposalRequest
from app.services.intent_service import IntentService
from app.services.voice_orchestrator import VoiceOrchestrator
from app.voice.audio import validate_pcm_chunk


class TestFinancialSafetyAudit:
    """Verifies that speech, LLM output, and TTS can NEVER directly alter the ledger."""

    def test_intent_service_has_no_db_dependencies(self):
        """IntentService and GroqIntentParser must have zero access to database sessions or mutation methods."""
        service = IntentService()
        assert not hasattr(service, "db")
        assert not hasattr(service, "session")
        assert not hasattr(service, "commit")
        assert not hasattr(service.parser, "db")

    def test_voice_orchestrator_only_stages_never_commits(
        self,
        client: TestClient,
        test_store: KiranaStore,
        db_session: Session,
    ):
        """Streaming speech utterances must only create PENDING proposals and NEVER commit financial entries."""
        initial_entries = db_session.query(KhataEntry).filter(KhataEntry.store_id == test_store.id).count()
        prop_id = f"safety-prop-{uuid.uuid4()}"

        mock_proposal = TransactionProposal(
            intent=IntentType.ADD_CREDIT,
            customer_name="Ramesh",
            amount=Decimal("340.00"),
            currency="INR",
            confidence=0.95,
            language="kn-IN",
            summary="Add ₹340.00 credit for Ramesh",
            reasoning_code="CUSTOMER_AND_AMOUNT_IDENTIFIED",
            requires_confirmation=True,
            proposal_id=prop_id,
        )

        with patch.object(IntentService, "parse_transcript", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = mock_proposal

            with client.websocket_connect(f"/api/v1/voice/stream?store_id={test_store.id}") as ws:
                ws.receive_json()  # SESSION_STARTED

                ws.send_json({
                    "action": "SIMULATE_TRANSCRIPT",
                    "transcript": "ರಮೇಶ್ ಅವರಿಗೆ ಮುನ್ನೂರ ನಲವತ್ತು ರೂಪಾಯಿ ಸಾಲ ಕೊಡಿ",
                    "language": "kn-IN",
                })

                ws.receive_json()  # FINAL_TRANSCRIPT
                ws.receive_json()  # PROCESSING
                res = ws.receive_json()
                assert res["event"] == "PROPOSAL_READY"
                assert res["staged_proposal"]["status"] == "PENDING"

        # Check ledger table: MUST BE EXACTLY 0 NEW ENTRIES
        entries_after = db_session.query(KhataEntry).filter(KhataEntry.store_id == test_store.id).count()
        assert entries_after == initial_entries, "Financial transaction was committed without merchant confirmation!"

    def test_unconfirmed_proposal_rejected(
        self,
        test_store: KiranaStore,
        test_customer: Customer,
        db_session: Session,
    ):
        """Commit request with confirmed=False must be rejected with LedgerError."""
        ledger = LedgerService()
        staged = ledger.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name=test_customer.customer_name,
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("100.00"),
                proposal_id=f"unconf-{uuid.uuid4()}",
            ),
            db=db_session,
        )

        with pytest.raises(LedgerError, match="explicitly confirmed"):
            ledger.commit_proposal(
                store_id=test_store.id,
                request=CommitProposalRequest(
                    proposal_id=staged.proposal_id,
                    confirmed=False,
                ),
                db=db_session,
            )

    def test_rejected_proposal_cannot_commit(
        self,
        test_store: KiranaStore,
        test_customer: Customer,
        db_session: Session,
    ):
        """A proposal rejected by the merchant cannot be committed subsequently."""
        ledger = LedgerService()
        staged = ledger.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name=test_customer.customer_name,
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("200.00"),
                proposal_id=f"rej-{uuid.uuid4()}",
            ),
            db=db_session,
        )

        # Reject proposal
        ledger.reject_proposal(
            store_id=test_store.id,
            proposal_id=staged.proposal_id,
            db=db_session,
            reason="Merchant canceled",
        )

        # Attempt commit
        with pytest.raises(ProposalAlreadyCommittedError, match="previously rejected"):
            ledger.commit_proposal(
                store_id=test_store.id,
                request=CommitProposalRequest(
                    proposal_id=staged.proposal_id,
                    confirmed=True,
                ),
                db=db_session,
            )

    def test_expired_proposal_cannot_commit(
        self,
        test_store: KiranaStore,
        test_customer: Customer,
        db_session: Session,
    ):
        """A proposal past its TTL (15 minutes) expires and cannot be committed."""
        ledger = LedgerService()
        prop_id = f"exp-{uuid.uuid4()}"
        staged = ledger.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name=test_customer.customer_name,
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("150.00"),
                proposal_id=prop_id,
            ),
            db=db_session,
        )

        # Manually backdate expiration in DB to 10 minutes ago
        pending = db_session.query(PendingProposal).filter(PendingProposal.proposal_id == prop_id).first()
        assert pending is not None
        pending.expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        db_session.commit()

        # Attempt commit
        with pytest.raises(ProposalExpiredError):
            ledger.commit_proposal(
                store_id=test_store.id,
                request=CommitProposalRequest(
                    proposal_id=prop_id,
                    confirmed=True,
                ),
                db=db_session,
            )

    def test_cross_store_proposal_commit_blocked(
        self,
        test_store: KiranaStore,
        test_customer: Customer,
        db_session: Session,
    ):
        """A merchant from Store B cannot commit a proposal staged in Store A."""
        # Create Store B
        store_b = KiranaStore(
            id=str(uuid.uuid4()),
            store_name="Store B Malicious",
            owner_name="Attacker",
            phone_number="+919999900000",
            is_active=True,
        )
        db_session.add(store_b)
        db_session.commit()

        ledger = LedgerService()
        staged = ledger.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name=test_customer.customer_name,
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("500.00"),
                proposal_id=f"cross-{uuid.uuid4()}",
            ),
            db=db_session,
        )

        # Attempt commit from store_b
        with pytest.raises(StoreMismatchError):
            ledger.commit_proposal(
                store_id=store_b.id,
                request=CommitProposalRequest(
                    proposal_id=staged.proposal_id,
                    confirmed=True,
                ),
                db=db_session,
            )

    def test_idempotent_commit_with_amount_mismatch_fails(
        self,
        test_store: KiranaStore,
        test_customer: Customer,
        db_session: Session,
    ):
        """Reusing the same idempotency key with a conflicting amount must raise IdempotencyConflictError."""
        ledger = LedgerService()
        key = f"idem-key-{uuid.uuid4()}"

        # First commit
        ledger.record_transaction(
            store_id=test_store.id,
            customer_id=test_customer.id,
            entry_type="CREDIT",
            amount=Decimal("100.00"),
            idempotency_key=key,
            db=db_session,
        )

        # Conflicting commit with amount 200.00
        with pytest.raises(IdempotencyConflictError):
            ledger.record_transaction(
                store_id=test_store.id,
                customer_id=test_customer.id,
                entry_type="CREDIT",
                amount=Decimal("200.00"),
                idempotency_key=key,
                db=db_session,
            )


class TestAudioQualityAndFraming:
    """Verifies audio validation, S16LE PCM framing, and edge-case handling."""

    def test_validate_pcm_chunk_alignment(self):
        """Even byte count is valid 16-bit PCM; odd byte count is rejected."""
        valid_chunk = b"\x00\x00" * 512  # 1024 bytes
        assert validate_pcm_chunk(valid_chunk) is True

        odd_chunk = b"\x00\x00\x01"  # 3 bytes (misaligned)
        assert validate_pcm_chunk(odd_chunk) is False

        empty_chunk = b""
        assert validate_pcm_chunk(empty_chunk) is False

    def test_validate_pcm_chunk_non_bytes_and_misaligned(self):
        """PCM validator rejects non-bytes objects, odd byte lengths, and empty buffers."""
        assert validate_pcm_chunk("not bytes") is False
        assert validate_pcm_chunk(12345) is False
        assert validate_pcm_chunk([0, 0, 0]) is False
        assert validate_pcm_chunk(b"\x00\x00\x01\x02\x03") is False
        assert validate_pcm_chunk(b"", allow_partial=False) is False
        assert validate_pcm_chunk(b"", allow_partial=True) is True

    def test_validate_pcm_chunk_oversized_rejected(self):
        """Oversized audio chunks exceeding MAX_PCM_CHUNK_BYTES (65536) must be rejected."""
        oversized = b"\x00\x00" * 35000  # 70,000 bytes
        assert validate_pcm_chunk(oversized) is False


class TestSecurityAndPrivacy:
    """Verifies credential containment, tenant isolation, and error sanitization."""

    def test_api_keys_not_exposed_in_websocket_error(
        self,
        client: TestClient,
    ):
        """WebSocket error responses must return clean error codes and never leak stack traces or internal secrets."""
        with client.websocket_connect("/api/v1/voice/stream?store_id=00000000-dead-beef-0000-000000000000") as ws:
            err = ws.receive_json()
            assert err["event"] == "ERROR"
            assert err["code"] == "STORE_NOT_FOUND"
            assert "traceback" not in str(err).lower()
            assert "api_key" not in str(err).lower()
            assert "groq" not in str(err).lower()
            assert "gnani" not in str(err).lower()

    def test_cross_store_customer_isolation(
        self,
        test_store: KiranaStore,
        test_customer: Customer,
        db_session: Session,
    ):
        """Store B cannot read or query balances for Store A customers."""
        store_b = KiranaStore(
            id=str(uuid.uuid4()),
            store_name="Store B",
            owner_name="Merchant B",
            is_active=True,
        )
        db_session.add(store_b)
        db_session.commit()

        ledger = LedgerService()
        with pytest.raises(CustomerNotFoundError):
            ledger.get_customer_balance(
                store_id=store_b.id,
                customer_id=test_customer.id,
                db=db_session,
            )


class TestFullFinancialScenarioTask6:
    """Executes the exact 10-step financial verification scenario from Task 6."""

    def test_exact_task_6_scenario_lifecycle(
        self,
        client: TestClient,
        test_store: KiranaStore,
        db_session: Session,
    ):
        """
        Task 6 Scenario:
        1. Add ₹340 credit for Ramesh.
        2. Confirm the proposal.
        3. Verify balance = ₹340.
        4. Repeat the same commit request.
        5. Verify balance remains ₹340.
        6. Record ₹200 payment.
        7. Confirm the payment.
        8. Verify final balance = ₹140.
        9. Query the balance through voice.
        10. Verify no additional financial entry was created by the query.
        11. Test a rejected proposal.
        12. Test an ambiguous customer name.
        """
        ledger = LedgerService()

        # Step 1: Voice Credit Utterance (₹340 for Ramesh)
        credit_prop_id = f"task6-prop-credit-{uuid.uuid4()}"
        mock_credit_proposal = TransactionProposal(
            intent=IntentType.ADD_CREDIT,
            customer_name="Ramesh",
            amount=Decimal("340.00"),
            currency="INR",
            confidence=0.96,
            language="kn-IN",
            summary="Add ₹340.00 credit for Ramesh",
            reasoning_code="CUSTOMER_AND_AMOUNT_IDENTIFIED",
            requires_confirmation=True,
            proposal_id=credit_prop_id,
        )

        with patch.object(IntentService, "parse_transcript", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = mock_credit_proposal

            with client.websocket_connect(f"/api/v1/voice/stream?store_id={test_store.id}") as ws:
                ws.receive_json()  # SESSION_STARTED

                ws.send_json({
                    "action": "SIMULATE_TRANSCRIPT",
                    "transcript": "ರಮೇಶ್ ಅವರಿಗೆ 340 ರೂಪಾಯಿ ಸಾಲ ಕೊಡಿ",
                    "language": "kn-IN",
                })

                ws.receive_json()  # FINAL_TRANSCRIPT
                ws.receive_json()  # PROCESSING
                res = ws.receive_json()  # PROPOSAL_READY
                assert res["event"] == "PROPOSAL_READY"
                proposal_id = res["staged_proposal"]["proposal_id"]

        # Step 2: Explicit Confirmation via UI Commit API
        commit_res = client.post(
            "/api/v1/ledger/commit",
            json={"proposal_id": proposal_id, "confirmed": True, "actor_type": "merchant"},
            headers={"X-Store-Id": test_store.id},
        )
        assert commit_res.status_code == 200
        c_data = commit_res.json()
        assert c_data["entry_type"] == "CREDIT"
        assert c_data["amount"] == "340.00"

        # Step 3: Verify balance = ₹340.00
        assert c_data["resulting_balance"] == "340.00"
        customer_id = c_data["customer_id"]

        # Step 4: Repeat the same commit request
        replay_res = client.post(
            "/api/v1/ledger/commit",
            json={"proposal_id": proposal_id, "confirmed": True, "actor_type": "merchant"},
            headers={"X-Store-Id": test_store.id},
        )
        assert replay_res.status_code == 200
        r_data = replay_res.json()

        # Step 5: Verify balance remains ₹340.00 (idempotent duplicate)
        assert r_data["is_duplicate"] is True
        assert r_data["resulting_balance"] == "340.00"

        # Step 6: Voice Payment Utterance (₹200 from Ramesh)
        pay_prop_id = f"task6-prop-pay-{uuid.uuid4()}"
        mock_pay_proposal = TransactionProposal(
            intent=IntentType.LOG_PAYMENT,
            customer_name="Ramesh",
            amount=Decimal("200.00"),
            currency="INR",
            confidence=0.97,
            language="kn-IN",
            summary="Record ₹200.00 payment from Ramesh",
            reasoning_code="CUSTOMER_AND_AMOUNT_IDENTIFIED",
            requires_confirmation=True,
            proposal_id=pay_prop_id,
        )

        with patch.object(IntentService, "parse_transcript", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = mock_pay_proposal

            with client.websocket_connect(f"/api/v1/voice/stream?store_id={test_store.id}") as ws:
                ws.receive_json()  # SESSION_STARTED

                ws.send_json({
                    "action": "SIMULATE_TRANSCRIPT",
                    "transcript": "ರಮೇಶ್ ಅವರಿಂದ 200 ರೂಪಾಯಿ ಜಮೆ ಬಂತು",
                    "language": "kn-IN",
                })

                ws.receive_json()  # FINAL_TRANSCRIPT
                ws.receive_json()  # PROCESSING
                res2 = ws.receive_json()  # PROPOSAL_READY
                assert res2["event"] == "PROPOSAL_READY"
                payment_proposal_id = res2["staged_proposal"]["proposal_id"]

        # Step 7: Explicit Confirmation of Payment via UI Commit API
        commit_pay_res = client.post(
            "/api/v1/ledger/commit",
            json={"proposal_id": payment_proposal_id, "confirmed": True, "actor_type": "merchant"},
            headers={"X-Store-Id": test_store.id},
        )
        assert commit_pay_res.status_code == 200
        p_data = commit_pay_res.json()
        assert p_data["entry_type"] == "PAYMENT"
        assert p_data["amount"] == "200.00"

        # Step 8: Verify final balance = ₹140.00
        assert p_data["resulting_balance"] == "140.00"

        bal_check = ledger.get_customer_balance(test_store.id, customer_id, db_session)
        assert bal_check.outstanding_balance == Decimal("140.00")
        assert bal_check.total_credit == Decimal("340.00")
        assert bal_check.total_payment == Decimal("200.00")

        # Step 9: Query balance through voice
        entries_count_before_query = db_session.query(KhataEntry).filter(KhataEntry.store_id == test_store.id).count()

        mock_query_proposal = TransactionProposal(
            intent=IntentType.QUERY_BALANCE,
            customer_name="Ramesh",
            amount=None,
            confidence=0.98,
            language="kn-IN",
            summary="Query balance for Ramesh",
            reasoning_code="CUSTOMER_IDENTIFIED_FOR_BALANCE",
            requires_confirmation=False,
            proposal_id=f"query-prop-{uuid.uuid4()}",
        )

        with patch.object(IntentService, "parse_transcript", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = mock_query_proposal

            with client.websocket_connect(f"/api/v1/voice/stream?store_id={test_store.id}") as ws:
                ws.receive_json()  # SESSION_STARTED

                ws.send_json({
                    "action": "SIMULATE_TRANSCRIPT",
                    "transcript": "ರಮೇಶ್ ಅವರ ಬಾಕಿ ಎಷ್ಟು?",
                    "language": "kn-IN",
                })

                ws.receive_json()  # FINAL_TRANSCRIPT
                ws.receive_json()  # PROCESSING
                query_res = ws.receive_json()
                assert query_res["event"] == "READ_ONLY_RESPONSE"
                assert query_res["data"]["found"] is True
                assert query_res["data"]["outstanding_balance"] == "140.00"

        # Step 10: Verify no additional financial entry was created by the query
        entries_count_after_query = db_session.query(KhataEntry).filter(KhataEntry.store_id == test_store.id).count()
        assert entries_count_after_query == entries_count_before_query, "Read-only balance query created an unauthorized KhataEntry!"

        # Step 11: Test a rejected proposal
        rej_prop_id = f"task6-rej-{uuid.uuid4()}"
        staged_rej = ledger.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name="Ramesh",
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("50.00"),
                proposal_id=rej_prop_id,
            ),
            db=db_session,
        )
        rej_response = client.post(
            f"/api/v1/ledger/proposals/{rej_prop_id}/reject",
            headers={"X-Store-Id": test_store.id},
        )
        assert rej_response.status_code == 200
        assert rej_response.json()["status"] == "REJECTED"

        # Step 12: Test ambiguous customer name
        # Create second customer named "Ramesh" with a different phone number
        cust2 = Customer(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            customer_name="Ramesh",
            normalized_name="ramesh",
            phone_number="+919876500000",
            is_active=True,
        )
        db_session.add(cust2)
        db_session.commit()

        # Staging without customer_id or phone now detects ambiguity
        ambig_prop_id = f"task6-ambig-{uuid.uuid4()}"
        staged_ambig = ledger.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name="Ramesh",
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("80.00"),
                proposal_id=ambig_prop_id,
            ),
            db=db_session,
        )
        # PendingProposal has customer_id = None because two match
        assert staged_ambig.customer_name == "Ramesh"

        # Committing without disambiguation raises CustomerAmbiguityError
        with pytest.raises(CustomerAmbiguityError):
            ledger.commit_proposal(
                store_id=test_store.id,
                request=CommitProposalRequest(
                    proposal_id=ambig_prop_id,
                    confirmed=True,
                ),
                db=db_session,
            )
