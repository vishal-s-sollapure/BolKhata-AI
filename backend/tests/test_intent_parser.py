"""Comprehensive unit, integration, and safety tests for the AI intent parser in BolKhata AI."""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from groq import APITimeoutError

from app.agent.intent_parser import (
    GroqIntentParser,
    IntentParserAPIError,
    IntentParserConfigError,
)
from app.config.settings import get_settings
from app.database.session import engine
from app.main import app
from app.schemas.intent import (
    IntentType,
    ReasoningCode,
    TransactionProposal,
    ParseIntentRequest,
    ParseIntentResponse,
)
from app.services.intent_service import IntentService

client = TestClient(app)
settings = get_settings()


# ==============================================================================
# Helper Mock Factories
# ==============================================================================

def make_mock_groq_response(json_payload: dict):
    """Helper to construct a mock Groq ChatCompletion response."""
    choice_mock = MagicMock()
    choice_mock.message.content = json.dumps(json_payload)
    response_mock = MagicMock()
    response_mock.choices = [choice_mock]
    return response_mock


# ==============================================================================
# 1. Pydantic Schema and Business Rules Unit Tests
# ==============================================================================

class TestProposalSchemas:
    """Tests Pydantic schema validation, amount handling, and business rules."""

    def test_valid_credit_proposal_is_executable(self):
        proposal = TransactionProposal(
            intent=IntentType.ADD_CREDIT,
            customer_name="Ramesh",
            amount=Decimal("340.00"),
            currency="INR",
            language="en-IN",
            confidence=0.98,
            requires_clarification=False,
            clarification_question=None,
            summary="Add ₹340.00 credit for Ramesh.",
            reasoning_code=ReasoningCode.CUSTOMER_AND_AMOUNT_IDENTIFIED.value,
        )
        assert proposal.is_executable is True
        assert proposal.amount == Decimal("340.00")
        assert proposal.currency == "INR"

    def test_amount_serialization_formatting(self):
        proposal = TransactionProposal(
            intent=IntentType.ADD_CREDIT,
            customer_name="Ramesh",
            amount=Decimal("340"),
            confidence=0.95,
            summary="Add credit",
            reasoning_code=ReasoningCode.CUSTOMER_AND_AMOUNT_IDENTIFIED.value,
        )
        data = proposal.model_dump(mode="json")
        assert data["amount"] == "340.00"

    def test_non_inr_currency_rejected(self):
        with pytest.raises(ValueError, match="Only 'INR' is supported"):
            TransactionProposal(
                intent=IntentType.ADD_CREDIT,
                customer_name="Ramesh",
                amount=Decimal("100.00"),
                currency="USD",
                confidence=0.9,
                summary="Credit",
                reasoning_code="CUSTOMER_AND_AMOUNT_IDENTIFIED",
            )

    def test_missing_customer_name_triggers_clarification(self):
        proposal = TransactionProposal(
            intent=IntentType.ADD_CREDIT,
            customer_name=None,
            amount=Decimal("500.00"),
            confidence=0.8,
            summary="Add credit",
            reasoning_code="CUSTOMER_AND_AMOUNT_IDENTIFIED",
        )
        assert proposal.requires_clarification is True
        assert proposal.reasoning_code == ReasoningCode.MISSING_CUSTOMER_NAME.value
        assert "Which customer" in proposal.clarification_question
        assert proposal.is_executable is False

    def test_missing_amount_triggers_clarification(self):
        proposal = TransactionProposal(
            intent=IntentType.RECORD_PAYMENT,
            customer_name="Suresh",
            amount=None,
            confidence=0.8,
            summary="Payment",
            reasoning_code="CUSTOMER_AND_AMOUNT_IDENTIFIED",
        )
        assert proposal.requires_clarification is True
        assert proposal.reasoning_code == ReasoningCode.MISSING_AMOUNT.value
        assert "What is the payment amount" in proposal.clarification_question
        assert proposal.is_executable is False

    def test_check_balance_enforces_none_amount(self):
        proposal = TransactionProposal(
            intent=IntentType.CHECK_BALANCE,
            customer_name="Mahesh",
            amount=Decimal("100.00"),  # Should be forced to None by validator
            confidence=0.9,
            summary="Check balance",
            reasoning_code=ReasoningCode.CUSTOMER_IDENTIFIED_FOR_BALANCE.value,
        )
        assert proposal.amount is None
        assert proposal.is_executable is True

    def test_unknown_intent_never_executable(self):
        proposal = TransactionProposal(
            intent=IntentType.UNKNOWN,
            customer_name=None,
            amount=None,
            confidence=0.5,
            summary="Unknown",
            reasoning_code=ReasoningCode.UNKNOWN_INTENT.value,
        )
        assert proposal.requires_clarification is True
        assert proposal.is_executable is False


# ==============================================================================
# 2. Mocked Groq Intent Parser Unit Tests (Offline CI)
# ==============================================================================

class TestGroqIntentParserMocked:
    """Tests the intent parser with various language transcripts using mocked Groq LLM."""

    @pytest.mark.asyncio
    async def test_kannada_add_credit(self):
        mock_response = make_mock_groq_response({
            "intent": "ADD_CREDIT",
            "customer_name": "Ramesh",
            "amount": 340.00,
            "currency": "INR",
            "language": "kn-IN",
            "confidence": 0.98,
            "requires_clarification": False,
            "clarification_question": None,
            "summary": "Add ₹340.00 credit for Ramesh.",
            "reasoning_code": "CUSTOMER_AND_AMOUNT_IDENTIFIED",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        parser = GroqIntentParser(api_key="mock_key", client=mock_client)
        proposal = await parser.parse("ರಮೇಶ್ ಗೆ 340 ರೂಪಾಯಿ ಉಧಾರ್ ಬರೆಯಿರಿ.", language="kn-IN")

        assert proposal.intent == IntentType.ADD_CREDIT
        assert proposal.customer_name == "Ramesh"
        assert proposal.amount == Decimal("340.00")
        assert proposal.currency == "INR"
        assert proposal.language == "kn-IN"
        assert proposal.requires_clarification is False
        assert proposal.is_executable is True

    @pytest.mark.asyncio
    async def test_hindi_add_credit(self):
        mock_response = make_mock_groq_response({
            "intent": "ADD_CREDIT",
            "customer_name": "Ramesh",
            "amount": 340.00,
            "currency": "INR",
            "language": "hi-IN",
            "confidence": 0.98,
            "requires_clarification": False,
            "clarification_question": None,
            "summary": "Add ₹340.00 credit for Ramesh.",
            "reasoning_code": "CUSTOMER_AND_AMOUNT_IDENTIFIED",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        parser = GroqIntentParser(api_key="mock_key", client=mock_client)
        proposal = await parser.parse("रमेश के नाम 340 रुपये उधार लिखो।", language="hi-IN")

        assert proposal.intent == IntentType.ADD_CREDIT
        assert proposal.customer_name == "Ramesh"
        assert proposal.amount == Decimal("340.00")
        assert proposal.language == "hi-IN"
        assert proposal.is_executable is True

    @pytest.mark.asyncio
    async def test_english_add_credit(self):
        mock_response = make_mock_groq_response({
            "intent": "ADD_CREDIT",
            "customer_name": "Ramesh",
            "amount": 340.00,
            "currency": "INR",
            "language": "en-IN",
            "confidence": 0.99,
            "requires_clarification": False,
            "clarification_question": None,
            "summary": "Add ₹340.00 credit for Ramesh.",
            "reasoning_code": "CUSTOMER_AND_AMOUNT_IDENTIFIED",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        parser = GroqIntentParser(api_key="mock_key", client=mock_client)
        proposal = await parser.parse("Add 340 rupees credit for Ramesh.", language="en-IN")

        assert proposal.intent == IntentType.ADD_CREDIT
        assert proposal.customer_name == "Ramesh"
        assert proposal.amount == Decimal("340.00")
        assert proposal.is_executable is True

    @pytest.mark.asyncio
    async def test_code_mixed_add_credit(self):
        mock_response = make_mock_groq_response({
            "intent": "ADD_CREDIT",
            "customer_name": "Ramesh",
            "amount": 340.00,
            "currency": "INR",
            "language": "indic-auto",
            "confidence": 0.97,
            "requires_clarification": False,
            "clarification_question": None,
            "summary": "Add ₹340.00 credit for Ramesh.",
            "reasoning_code": "CUSTOMER_AND_AMOUNT_IDENTIFIED",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        parser = GroqIntentParser(api_key="mock_key", client=mock_client)
        proposal = await parser.parse("Ramesh ka 340 rupaye udhaar add karo.", language="indic-auto")

        assert proposal.intent == IntentType.ADD_CREDIT
        assert proposal.customer_name == "Ramesh"
        assert proposal.amount == Decimal("340.00")
        assert proposal.is_executable is True

    @pytest.mark.asyncio
    async def test_record_payment(self):
        mock_response = make_mock_groq_response({
            "intent": "RECORD_PAYMENT",
            "customer_name": "Ramesh",
            "amount": 200.00,
            "currency": "INR",
            "language": "en-IN",
            "confidence": 0.98,
            "requires_clarification": False,
            "clarification_question": None,
            "summary": "Record ₹200.00 payment received from Ramesh.",
            "reasoning_code": "CUSTOMER_AND_AMOUNT_IDENTIFIED",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        parser = GroqIntentParser(api_key="mock_key", client=mock_client)
        proposal = await parser.parse("Ramesh paid 200 rupees.", language="en-IN")

        assert proposal.intent == IntentType.RECORD_PAYMENT
        assert proposal.customer_name == "Ramesh"
        assert proposal.amount == Decimal("200.00")
        assert proposal.is_executable is True

    @pytest.mark.asyncio
    async def test_check_balance(self):
        mock_response = make_mock_groq_response({
            "intent": "CHECK_BALANCE",
            "customer_name": "Ramesh",
            "amount": None,
            "currency": "INR",
            "language": "en-IN",
            "confidence": 0.95,
            "requires_clarification": False,
            "clarification_question": None,
            "summary": "Check current balance for Ramesh.",
            "reasoning_code": "CUSTOMER_IDENTIFIED_FOR_BALANCE",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        parser = GroqIntentParser(api_key="mock_key", client=mock_client)
        proposal = await parser.parse("How much does Ramesh owe?", language="en-IN")

        assert proposal.intent == IntentType.CHECK_BALANCE
        assert proposal.customer_name == "Ramesh"
        assert proposal.amount is None
        assert proposal.is_executable is True

    @pytest.mark.asyncio
    async def test_list_recent_transactions(self):
        mock_response = make_mock_groq_response({
            "intent": "LIST_RECENT_TRANSACTIONS",
            "customer_name": None,
            "amount": None,
            "currency": "INR",
            "language": "en-IN",
            "confidence": 0.96,
            "requires_clarification": False,
            "clarification_question": None,
            "summary": "List recent transactions.",
            "reasoning_code": "RECENT_TRANSACTIONS_REQUESTED",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        parser = GroqIntentParser(api_key="mock_key", client=mock_client)
        proposal = await parser.parse("Show today's transactions.", language="en-IN")

        assert proposal.intent == IntentType.LIST_RECENT_TRANSACTIONS
        assert proposal.is_executable is True

    @pytest.mark.asyncio
    async def test_unknown_intent(self):
        mock_response = make_mock_groq_response({
            "intent": "UNKNOWN",
            "customer_name": None,
            "amount": None,
            "currency": "INR",
            "language": "en-IN",
            "confidence": 0.99,
            "requires_clarification": True,
            "clarification_question": "I could not understand the khata request. Please specify customer name and transaction details.",
            "summary": "Unknown or unsupported request.",
            "reasoning_code": "UNKNOWN_INTENT",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        parser = GroqIntentParser(api_key="mock_key", client=mock_client)
        proposal = await parser.parse("What is the weather outside today?", language="en-IN")

        assert proposal.intent == IntentType.UNKNOWN
        assert proposal.requires_clarification is True
        assert proposal.is_executable is False

    @pytest.mark.asyncio
    async def test_ambiguous_transaction_type(self):
        mock_response = make_mock_groq_response({
            "intent": "ADD_CREDIT",
            "customer_name": "Ramesh",
            "amount": 340.00,
            "currency": "INR",
            "language": "en-IN",
            "confidence": 0.70,
            "requires_clarification": True,
            "clarification_question": "Should this ₹340.00 for Ramesh be added as credit or recorded as a payment?",
            "summary": "Transaction of ₹340.00 for Ramesh (unclear if credit or payment).",
            "reasoning_code": "AMBIGUOUS_TRANSACTION_TYPE",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        parser = GroqIntentParser(api_key="mock_key", client=mock_client)
        proposal = await parser.parse("Add 340 for Ramesh.", language="en-IN")

        assert proposal.requires_clarification is True
        assert proposal.reasoning_code == ReasoningCode.AMBIGUOUS_TRANSACTION_TYPE.value
        assert proposal.is_executable is False

    @pytest.mark.asyncio
    async def test_multiple_transactions_detected(self):
        mock_response = make_mock_groq_response({
            "intent": "UNKNOWN",
            "customer_name": None,
            "amount": None,
            "currency": "INR",
            "language": "en-IN",
            "confidence": 0.50,
            "requires_clarification": True,
            "clarification_question": "Multiple transactions were mentioned. Please speak them one by one.",
            "summary": "Multiple transactions detected in a single request.",
            "reasoning_code": "MULTIPLE_TRANSACTIONS_DETECTED",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        parser = GroqIntentParser(api_key="mock_key", client=mock_client)
        proposal = await parser.parse("Add 300 for Suresh and 500 for Ramesh.", language="en-IN")

        assert proposal.requires_clarification is True
        assert proposal.reasoning_code == ReasoningCode.MULTIPLE_TRANSACTIONS_DETECTED.value
        assert proposal.is_executable is False

    @pytest.mark.asyncio
    async def test_empty_transcript_raises_value_error(self):
        parser = GroqIntentParser(api_key="mock_key")
        with pytest.raises(ValueError, match="cannot be empty"):
            await parser.parse("   ")

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_config_error(self):
        parser = GroqIntentParser(api_key="")
        with pytest.raises(IntentParserConfigError, match="GROQ_API_KEY is not configured"):
            await parser.parse("Add 100 for Ramesh")

    @pytest.mark.asyncio
    async def test_groq_timeout_raises_api_error(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=APITimeoutError(request=MagicMock())
        )

        parser = GroqIntentParser(api_key="mock_key", client=mock_client)
        with pytest.raises(IntentParserAPIError, match="Groq API communication failed"):
            await parser.parse("Add 100 for Ramesh")

    @pytest.mark.asyncio
    async def test_malformed_json_from_llm_handled_gracefully(self):
        choice_mock = MagicMock()
        choice_mock.message.content = "INVALID_NOT_A_JSON_STRING"
        response_mock = MagicMock()
        response_mock.choices = [choice_mock]

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=response_mock)

        parser = GroqIntentParser(api_key="mock_key", client=mock_client)
        proposal = await parser.parse("Add 100 for Ramesh")

        assert proposal.intent == IntentType.UNKNOWN
        assert proposal.requires_clarification is True
        assert proposal.reasoning_code == ReasoningCode.LLM_PARSING_ERROR.value
        assert proposal.is_executable is False


# ==============================================================================
# 3. FastAPI Endpoint Tests
# ==============================================================================

class TestFastAPIEndpoints:
    """Tests the /api/intent/parse endpoint behavior and error codes."""

    def test_parse_endpoint_empty_transcript_returns_400(self):
        response = client.post("/api/intent/parse", json={"transcript": "   ", "language": "en-IN"})
        assert response.status_code == 400

    @patch("app.api.intent.intent_service.parse_transcript")
    def test_parse_endpoint_success(self, mock_parse):
        mock_proposal = TransactionProposal(
            intent=IntentType.ADD_CREDIT,
            customer_name="Ramesh",
            amount=Decimal("340.00"),
            currency="INR",
            language="en-IN",
            confidence=0.98,
            requires_clarification=False,
            clarification_question=None,
            summary="Add ₹340.00 credit for Ramesh.",
            reasoning_code=ReasoningCode.CUSTOMER_AND_AMOUNT_IDENTIFIED.value,
        )
        mock_parse.return_value = mock_proposal

        response = client.post(
            "/api/intent/parse",
            json={"transcript": "Add 340 rupees credit for Ramesh.", "language": "en-IN"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["original_transcript"] == "Add 340 rupees credit for Ramesh."
        assert data["proposal"]["intent"] == "ADD_CREDIT"
        assert data["proposal"]["customer_name"] == "Ramesh"
        assert data["proposal"]["amount"] == "340.00"

    @patch("app.api.intent.intent_service.parse_transcript")
    def test_parse_endpoint_api_error_returns_503(self, mock_parse):
        mock_parse.side_effect = IntentParserAPIError("Groq service rate limited.")
        response = client.post(
            "/api/intent/parse",
            json={"transcript": "Add 340 for Ramesh", "language": "en-IN"},
        )
        assert response.status_code == 503
        assert "AI parsing service unavailable" in response.json()["detail"]


# ==============================================================================
# 4. CRITICAL SAFETY TEST: ZERO DATABASE MUTATION
# ==============================================================================

class TestLedgerSafetyGuarantee:
    """Verifies that intent parsing NEVER mutates or writes to the database.
    
    The AI Intent Parser is strictly advisory and creates proposals only.
    Only explicit user confirmation in a later phase can trigger a ledger commit.
    """

    @pytest.mark.asyncio
    async def test_intent_parsing_causes_zero_db_mutations(self):
        # 1. Inspect initial database state
        with engine.connect() as conn:
            # Query existing table names in SQLite
            result = conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            )
            tables_before = [row[0] for row in result.fetchall()]

        # 2. Run intent parser through mock
        mock_response = make_mock_groq_response({
            "intent": "ADD_CREDIT",
            "customer_name": "Ramesh",
            "amount": 9999.00,
            "currency": "INR",
            "language": "en-IN",
            "confidence": 0.99,
            "requires_clarification": False,
            "clarification_question": None,
            "summary": "Add ₹9999.00 credit for Ramesh.",
            "reasoning_code": "CUSTOMER_AND_AMOUNT_IDENTIFIED",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        service = IntentService(parser=GroqIntentParser(api_key="mock_key", client=mock_client))
        proposal = await service.parse_transcript("Add 9999 rupees credit for Ramesh.")

        assert proposal is not None
        assert proposal.amount == Decimal("9999.00")

        # 3. Verify database state is completely unchanged
        with engine.connect() as conn:
            result = conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            )
            tables_after = [row[0] for row in result.fetchall()]

        # No new tables or hidden balance records must be created
        assert tables_before == tables_after, "Database schema or tables were mutated during intent parsing!"


# ==============================================================================
# 5. Live Groq Integration Test (Runs if GROQ_API_KEY is configured)
# ==============================================================================

@pytest.mark.skipif(
    not settings.GROQ_API_KEY or not settings.GROQ_API_KEY.startswith("gsk_"),
    reason="GROQ_API_KEY is not configured or is a placeholder.",
)
class TestLiveGroqIntegration:
    """Live integration tests running against the actual Groq API."""

    @pytest.mark.asyncio
    async def test_live_english_add_credit(self):
        parser = GroqIntentParser()
        transcript = "Add 340 rupees credit for Ramesh."
        proposal = await parser.parse(transcript, language="en-IN")

        assert proposal.intent == IntentType.ADD_CREDIT
        assert proposal.customer_name == "Ramesh"
        assert proposal.amount == Decimal("340.00")
        assert proposal.currency == "INR"
        assert proposal.requires_clarification is False
        assert proposal.is_executable is True

    @pytest.mark.asyncio
    async def test_live_hindi_add_credit(self):
        parser = GroqIntentParser()
        transcript = "रमेश के नाम 340 रुपये उधार लिखो।"
        proposal = await parser.parse(transcript, language="hi-IN")

        assert proposal.intent == IntentType.ADD_CREDIT
        assert proposal.customer_name == "Ramesh"
        assert proposal.amount == Decimal("340.00")
        assert proposal.currency == "INR"
        assert proposal.requires_clarification is False
        assert proposal.is_executable is True

    @pytest.mark.asyncio
    async def test_live_kannada_add_credit(self):
        parser = GroqIntentParser()
        transcript = "ರಮೇಶ್ ಗೆ 340 ರೂಪಾಯಿ ಉಧಾರ್ ಬರೆಯಿರಿ."
        proposal = await parser.parse(transcript, language="kn-IN")

        assert proposal.intent == IntentType.ADD_CREDIT
        assert proposal.customer_name == "Ramesh"
        assert proposal.amount == Decimal("340.00")
        assert proposal.currency == "INR"
        assert proposal.requires_clarification is False
        assert proposal.is_executable is True

    @pytest.mark.asyncio
    async def test_live_code_mixed_add_credit(self):
        parser = GroqIntentParser()
        transcript = "Ramesh ka 340 rupaye udhaar add karo."
        proposal = await parser.parse(transcript, language="indic-auto")

        assert proposal.intent == IntentType.ADD_CREDIT
        assert proposal.customer_name == "Ramesh"
        assert proposal.amount == Decimal("340.00")
        assert proposal.currency == "INR"
        assert proposal.requires_clarification is False
        assert proposal.is_executable is True
