"""Real-time Voice-to-Voice Streaming WebSocket and REST API for BolKhata AI.

Endpoints:
- WebSocket `/stream` (mounted at `/api/v1/voice/stream` and `/api/voice/stream`)
  Bi-directional audio streaming proxy between browser microphone and Gnani Prisma v3.0 STT,
  coupled to Groq Intent Parser, Ledger Staging Engine, and Gnani Timbre v3.0 TTS.
- POST `/process-transcript`
  HTTP endpoint to execute voice-orchestrated intent parsing and proposal staging.
- POST `/synthesize`
  HTTP endpoint for on-demand localized Kirana speech synthesis via Timbre v3.0.
"""

import asyncio
import base64
import json
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database.session import SessionLocal, get_db
from app.models.kirana_store import KiranaStore
from app.schemas.intent import TransactionProposal
from app.schemas.ledger import PendingProposalResponse
from app.services.store_service import StoreService
from app.services.voice_orchestrator import VoiceOrchestrator, VoiceOrchestratorResult
from app.utils.logger import configure_logger
from app.voice.audio import SAMPLE_RATE_16K, validate_pcm_chunk
from app.voice.stt import (
    SUPPORTED_STT_LANGUAGES,
    GnaniAuthenticationError,
    GnaniConnectionError,
    GnaniPrismaSTTClient,
    PrismaV3STTConfig,
)
from app.voice.tts import GnaniTimbreTTSClient

logger = configure_logger("bolkhata.api.voice")
router = APIRouter(prefix="/voice", tags=["Voice Engine"])
settings = get_settings()


class ProcessTranscriptRequest(BaseModel):
    """Request payload to process an utterance transcript through voice orchestrator."""
    transcript: str = Field(..., min_length=1, max_length=1000, description="Transcribed voice text")
    language: Optional[str] = Field("kn-IN", description="Language code (kn-IN, hi-IN, en-IN, indic-auto)")


class SynthesizeSpeechRequest(BaseModel):
    """Request payload to synthesize speech text into audio."""
    text: str = Field(..., min_length=1, max_length=1000, description="Text to synthesize into speech")
    language: Optional[str] = Field("kn-IN", description="Language code (kn-IN, hi-IN, en-IN)")


class VoiceProcessResponse(BaseModel):
    """Response from processing a voice transcript."""
    event_type: str
    transcript: str
    language: str
    spoken_response: str
    proposal: Optional[Dict[str, Any]] = None
    staged_proposal: Optional[Dict[str, Any]] = None
    read_only_data: Optional[Dict[str, Any]] = None
    audio_b64: Optional[str] = None
    audio_format: str = "audio/wav"


class SynthesizeSpeechResponse(BaseModel):
    """Response containing synthesized speech audio."""
    audio_b64: Optional[str]
    audio_format: str = "audio/wav"
    text: str
    language: str


@router.websocket("/stream")
async def voice_streaming_endpoint(
    websocket: WebSocket,
    store_id: Optional[str] = Query(None, description="Optional Kirana Store UUID"),
    lang: Optional[str] = Query("indic-auto", description="Initial language code"),
    db: Session = Depends(get_db),
):
    """Bidirectional WebSocket streaming interface for merchant voice interactions.
    
    Flow:
    1. Browser connects, server verifies store and sends SESSION_STARTED.
    2. Browser streams raw 16kHz S16LE PCM chunks as binary frames.
    3. Server proxies audio to Gnani Prisma v3.0 STT over WebSocket.
    4. Server emits PARTIAL_TRANSCRIPT events back to browser for live feedback.
    5. Upon final speech segment (or END_AUDIO / SIMULATE_TRANSCRIPT):
       - Server emits FINAL_TRANSCRIPT.
       - Server emits PROCESSING.
       - GroqIntentParser parses utterance.
       - If CREDIT or PAYMENT: LedgerService STAGES proposal (PendingProposal) - NEVER commits automatically.
       - Gnani Timbre v3.0 synthesizes spoken confirmation audio.
       - Server emits PROPOSAL_READY (or READ_ONLY_RESPONSE or CLARIFICATION_REQUIRED) with audio payload.
    """
    await websocket.accept()

    session_id = str(uuid.uuid4())

    # 1. Resolve store context
    try:
        resolved_store_id = store_id
        if not resolved_store_id:
            default_store = StoreService.get_or_create_default_store(db)
            resolved_store_id = default_store.id
        else:
            store = db.query(KiranaStore).filter(KiranaStore.id == resolved_store_id, KiranaStore.is_active == True).first()
            if not store:
                await websocket.send_json({
                    "event": "ERROR",
                    "code": "STORE_NOT_FOUND",
                    "message": f"Active Kirana store '{resolved_store_id}' was not found.",
                })
                await websocket.close(code=4004)
                return
    except Exception as e:
        logger.error("Error resolving store in voice websocket: %s", e)
        await websocket.send_json({
            "event": "ERROR",
            "code": "STORE_INIT_FAILED",
            "message": "Failed to initialize store context.",
        })
        await websocket.close(code=1011)
        return

    # 2. Emit SESSION_STARTED frame
    initial_language = lang if lang in SUPPORTED_STT_LANGUAGES else "indic-auto"
    await websocket.send_json({
        "event": "SESSION_STARTED",
        "session_id": session_id,
        "store_id": resolved_store_id,
        "sample_rate": SAMPLE_RATE_16K,
        "format": "s16le",
        "channels": 1,
        "language": initial_language,
    })

    # 3. Initialize components
    orchestrator = VoiceOrchestrator()
    stt_config = PrismaV3STTConfig(
        language_code=initial_language,
        sample_rate=SAMPLE_RATE_16K,
        format="codemix",
    )
    stt_client = GnaniPrismaSTTClient(config=stt_config)
    stt_connected = False

    try:
        await stt_client.connect()
        stt_connected = True
        logger.info("Session %s: Connected to Gnani Prisma v3.0 STT WebSocket.", session_id[:8])
    except (GnaniAuthenticationError, GnaniConnectionError, Exception) as e:
        logger.warning(
            "Session %s: Live Prisma STT connection unavailable (%s). Operating in offline/simulated fallback mode.",
            session_id[:8],
            e,
        )
        stt_connected = False

    session_state = {
        "is_canceled": False,
        "active": True,
        "language": initial_language,
        "processing_final": False,
    }

    async def handle_final_processing(transcript: str, detected_lang: Optional[str]):
        """Processes final transcript through orchestrator and delivers event to client."""
        if session_state["is_canceled"]:
            return

        session_state["processing_final"] = True
        try:
            await websocket.send_json({
                "event": "PROCESSING",
                "session_id": session_id,
                "status": "PARSING_INTENT",
            })

            result: VoiceOrchestratorResult = await orchestrator.process_utterance(
                store_id=resolved_store_id,
                transcript=transcript,
                language_hint=detected_lang or session_state["language"],
                db=db,
            )

            client_event = result.to_client_event(session_id)
            await websocket.send_json(client_event)

            # Also stream optional standalone TTS_AUDIO event if audio was generated
            if result.audio_bytes:
                await websocket.send_json({
                    "event": "TTS_AUDIO",
                    "session_id": session_id,
                    "audio_b64": base64.b64encode(result.audio_bytes).decode("ascii"),
                    "audio_format": "audio/wav",
                    "text": result.spoken_response,
                })

        except Exception as proc_err:
            logger.exception("Error processing final transcript in voice websocket: %s", proc_err)
            await websocket.send_json({
                "event": "ERROR",
                "session_id": session_id,
                "code": "VOICE_PROCESSING_FAILED",
                "message": f"Failed to process transcript: {str(proc_err)}",
            })
        finally:
            session_state["processing_final"] = False

    async def stt_event_pump():
        """Pumps events from Prisma STT client to client websocket."""
        if not stt_connected:
            return

        try:
            async for event in stt_client.receive_events():
                if session_state["is_canceled"] or not session_state["active"]:
                    break

                if not event.is_final:
                    await websocket.send_json({
                        "event": "PARTIAL_TRANSCRIPT",
                        "session_id": session_id,
                        "transcript": event.transcript,
                        "is_final": False,
                        "language": event.language,
                    })
                else:
                    await websocket.send_json({
                        "event": "FINAL_TRANSCRIPT",
                        "session_id": session_id,
                        "transcript": event.transcript,
                        "is_final": True,
                        "language": event.language,
                        "confidence": event.confidence,
                    })
                    await handle_final_processing(event.transcript, event.language)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if session_state["active"]:
                logger.warning("Session %s STT pump ended: %s", session_id[:8], e)

    stt_task = asyncio.create_task(stt_event_pump()) if stt_connected else None

    # 4. Client WebSocket message receiver loop
    try:
        while session_state["active"]:
            raw_msg = await websocket.receive()
            msg_type = raw_msg.get("type", "")

            if msg_type == "websocket.disconnect":
                break

            # A. Binary PCM audio chunk from microphone
            if "bytes" in raw_msg and raw_msg["bytes"]:
                chunk = raw_msg["bytes"]
                if validate_pcm_chunk(chunk):
                    if stt_connected:
                        try:
                            await stt_client.send_audio_chunk(chunk)
                        except Exception as send_err:
                            logger.debug("Failed sending chunk to STT: %s", send_err)
                else:
                    logger.warning(
                        "Rejected invalid or oversized PCM chunk (%d bytes)",
                        len(chunk) if isinstance(chunk, (bytes, bytearray)) else 0,
                    )

            # B. Text JSON control frames
            elif "text" in raw_msg and raw_msg["text"]:
                try:
                    payload = json.loads(raw_msg["text"])
                except json.JSONDecodeError:
                    continue

                action = payload.get("action", "")

                if action == "START_SESSION":
                    new_lang = payload.get("language")
                    if new_lang and new_lang in SUPPORTED_STT_LANGUAGES:
                        session_state["language"] = new_lang
                    session_state["is_canceled"] = False

                elif action == "END_AUDIO":
                    logger.debug("Client signaled END_AUDIO for session %s", session_id[:8])

                elif action == "CANCEL_SESSION":
                    session_state["is_canceled"] = True
                    await websocket.send_json({
                        "event": "SESSION_ENDED",
                        "session_id": session_id,
                        "reason": "canceled_by_client",
                    })

                elif action == "SIMULATE_TRANSCRIPT":
                    # Allows automated tests and simulated offline inputs
                    test_transcript = payload.get("transcript", "")
                    test_lang = payload.get("language", session_state["language"])
                    if test_transcript:
                        await websocket.send_json({
                            "event": "FINAL_TRANSCRIPT",
                            "session_id": session_id,
                            "transcript": test_transcript,
                            "is_final": True,
                            "language": test_lang,
                            "confidence": 0.95,
                        })
                        await handle_final_processing(test_transcript, test_lang)

                elif action == "PING":
                    await websocket.send_json({
                        "event": "PONG",
                        "timestamp": payload.get("timestamp"),
                    })

    except WebSocketDisconnect:
        logger.info("Session %s: Client disconnected.", session_id[:8])
    except Exception as ws_err:
        logger.warning("Session %s WebSocket loop error: %s", session_id[:8], ws_err)
    finally:
        session_state["active"] = False
        if stt_task:
            stt_task.cancel()
            try:
                await stt_task
            except asyncio.CancelledError:
                pass

        if stt_connected:
            await stt_client.close()

        logger.info("Session %s cleaned up successfully.", session_id[:8])


@router.post("/process-transcript", response_model=VoiceProcessResponse, summary="Process Spoken Transcript")
async def process_voice_transcript(
    request: ProcessTranscriptRequest,
    store_id: Optional[str] = Query(None, description="Optional Store ID"),
    db: Session = Depends(get_db),
):
    """Processes a transcribed merchant utterance directly, returning structured proposal and spoken audio."""
    resolved_store_id = store_id
    if not resolved_store_id:
        default_store = StoreService.get_or_create_default_store(db)
        resolved_store_id = default_store.id

    orchestrator = VoiceOrchestrator()
    result = await orchestrator.process_utterance(
        store_id=resolved_store_id,
        transcript=request.transcript,
        language_hint=request.language or "kn-IN",
        db=db,
    )

    audio_b64 = base64.b64encode(result.audio_bytes).decode("ascii") if result.audio_bytes else None

    proposal_dict = None
    if result.proposal:
        proposal_dict = result.proposal.model_dump()
        if proposal_dict.get("amount") is not None:
            proposal_dict["amount"] = str(proposal_dict["amount"])

    staged_dict = None
    if result.staged_proposal:
        staged_dict = result.staged_proposal.model_dump()
        if staged_dict.get("created_at"):
            staged_dict["created_at"] = staged_dict["created_at"].isoformat()
        if staged_dict.get("expires_at"):
            staged_dict["expires_at"] = staged_dict["expires_at"].isoformat()

    return VoiceProcessResponse(
        event_type=result.event_type,
        transcript=result.transcript,
        language=result.language,
        spoken_response=result.spoken_response,
        proposal=proposal_dict,
        staged_proposal=staged_dict,
        read_only_data=result.read_only_data,
        audio_b64=audio_b64,
        audio_format=result.audio_format,
    )


@router.post("/synthesize", response_model=SynthesizeSpeechResponse, summary="Synthesize Text-To-Speech")
async def synthesize_speech_endpoint(
    request: SynthesizeSpeechRequest,
):
    """Synthesizes text into high-fidelity speech audio via Gnani Timbre v3.0."""
    orchestrator = VoiceOrchestrator()
    audio_bytes = await orchestrator.synthesize_speech(
        text=request.text,
        language=request.language or "kn-IN",
    )
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii") if audio_bytes else None

    return SynthesizeSpeechResponse(
        audio_b64=audio_b64,
        audio_format="audio/wav",
        text=request.text,
        language=request.language or "kn-IN",
    )
