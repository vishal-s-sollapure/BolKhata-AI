"""Voice Orchestrator for BolKhata AI.

Coordinates the end-to-end pipeline:
Voice Transcript -> Intent Parsing -> Proposal Staging (HITL) -> Spoken Confirmation (TTS).

CRITICAL SAFETY INVARIANTS:
1. Spoken audio or LLM output NEVER automatically commits to the ledger.
2. Financial ledger writes require explicit merchant confirmation via HITL UI.
3. Read-only queries (QUERY_BALANCE, LIST_DUES) execute without ledger mutations.
4. Ambiguous or unknown intents trigger spoken clarification prompts.
"""

import base64
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.agent.intent_parser import GroqIntentParser
from app.ledger.service import LedgerService
from app.models.customer import Customer
from app.schemas.intent import IntentType, TransactionProposal
from app.schemas.ledger import CustomerBalanceResponse, PendingProposalResponse, StageProposalRequest
from app.services.customer_service import CustomerService
from app.services.intent_service import IntentService
from app.utils.logger import configure_logger
from app.voice.tts import (
    LANGUAGE_VOICE_MAP,
    GnaniTimbreTTSClient,
    TimbreV3TTSConfig,
)

logger = configure_logger("bolkhata.services.voice_orchestrator")


@dataclass
class VoiceOrchestratorResult:
    """Encapsulates the result of processing a merchant voice transcript."""
    event_type: str  # "PROPOSAL_READY", "READ_ONLY_RESPONSE", "CLARIFICATION_REQUIRED", "ERROR"
    transcript: str
    language: str
    proposal: Optional[TransactionProposal] = None
    staged_proposal: Optional[PendingProposalResponse] = None
    read_only_data: Optional[Dict[str, Any]] = None
    spoken_response: str = ""
    audio_bytes: Optional[bytes] = None
    audio_format: str = "audio/wav"

    def to_client_event(self, session_id: str) -> Dict[str, Any]:
        """Serializes the result to a WebSocket event dictionary matching protocol."""
        audio_b64 = base64.b64encode(self.audio_bytes).decode("ascii") if self.audio_bytes else None

        if self.event_type == "PROPOSAL_READY":
            proposal_dict = self.proposal.model_dump() if self.proposal else {}
            # Format Decimal to string in proposal_dict
            if proposal_dict.get("amount") is not None:
                proposal_dict["amount"] = str(proposal_dict["amount"])

            staged_dict = self.staged_proposal.model_dump() if self.staged_proposal else {}
            if staged_dict.get("created_at"):
                staged_dict["created_at"] = staged_dict["created_at"].isoformat()
            if staged_dict.get("expires_at"):
                staged_dict["expires_at"] = staged_dict["expires_at"].isoformat()

            return {
                "event": "PROPOSAL_READY",
                "session_id": session_id,
                "proposal": proposal_dict,
                "staged_proposal": staged_dict,
                "spoken_response": self.spoken_response,
                "audio_b64": audio_b64,
                "audio_format": self.audio_format,
            }

        elif self.event_type == "READ_ONLY_RESPONSE":
            return {
                "event": "READ_ONLY_RESPONSE",
                "session_id": session_id,
                "intent": self.proposal.intent.value if self.proposal else "QUERY_BALANCE",
                "data": self.read_only_data or {},
                "spoken_response": self.spoken_response,
                "audio_b64": audio_b64,
                "audio_format": self.audio_format,
            }

        elif self.event_type == "CLARIFICATION_REQUIRED":
            return {
                "event": "CLARIFICATION_REQUIRED",
                "session_id": session_id,
                "transcript": self.transcript,
                "spoken_response": self.spoken_response,
                "audio_b64": audio_b64,
                "audio_format": self.audio_format,
            }

        return {
            "event": "ERROR",
            "session_id": session_id,
            "code": "INTERNAL_ORCHESTRATION_ERROR",
            "message": self.spoken_response or "An error occurred during voice processing.",
        }


class VoiceOrchestrator:
    """Orchestrates speech-to-intent-to-proposal-to-speech lifecycle."""

    def __init__(
        self,
        intent_service: Optional[IntentService] = None,
        ledger_service: Optional[LedgerService] = None,
        customer_service: Optional[CustomerService] = None,
        tts_client: Optional[GnaniTimbreTTSClient] = None,
    ) -> None:
        self.intent_service = intent_service or IntentService()
        self.ledger_service = ledger_service or LedgerService()
        self.customer_service = customer_service or CustomerService()
        self.tts_client = tts_client

    @staticmethod
    def normalize_language_code(lang: Optional[str]) -> str:
        """Normalizes language code to standard kn-IN, hi-IN, or en-IN."""
        if not lang:
            return "kn-IN"
        l = lang.lower().strip()
        if "kn" in l or "kannada" in l:
            return "kn-IN"
        if "hi" in l or "hindi" in l:
            return "hi-IN"
        if "en" in l or "english" in l:
            return "en-IN"
        return "kn-IN"

    def generate_spoken_prompt(
        self,
        intent: IntentType,
        customer_name: Optional[str],
        amount: Optional[Decimal],
        language: str,
        balance: Optional[Decimal] = None,
    ) -> str:
        """Generates localized confirmation or response text in kn, hi, or en."""
        norm_lang = self.normalize_language_code(language)
        c_name = customer_name or "ಗ್ರಾಹಕರು" if norm_lang == "kn-IN" else (customer_name or "ग्राहक" if norm_lang == "hi-IN" else (customer_name or "Customer"))
        amt_str = f"{amount:.2f}" if amount is not None else "0.00"
        bal_str = f"{balance:.2f}" if balance is not None else "0.00"

        if intent == IntentType.ADD_CREDIT:
            if norm_lang == "kn-IN":
                return f"{c_name} ಅವರಿಗೆ ₹{amt_str} ಸಾಲ ದಾಖಲಿಸಲು ಸಿದ್ಧವಾಗಿದೆ. ದಯವಿಟ್ಟು ಖಚಿತಪಡಿಸಿ."
            elif norm_lang == "hi-IN":
                return f"{c_name} के लिए ₹{amt_str} उधार दर्ज करने के लिए तैयार है। कृपया पुष्टि करें।"
            return f"Ready to add ₹{amt_str} credit for {c_name}. Please confirm."

        elif intent in (IntentType.LOG_PAYMENT, IntentType.RECORD_PAYMENT):
            if norm_lang == "kn-IN":
                return f"{c_name} ಅವರಿಂದ ₹{amt_str} ಜಮೆ ದಾಖಲಿಸಲು ಸಿದ್ಧವಾಗಿದೆ. ದಯವಿಟ್ಟು ಖಚಿತಪಡಿಸಿ."
            elif norm_lang == "hi-IN":
                return f"{c_name} से ₹{amt_str} जमा दर्ज करने के लिए तैयार है। कृपया पुष्टि करें।"
            return f"Ready to record ₹{amt_str} payment from {c_name}. Please confirm."

        elif intent == IntentType.QUERY_BALANCE:
            if norm_lang == "kn-IN":
                return f"{c_name} ಅವರ ಬಾಕಿ ಮೊತ್ತ ₹{bal_str} ಆಗಿದೆ."
            elif norm_lang == "hi-IN":
                return f"{c_name} का कुल बकाया ₹{bal_str} है।"
            return f"The outstanding balance for {c_name} is ₹{bal_str}."

        elif intent == IntentType.LIST_DUES:
            if norm_lang == "kn-IN":
                return f"ಬಾಕಿ ಪಟ್ಟಿಯನ್ನು ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ನಲ್ಲಿ ಪ್ರದರ್ಶಿಸಲಾಗಿದೆ."
            elif norm_lang == "hi-IN":
                return f"बकाया सूची स्क्रीन पर प्रदर्शित कर दी गई है।"
            return f"Outstanding dues list is displayed on the dashboard."

        # Default fallback / UNKNOWN
        if norm_lang == "kn-IN":
            return "ಕ್ಷಮಿಸಿ, ಅರ್ಥವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಸ್ಪಷ್ಟವಾಗಿ ಹೇಳಿ."
        elif norm_lang == "hi-IN":
            return "माफ़ कीजिए, समझ नहीं आया। कृपया दोबारा स्पष्ट रूप से बोलें।"
        return "Sorry, I could not understand that. Please speak again clearly."

    async def synthesize_speech(self, text: str, language: str) -> Optional[bytes]:
        """Synthesizes text into speech bytes using Timbre v3.0."""
        if not text or not text.strip():
            return None

        norm_lang = self.normalize_language_code(language)
        voice_map = LANGUAGE_VOICE_MAP.get(norm_lang, LANGUAGE_VOICE_MAP["kn-IN"])
        voice = voice_map.get("default", "Manjunath")

        tts = self.tts_client
        should_close = False
        if tts is None:
            try:
                config = TimbreV3TTSConfig(voice=voice, language=norm_lang, container="wav")
                tts = GnaniTimbreTTSClient(config=config)
                should_close = True
            except Exception as e:
                logger.warning("Could not initialize Timbre v3.0 TTS client: %s", e)
                return None

        try:
            audio_bytes = await tts.synthesize(text)
            return audio_bytes
        except Exception as e:
            logger.warning("TTS synthesis failed for text '%s': %s", text[:40], e)
            return None
        finally:
            if should_close and tts:
                try:
                    await tts.close()
                except Exception:
                    pass

    async def process_utterance(
        self,
        store_id: str,
        transcript: str,
        language_hint: Optional[str],
        db: Session,
    ) -> VoiceOrchestratorResult:
        """Processes a merchant voice transcript end-to-end.
        
        Args:
            store_id: ID of the authenticated kirana store.
            transcript: Transcribed merchant text.
            language_hint: Language hint (e.g. kn-IN, hi-IN, en-IN).
            db: SQLAlchemy database session.
            
        Returns:
            VoiceOrchestratorResult with status, proposal, staged proposal, spoken text, and audio.
        """
        logger.info("Processing voice utterance for store '%s': '%s'", store_id, transcript)

        if not transcript or not transcript.strip():
            spoken = self.generate_spoken_prompt(IntentType.UNKNOWN, None, None, language_hint or "kn-IN")
            audio = await self.synthesize_speech(spoken, language_hint or "kn-IN")
            return VoiceOrchestratorResult(
                event_type="CLARIFICATION_REQUIRED",
                transcript="",
                language=self.normalize_language_code(language_hint),
                spoken_response=spoken,
                audio_bytes=audio,
            )

        # 1. Parse intent via GroqIntentParser
        proposal = await self.intent_service.parse_transcript(
            transcript=transcript,
            language=language_hint,
        )
        resolved_lang = proposal.language or language_hint or "kn-IN"

        # 2. Branch based on intent
        if proposal.intent in (IntentType.ADD_CREDIT, IntentType.LOG_PAYMENT, IntentType.RECORD_PAYMENT):
            # Financial mutation proposal -> STAGE ONLY, NEVER AUTO-COMMIT
            if not proposal.customer_name or proposal.amount is None or proposal.amount <= Decimal("0"):
                logger.warning(
                    "Proposal missing customer or amount (customer=%s, amount=%s)",
                    proposal.customer_name,
                    proposal.amount,
                )
                spoken = (
                    "ದಯವಿಟ್ಟು ಗ್ರಾಹಕರ ಹೆಸರು ಮತ್ತು ಮೊತ್ತವನ್ನು ತಿಳಿಸಿ."
                    if self.normalize_language_code(resolved_lang) == "kn-IN"
                    else ("कृपया ग्राहक का नाम और राशि बताएं।" if self.normalize_language_code(resolved_lang) == "hi-IN"
                          else "Please specify the customer name and amount.")
                )
                audio = await self.synthesize_speech(spoken, resolved_lang)
                return VoiceOrchestratorResult(
                    event_type="CLARIFICATION_REQUIRED",
                    transcript=transcript,
                    language=resolved_lang,
                    proposal=proposal,
                    spoken_response=spoken,
                    audio_bytes=audio,
                )

            # Stage proposal in server-side database
            stage_request = StageProposalRequest(
                customer_name=proposal.customer_name,
                intent=proposal.intent,
                amount=proposal.amount,
                currency="INR",
                summary=proposal.summary,
                raw_transcript=transcript,
                proposal_id=proposal.proposal_id,
            )
            staged = self.ledger_service.stage_proposal(store_id=store_id, request=stage_request, db=db)

            # Localized spoken confirmation prompt
            spoken = self.generate_spoken_prompt(
                intent=proposal.intent,
                customer_name=proposal.customer_name,
                amount=proposal.amount,
                language=resolved_lang,
            )
            audio = await self.synthesize_speech(spoken, resolved_lang)

            return VoiceOrchestratorResult(
                event_type="PROPOSAL_READY",
                transcript=transcript,
                language=resolved_lang,
                proposal=proposal,
                staged_proposal=staged,
                spoken_response=spoken,
                audio_bytes=audio,
            )

        elif proposal.intent == IntentType.QUERY_BALANCE:
            # Read-only query -> NO MUTATION
            if not proposal.customer_name:
                spoken = (
                    "ಯಾರ ಬಾಕಿ ತಿಳಿಯಬೇಕು? ದಯವಿಟ್ಟು ಗ್ರಾಹಕರ ಹೆಸರನ್ನು ಹೇಳಿ."
                    if self.normalize_language_code(resolved_lang) == "kn-IN"
                    else ("किसका बकाया जानना चाहते हैं? कृपया ग्राहक का नाम बताएं।"
                          if self.normalize_language_code(resolved_lang) == "hi-IN"
                          else "Whose balance would you like to check? Please state the customer name.")
                )
                audio = await self.synthesize_speech(spoken, resolved_lang)
                return VoiceOrchestratorResult(
                    event_type="CLARIFICATION_REQUIRED",
                    transcript=transcript,
                    language=resolved_lang,
                    proposal=proposal,
                    spoken_response=spoken,
                    audio_bytes=audio,
                )

            # Look up customer
            clean_name = proposal.customer_name.strip()
            cust = (
                db.query(Customer)
                .filter(
                    Customer.store_id == store_id,
                    Customer.normalized_name == clean_name.lower(),
                    Customer.is_active == True,
                )
                .first()
            )

            if not cust:
                spoken = (
                    f"ಕ್ಷಮಿಸಿ, {clean_name} ಎಂಬ ಗ್ರಾಹಕರು ಸಿಗಲಿಲ್ಲ."
                    if self.normalize_language_code(resolved_lang) == "kn-IN"
                    else (f"माफ़ कीजिए, {clean_name} नाम का कोई ग्राहक नहीं मिला।"
                          if self.normalize_language_code(resolved_lang) == "hi-IN"
                          else f"Customer {clean_name} was not found.")
                )
                audio = await self.synthesize_speech(spoken, resolved_lang)
                return VoiceOrchestratorResult(
                    event_type="READ_ONLY_RESPONSE",
                    transcript=transcript,
                    language=resolved_lang,
                    proposal=proposal,
                    read_only_data={"found": False, "customer_name": clean_name},
                    spoken_response=spoken,
                    audio_bytes=audio,
                )

            balance_res = self.ledger_service.get_customer_balance(store_id=store_id, customer_id=cust.id, db=db)
            spoken = self.generate_spoken_prompt(
                intent=IntentType.QUERY_BALANCE,
                customer_name=cust.customer_name,
                amount=None,
                language=resolved_lang,
                balance=balance_res.outstanding_balance,
            )
            audio = await self.synthesize_speech(spoken, resolved_lang)

            return VoiceOrchestratorResult(
                event_type="READ_ONLY_RESPONSE",
                transcript=transcript,
                language=resolved_lang,
                proposal=proposal,
                read_only_data={
                    "found": True,
                    "customer_id": cust.id,
                    "customer_name": cust.customer_name,
                    "outstanding_balance": str(balance_res.outstanding_balance),
                    "total_credit": str(balance_res.total_credit),
                    "total_payment": str(balance_res.total_payment),
                },
                spoken_response=spoken,
                audio_bytes=audio,
            )

        elif proposal.intent == IntentType.LIST_DUES:
            summary = self.ledger_service.get_store_ledger_summary(store_id=store_id, db=db)
            spoken = self.generate_spoken_prompt(
                intent=IntentType.LIST_DUES,
                customer_name=None,
                amount=None,
                language=resolved_lang,
            )
            audio = await self.synthesize_speech(spoken, resolved_lang)

            return VoiceOrchestratorResult(
                event_type="READ_ONLY_RESPONSE",
                transcript=transcript,
                language=resolved_lang,
                proposal=proposal,
                read_only_data={
                    "total_customers": summary.total_customers,
                    "total_outstanding_balance": str(summary.total_outstanding_balance),
                    "total_store_credit": str(summary.total_store_credit),
                    "total_store_payment": str(summary.total_store_payment),
                },
                spoken_response=spoken,
                audio_bytes=audio,
            )

        # UNKNOWN or unhandled intent
        spoken = self.generate_spoken_prompt(IntentType.UNKNOWN, None, None, resolved_lang)
        audio = await self.synthesize_speech(spoken, resolved_lang)
        return VoiceOrchestratorResult(
            event_type="CLARIFICATION_REQUIRED",
            transcript=transcript,
            language=resolved_lang,
            proposal=proposal,
            spoken_response=spoken,
            audio_bytes=audio,
        )
