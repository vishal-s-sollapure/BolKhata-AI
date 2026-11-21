"""Intent parsing and transaction proposal service for BolKhata AI."""

from typing import Optional
from app.agent.intent_parser import GroqIntentParser
from app.schemas.intent import TransactionProposal
from app.utils.logger import configure_logger

logger = configure_logger("bolkhata.services.intent_service")


class IntentService:
    """Service orchestrating AI voice transcript interpretation.
    
    IMPORTANT SAFETY GUARANTEE:
    This service is strictly decoupled from the ledger. It has ZERO access to
    database sessions, models, or mutation functions. It produces proposals
    that require explicit human merchant confirmation before any ledger write.
    """

    def __init__(self, parser: Optional[GroqIntentParser] = None) -> None:
        self.parser = parser or GroqIntentParser()

    async def parse_transcript(
        self,
        transcript: str,
        language: Optional[str] = None,
    ) -> TransactionProposal:
        """Parses a merchant voice transcript into a structured TransactionProposal.
        
        Args:
            transcript: Transcribed text from voice engine (Gnani Prisma v3.0).
            language: Utterance language code (kn-IN, hi-IN, en-IN, indic-auto).
            
        Returns:
            Validated TransactionProposal.
        """
        logger.info("Parsing transcript via IntentService (lang: %s)", language or "unspecified")
        return await self.parser.parse(transcript=transcript, language=language)
