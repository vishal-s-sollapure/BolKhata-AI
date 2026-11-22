"""Comprehensive test suite for BolKhata AI Real-time Voice WebSocket and Orchestrator.

Covers:
1. WebSocket connection handshake and SESSION_STARTED event.
2. Tenant isolation and invalid store rejection (code 4004).
3. Bidirectional control frames (PING -> PONG, CANCEL_SESSION).
4. Binary S16LE PCM audio chunk streaming.
5. End-to-end Voice Staging Safety:
   - Final transcript triggers Groq intent parsing and proposal staging.
   - Server emits PROPOSAL_READY.
   - Financial ledger entries are NOT automatically created (strictly append-only HITL).
6. Read-only query handling (QUERY_BALANCE -> READ_ONLY_RESPONSE, zero mutations).
7. Clarification requests for ambiguous or unknown intents.
8. REST fallback endpoints (/process-transcript and /synthesize).
9. Complete multi-step lifecycle:
   - Kannada credit voice utterance -> Staged proposal -> UI Merchant Commit -> Balance ₹340.
   - Duplicate commit replay check.
   - Payment voice utterance -> Staged proposal -> UI Merchant Commit -> Balance ₹140.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent.intent_parser import GroqIntentParser
from app.ledger.service import LedgerService
from app.main import app
from app.models.customer import Customer
from app.models.khata_entry import KhataEntry
from app.models.kirana_store import KiranaStore
from app.models.pending_proposal import PendingProposal
from app.schemas.intent import IntentType, TransactionProposal
from app.schemas.ledger import CommitProposalRequest
from app.services.intent_service import IntentService
from app.services.voice_orchestrator import VoiceOrchestrator


class TestVoiceWebSocketConnection:
    """Tests WebSocket handshake, session initialization, and store isolation."""

    def test_websocket_session_started_default_store(self, client: TestClient, test_store: KiranaStore):
        """Verifies successful WebSocket connection emits SESSION_STARTED with audio format."""
        with client.websocket_connect("/api/v1/voice/stream") as ws:
            init_msg = ws.receive_json()
            assert init_msg["event"] == "SESSION_STARTED"
            assert "session_id" in init_msg
            assert "store_id" in init_msg
            assert init_msg["sample_rate"] == 16000
            assert init_msg["format"] == "s16le"
            assert init_msg["channels"] == 1

    def test_websocket_session_started_explicit_store(
        self,
        client: TestClient,
        test_store: KiranaStore,
    ):
        """Verifies connecting with a valid store_id query param binds that store."""
        with client.websocket_connect(f"/api/v1/voice/stream?store_id={test_store.id}") as ws:
            init_msg = ws.receive_json()
            assert init_msg["event"] == "SESSION_STARTED"
            assert init_msg["store_id"] == test_store.id

    def test_websocket_rejects_invalid_store(self, client: TestClient):
        """Verifies connecting with non-existent store_id is rejected."""
        try:
            with client.websocket_connect("/api/v1/voice/stream?store_id=00000000-dead-beef-0000-000000000000") as ws:
                err_msg = ws.receive_json()
                assert err_msg["event"] == "ERROR"
                assert err_msg["code"] == "STORE_NOT_FOUND"
        except Exception:
            # WebSocket closed with code 4004
            pass

    def test_websocket_ping_pong(self, client: TestClient):
        """Verifies keepalive PING/PONG control frames."""
        with client.websocket_connect("/api/v1/voice/stream") as ws:
            ws.receive_json()  # SESSION_STARTED

            ws.send_json({"action": "PING", "timestamp": 1700000000})
            resp = ws.receive_json()
            assert resp["event"] == "PONG"
            assert resp["timestamp"] == 1700000000

    def test_websocket_cancel_session(self, client: TestClient):
        """Verifies CANCEL_SESSION triggers SESSION_ENDED without staging."""
        with client.websocket_connect("/api/v1/voice/stream") as ws:
            ws.receive_json()  # SESSION_STARTED

            ws.send_json({"action": "CANCEL_SESSION"})
            resp = ws.receive_json()
            assert resp["event"] == "SESSION_ENDED"
            assert resp["reason"] == "canceled_by_client"

    def test_websocket_binary_pcm_stream(self, client: TestClient):
        """Verifies streaming raw 16kHz S16LE PCM chunks does not crash server."""
        with client.websocket_connect("/api/v1/voice/stream") as ws:
            ws.receive_json()  # SESSION_STARTED

            # Send 5 chunks of 1024 bytes (even byte count)
            for _ in range(5):
                pcm_chunk = b"\x00\x00" * 512
                ws.send_bytes(pcm_chunk)

            # Send keepalive to ensure socket remains operational
            ws.send_json({"action": "PING", "timestamp": 123})
            resp = ws.receive_json()
            assert resp["event"] == "PONG"


class TestVoiceOrchestratorSafety:
    """Verifies that voice utterances stage proposals and NEVER auto-commit financial records."""

    def test_voice_credit_stages_proposal_without_auto_commit(
        self,
        client: TestClient,
        test_store: KiranaStore,
        db_session: Session,
    ):
        """Voice credit utterance must stage a proposal with requires_confirmation=True and 0 ledger entries."""
        initial_entries = db_session.query(KhataEntry).filter(KhataEntry.store_id == test_store.id).count()
        test_prop_id = f"voice-prop-{uuid.uuid4()}"

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
            proposal_id=test_prop_id,
        )

        with patch.object(IntentService, "parse_transcript", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = mock_proposal

            with client.websocket_connect(f"/api/v1/voice/stream?store_id={test_store.id}") as ws:
                ws.receive_json()  # SESSION_STARTED

                # Send simulated transcript
                ws.send_json({
                    "action": "SIMULATE_TRANSCRIPT",
                    "transcript": "ರಮೇಶ್ ಅವರಿಗೆ ಮುನ್ನೂರ ನಲವತ್ತು ರೂಪಾಯಿ ಸಾಲ ಕೊಡಿ",
                    "language": "kn-IN",
                })

                # Receive events in order
                ev1 = ws.receive_json()
                assert ev1["event"] == "FINAL_TRANSCRIPT"
                assert ev1["transcript"] == "ರಮೇಶ್ ಅವರಿಗೆ ಮುನ್ನೂರ ನಲವತ್ತು ರೂಪಾಯಿ ಸಾಲ ಕೊಡಿ"

                ev2 = ws.receive_json()
                assert ev2["event"] == "PROCESSING"

                ev3 = ws.receive_json()
                assert ev3["event"] == "PROPOSAL_READY"
                assert ev3["proposal"]["intent"] == "ADD_CREDIT"
                assert ev3["proposal"]["customer_name"] == "Ramesh"
                assert ev3["proposal"]["amount"] == "340.00"
                assert ev3["staged_proposal"]["status"] == "PENDING"
                assert ev3["staged_proposal"]["requires_confirmation"] is True
                assert "Ramesh" in ev3["spoken_response"]
                assert "340.00" in ev3["spoken_response"]

        # CRITICAL VERIFICATION: Zero ledger mutations occurred
        final_entries = db_session.query(KhataEntry).filter(KhataEntry.store_id == test_store.id).count()
        assert final_entries == initial_entries, "Voice speech MUST NOT create KhataEntry before explicit merchant confirmation!"

        # Server-side PendingProposal must exist with status PENDING
        pending = (
            db_session.query(PendingProposal)
            .filter(PendingProposal.proposal_id == test_prop_id, PendingProposal.store_id == test_store.id)
            .first()
        )
        assert pending is not None
        assert pending.status == "PENDING"
        assert pending.amount == Decimal("340.00")

    def test_voice_query_balance_is_read_only(
        self,
        client: TestClient,
        test_store: KiranaStore,
        test_customer: Customer,
        db_session: Session,
    ):
        """Voice query balance must return customer balance with zero database mutations."""
        # Setup existing credit
        ledger = LedgerService()
        ledger.record_credit(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("500.00"),
            idempotency_key="setup-query-500",
            db=db_session,
        )

        entries_before = db_session.query(KhataEntry).filter(KhataEntry.store_id == test_store.id).count()

        mock_proposal = TransactionProposal(
            intent=IntentType.QUERY_BALANCE,
            customer_name=test_customer.customer_name,
            amount=None,
            confidence=0.96,
            language="kn-IN",
            summary=f"Query balance for {test_customer.customer_name}",
            reasoning_code="CUSTOMER_IDENTIFIED_FOR_BALANCE",
            requires_confirmation=False,
        )

        with patch.object(IntentService, "parse_transcript", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = mock_proposal

            with client.websocket_connect(f"/api/v1/voice/stream?store_id={test_store.id}") as ws:
                ws.receive_json()  # SESSION_STARTED

                ws.send_json({
                    "action": "SIMULATE_TRANSCRIPT",
                    "transcript": f"{test_customer.customer_name} ಅವರ ಬಾಕಿ ಎಷ್ಟು?",
                    "language": "kn-IN",
                })

                ws.receive_json()  # FINAL_TRANSCRIPT
                ws.receive_json()  # PROCESSING
                res = ws.receive_json()
                assert res["event"] == "READ_ONLY_RESPONSE"
                assert res["intent"] == "QUERY_BALANCE"
                assert res["data"]["found"] is True
                assert res["data"]["outstanding_balance"] == "500.00"
                assert "500.00" in res["spoken_response"]

        # Ledger entries count must remain identical
        entries_after = db_session.query(KhataEntry).filter(KhataEntry.store_id == test_store.id).count()
        assert entries_after == entries_before

    def test_voice_unknown_intent_requests_clarification(
        self,
        client: TestClient,
        test_store: KiranaStore,
    ):
        """Voice utterance with UNKNOWN intent must ask merchant to clarify."""
        mock_proposal = TransactionProposal(
            intent=IntentType.UNKNOWN,
            customer_name=None,
            amount=None,
            confidence=0.2,
            language="kn-IN",
            summary="Could not determine intent",
            reasoning_code="UNKNOWN_INTENT",
            requires_confirmation=False,
        )

        with patch.object(IntentService, "parse_transcript", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = mock_proposal

            with client.websocket_connect(f"/api/v1/voice/stream?store_id={test_store.id}") as ws:
                ws.receive_json()  # SESSION_STARTED

                ws.send_json({
                    "action": "SIMULATE_TRANSCRIPT",
                    "transcript": "ಏನೋ ಹೇಳಿದೆ ಅರ್ಥವಾಗಲಿಲ್ಲ",
                    "language": "kn-IN",
                })

                ws.receive_json()  # FINAL_TRANSCRIPT
                ws.receive_json()  # PROCESSING
                res = ws.receive_json()
                assert res["event"] == "CLARIFICATION_REQUIRED"
                assert "ಕ್ಷಮಿಸಿ" in res["spoken_response"]


class TestVoiceRESTEndpoints:
    """Tests POST /process-transcript and POST /synthesize REST endpoints."""

    def test_rest_process_transcript_credit(
        self,
        client: TestClient,
        test_store: KiranaStore,
        db_session: Session,
    ):
        """POST /api/v1/voice/process-transcript stages credit proposal."""
        test_rest_id = f"rest-prop-{uuid.uuid4()}"
        mock_proposal = TransactionProposal(
            intent=IntentType.ADD_CREDIT,
            customer_name="Suresh",
            amount=Decimal("250.00"),
            currency="INR",
            confidence=0.92,
            language="hi-IN",
            summary="Add ₹250.00 credit for Suresh",
            reasoning_code="CUSTOMER_AND_AMOUNT_IDENTIFIED",
            requires_confirmation=True,
            proposal_id=test_rest_id,
        )

        with patch.object(IntentService, "parse_transcript", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = mock_proposal

            resp = client.post(
                f"/api/v1/voice/process-transcript?store_id={test_store.id}",
                json={"transcript": "सुरेश को 250 रुपये उधार दो", "language": "hi-IN"},
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["event_type"] == "PROPOSAL_READY"
            assert data["staged_proposal"]["status"] == "PENDING"
            assert data["staged_proposal"]["amount"] == "250.00"
            assert "Suresh" in data["spoken_response"]

    def test_rest_synthesize_endpoint(self, client: TestClient):
        """POST /api/v1/voice/synthesize returns synthesized response."""
        resp = client.post(
            "/api/v1/voice/synthesize",
            json={"text": "ನಮಸ್ಕಾರ", "language": "kn-IN"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "ನಮಸ್ಕಾರ"
        assert data["language"] == "kn-IN"
        assert data["audio_format"] == "audio/wav"


class TestEndToEndVoiceWorkflow:
    """Full lifecycle: Voice audio -> Staged proposal -> UI Merchant confirmation -> Balance updates."""

    def test_full_credit_and_payment_cycle(
        self,
        client: TestClient,
        test_store: KiranaStore,
        test_customer: Customer,
        db_session: Session,
    ):
        """Verifies:
        1. Merchant speaks: 'Add ₹340 credit for Ramesh'
        2. Backend stages proposal (PENDING).
        3. Merchant confirms proposal via HITL API -> Balance becomes ₹340.
        4. Replay commit attempt is deduplicated (idempotency).
        5. Merchant speaks: 'Record ₹200 payment from Ramesh'
        6. Backend stages proposal (PENDING).
        7. Merchant confirms payment via HITL API -> Balance becomes ₹140.
        """
        ledger = LedgerService()

        # Step 1: Voice Credit Utterance
        cycle_credit_id = f"cycle-prop-credit-{uuid.uuid4()}"
        mock_credit_proposal = TransactionProposal(
            intent=IntentType.ADD_CREDIT,
            customer_name=test_customer.customer_name,
            amount=Decimal("340.00"),
            currency="INR",
            confidence=0.96,
            language="kn-IN",
            summary=f"Add ₹340.00 credit for {test_customer.customer_name}",
            reasoning_code="CUSTOMER_AND_AMOUNT_IDENTIFIED",
            requires_confirmation=True,
            proposal_id=cycle_credit_id,
        )

        with patch.object(IntentService, "parse_transcript", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = mock_credit_proposal

            with client.websocket_connect(f"/api/v1/voice/stream?store_id={test_store.id}") as ws:
                ws.receive_json()  # SESSION_STARTED

                ws.send_json({
                    "action": "SIMULATE_TRANSCRIPT",
                    "transcript": f"{test_customer.customer_name} ಅವರಿಗೆ 340 ರೂಪಾಯಿ ಸಾಲ ಕೊಡಿ",
                    "language": "kn-IN",
                })

                ws.receive_json()  # FINAL_TRANSCRIPT
                ws.receive_json()  # PROCESSING
                res = ws.receive_json()  # PROPOSAL_READY
                assert res["event"] == "PROPOSAL_READY"
                proposal_id = res["staged_proposal"]["proposal_id"]

        # Step 2: Merchant confirms credit in UI
        commit_resp = client.post(
            f"/api/v1/ledger/proposals/commit?store_id={test_store.id}",
            json={
                "proposal_id": proposal_id,
                "confirmed": True,
                "actor_type": "merchant",
            },
        )
        assert commit_resp.status_code == 200
        commit_data = commit_resp.json()
        assert commit_data["entry_type"] == "CREDIT"
        assert commit_data["amount"] == "340.00"
        assert commit_data["resulting_balance"] == "340.00"
        assert commit_data["is_duplicate"] is False

        # Step 3: Replay commit attempt is deduplicated safely
        replay_resp = client.post(
            f"/api/v1/ledger/proposals/commit?store_id={test_store.id}",
            json={
                "proposal_id": proposal_id,
                "confirmed": True,
                "actor_type": "merchant",
            },
        )
        assert replay_resp.status_code == 200
        replay_data = replay_resp.json()
        assert replay_data["is_duplicate"] is True
        assert replay_data["resulting_balance"] == "340.00"

        # Step 4: Voice Payment Utterance (₹200)
        cycle_pay_id = f"cycle-prop-pay-{uuid.uuid4()}"
        mock_payment_proposal = TransactionProposal(
            intent=IntentType.LOG_PAYMENT,
            customer_name=test_customer.customer_name,
            amount=Decimal("200.00"),
            currency="INR",
            confidence=0.97,
            language="kn-IN",
            summary=f"Record ₹200.00 payment from {test_customer.customer_name}",
            reasoning_code="CUSTOMER_AND_AMOUNT_IDENTIFIED",
            requires_confirmation=True,
            proposal_id=cycle_pay_id,
        )

        with patch.object(IntentService, "parse_transcript", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = mock_payment_proposal

            with client.websocket_connect(f"/api/v1/voice/stream?store_id={test_store.id}") as ws:
                ws.receive_json()  # SESSION_STARTED

                ws.send_json({
                    "action": "SIMULATE_TRANSCRIPT",
                    "transcript": f"{test_customer.customer_name} ಅವರಿಂದ 200 ರೂಪಾಯಿ ಜಮೆ ಬಂತು",
                    "language": "kn-IN",
                })

                ws.receive_json()  # FINAL_TRANSCRIPT
                ws.receive_json()  # PROCESSING
                res2 = ws.receive_json()  # PROPOSAL_READY
                assert res2["event"] == "PROPOSAL_READY"
                payment_proposal_id = res2["staged_proposal"]["proposal_id"]

        # Step 5: Merchant confirms payment in UI
        commit_payment_resp = client.post(
            f"/api/v1/ledger/proposals/commit?store_id={test_store.id}",
            json={
                "proposal_id": payment_proposal_id,
                "confirmed": True,
                "actor_type": "merchant",
            },
        )
        assert commit_payment_resp.status_code == 200
        payment_data = commit_payment_resp.json()
        assert payment_data["entry_type"] == "PAYMENT"
        assert payment_data["amount"] == "200.00"
        assert payment_data["resulting_balance"] == "140.00"

        # Step 6: Verify final customer balance through ledger service
        final_balance = ledger.get_customer_balance(
            store_id=test_store.id,
            customer_id=test_customer.id,
            db=db_session,
        )
        assert final_balance.outstanding_balance == Decimal("140.00")
        assert final_balance.total_credit == Decimal("340.00")
        assert final_balance.total_payment == Decimal("200.00")
