"""FastAPI endpoints for AI intent parsing and transaction proposal generation."""

from fastapi import APIRouter, HTTPException, status
from app.agent.intent_parser import (
    IntentParserAPIError,
    IntentParserConfigError,
)
from app.schemas.intent import (
    ParseIntentRequest,
    ParseIntentResponse,
)
from app.services.intent_service import IntentService
from app.utils.logger import configure_logger

logger = configure_logger("bolkhata.api.intent")
router = APIRouter(prefix="/intent", tags=["Intent Parsing"])

# Shared service instance
intent_service = IntentService()


@router.post(
    "/parse",
    response_model=ParseIntentResponse,
    status_code=status.HTTP_200_OK,
    summary="Parse voice transcript into transaction proposal",
    description="Processes a speech transcript from Gnani Prisma v3.0 through the Groq LLM "
                "intent parser and returns a validated TransactionProposal without mutating "
                "the database ledger.",
)
async def parse_intent(request: ParseIntentRequest) -> ParseIntentResponse:
    """Parses a merchant voice command into a structured transaction proposal."""
    transcript = request.transcript.strip()
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcript cannot be empty or whitespace.",
        )

    try:
        proposal = await intent_service.parse_transcript(
            transcript=transcript,
            language=request.language,
        )
        return ParseIntentResponse(
            success=True,
            original_transcript=request.transcript,
            proposal=proposal,
            error=None,
        )
    except ValueError as e:
        logger.warning("Validation error parsing intent: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except IntentParserConfigError as e:
        logger.error("Configuration error in intent parser: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Intent parser service not configured: {str(e)}",
        )
    except IntentParserAPIError as e:
        logger.error("Groq API error during intent parsing: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI parsing service unavailable: {str(e)}",
        )
    except Exception as e:
        logger.exception("Unexpected error in parse_intent endpoint: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while parsing the voice intent.",
        )
