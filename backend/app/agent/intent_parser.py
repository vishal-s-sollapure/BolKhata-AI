"""Groq LLM-based intent parser for BolKhata AI."""

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional
import groq
from groq import AsyncGroq, APIError, APITimeoutError, RateLimitError

from app.agent.prompts import INTENT_SYSTEM_PROMPT
from app.config.settings import get_settings
from app.schemas.intent import IntentType, ReasoningCode, TransactionProposal
from app.utils.logger import configure_logger

logger = configure_logger("bolkhata.agent.intent_parser")


class IntentParserError(Exception):
    """Base exception for intent parsing failures."""
    pass


class IntentParserConfigError(IntentParserError):
    """Raised when parser configuration (such as API key) is missing or invalid."""
    pass


class IntentParserAPIError(IntentParserError):
    """Raised when Groq API communication fails."""
    pass


class GroqIntentParser:
    """Asynchronous intent parser using Groq LLM (llama-3.3-70b-versatile).
    
    Transforms natural language speech transcripts into structured, validated
    TransactionProposal objects for merchant verification.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        client: Optional[AsyncGroq] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.GROQ_API_KEY
        self.model = model if model is not None else settings.GROQ_MODEL
        self._client = client

    def _get_client(self) -> AsyncGroq:
        """Returns or instantiates the AsyncGroq client."""
        if self._client is not None:
            return self._client
        if not self.api_key or not self.api_key.strip():
            raise IntentParserConfigError(
                "GROQ_API_KEY is not configured. Please set GROQ_API_KEY in the environment."
            )
        self._client = AsyncGroq(api_key=self.api_key)
        return self._client

    async def parse(
        self,
        transcript: str,
        language: Optional[str] = None,
    ) -> TransactionProposal:
        """Parses a speech transcript into a validated TransactionProposal.
        
        Args:
            transcript: Raw text transcription from Gnani Prisma v3.0.
            language: Language hint code (e.g. kn-IN, hi-IN, en-IN, indic-auto).
            
        Returns:
            Validated TransactionProposal instance.
            
        Raises:
            ValueError: If transcript is empty or whitespace.
            IntentParserConfigError: If Groq API key is not configured.
            IntentParserAPIError: If Groq API encounters a network or service error.
        """
        if not transcript or not transcript.strip():
            raise ValueError("Transcript cannot be empty or whitespace.")

        clean_transcript = transcript.strip()
        client = self._get_client()

        # Build user prompt
        user_content = f"Transcript: \"{clean_transcript}\""
        if language:
            user_content += f"\nLanguage Hint: {language}"

        logger.info(
            "Parsing transcript with Groq model [%s] (length: %d chars, lang: %s)",
            self.model,
            len(clean_transcript),
            language or "unspecified",
        )

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
        except (APITimeoutError, RateLimitError, APIError) as e:
            logger.error("Groq API error during intent parsing: %s", str(e))
            raise IntentParserAPIError(f"Groq API communication failed: {str(e)}") from e
        except Exception as e:
            logger.error("Unexpected error contacting Groq API: %s", str(e))
            raise IntentParserAPIError(f"Unexpected error contacting Groq API: {str(e)}") from e

        # Extract LLM response content
        message_content = response.choices[0].message.content
        if not message_content or not message_content.strip():
            logger.warning("Empty response received from Groq LLM.")
            return TransactionProposal(
                intent=IntentType.UNKNOWN,
                customer_name=None,
                amount=None,
                currency="INR",
                language=language,
                confidence=0.0,
                requires_clarification=True,
                clarification_question="No response generated. Please repeat your request.",
                summary="Unable to parse transcript.",
                reasoning_code=ReasoningCode.LLM_PARSING_ERROR.value,
            )

        # Parse JSON
        try:
            data: Dict[str, Any] = json.loads(message_content)
        except json.JSONDecodeError as e:
            logger.warning("Failed to decode JSON from Groq response: %s", message_content)
            return TransactionProposal(
                intent=IntentType.UNKNOWN,
                customer_name=None,
                amount=None,
                currency="INR",
                language=language,
                confidence=0.0,
                requires_clarification=True,
                clarification_question="I could not understand the response format. Please repeat your request.",
                summary="Malformed LLM response format.",
                reasoning_code=ReasoningCode.LLM_PARSING_ERROR.value,
            )

        # Sanitize and validate fields
        return self._build_proposal(data, clean_transcript, language)

    def _build_proposal(
        self,
        data: Dict[str, Any],
        original_transcript: str,
        default_language: Optional[str],
    ) -> TransactionProposal:
        """Constructs and validates a TransactionProposal from parsed dictionary data."""
        # 1. Intent validation
        raw_intent = str(data.get("intent", "UNKNOWN")).strip().upper()
        try:
            intent = IntentType(raw_intent)
        except ValueError:
            logger.warning("Unknown intent enum received from LLM: %s", raw_intent)
            intent = IntentType.UNKNOWN

        # 2. Customer Name sanitization
        customer_name = data.get("customer_name")
        if customer_name is not None:
            customer_name = str(customer_name).strip()
            if not customer_name or customer_name.lower() in ("null", "none"):
                customer_name = None

        # 3. Amount parsing & conversion
        raw_amount = data.get("amount")
        amount: Optional[Decimal] = None
        if raw_amount is not None:
            try:
                # Handle numeric, float or string representations
                str_amount = str(raw_amount).strip()
                if str_amount and str_amount.lower() not in ("null", "none"):
                    parsed_decimal = Decimal(str_amount)
                    if parsed_decimal > 0:
                        amount = parsed_decimal.quantize(Decimal("0.01"))
                    else:
                        # Non-positive amount requires clarification
                        amount = None
            except (InvalidOperation, ValueError):
                logger.warning("Invalid amount received from LLM: %s", raw_amount)
                amount = None

        # 4. Currency
        currency = str(data.get("currency", "INR")).strip().upper()
        if currency != "INR":
            currency = "INR"

        # 5. Language
        language = data.get("language") or default_language or "en-IN"

        # 6. Confidence
        try:
            confidence = float(data.get("confidence", 0.8))
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.5

        # 7. Reasoning code
        raw_reasoning = str(data.get("reasoning_code", "")).strip()
        try:
            reasoning_code = ReasoningCode(raw_reasoning).value
        except ValueError:
            if intent == IntentType.UNKNOWN:
                reasoning_code = ReasoningCode.UNKNOWN_INTENT.value
            elif not customer_name and intent in (IntentType.ADD_CREDIT, IntentType.RECORD_PAYMENT):
                reasoning_code = ReasoningCode.MISSING_CUSTOMER_NAME.value
            elif not amount and intent in (IntentType.ADD_CREDIT, IntentType.RECORD_PAYMENT):
                reasoning_code = ReasoningCode.MISSING_AMOUNT.value
            else:
                reasoning_code = ReasoningCode.CUSTOMER_AND_AMOUNT_IDENTIFIED.value

        # 8. Clarification
        requires_clarification = bool(data.get("requires_clarification", False))
        clarification_question = data.get("clarification_question")
        if clarification_question is not None:
            clarification_question = str(clarification_question).strip()
            if not clarification_question or clarification_question.lower() in ("null", "none"):
                clarification_question = None

        # 9. Summary
        summary = str(data.get("summary", "")).strip()
        if not summary:
            if intent == IntentType.ADD_CREDIT and customer_name and amount:
                summary = f"Add ₹{amount} credit for {customer_name}."
            elif intent == IntentType.RECORD_PAYMENT and customer_name and amount:
                summary = f"Record ₹{amount} payment received from {customer_name}."
            elif intent == IntentType.CHECK_BALANCE and customer_name:
                summary = f"Check current balance for {customer_name}."
            elif intent == IntentType.LIST_RECENT_TRANSACTIONS:
                summary = "List recent transactions."
            else:
                summary = f"Request: {original_transcript[:50]}"

        # Construct and validate through Pydantic
        return TransactionProposal(
            intent=intent,
            customer_name=customer_name,
            amount=amount,
            currency=currency,
            language=language,
            confidence=confidence,
            requires_clarification=requires_clarification,
            clarification_question=clarification_question,
            summary=summary,
            reasoning_code=reasoning_code,
        )
