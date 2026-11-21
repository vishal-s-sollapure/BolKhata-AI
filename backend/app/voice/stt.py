"""Gnani Prisma v3.0 Speech-To-Text (STT) WebSocket Streaming Client.

Requirements:
- Model: Strictly 'prisma-v3.0' (no silent fallbacks or legacy models).
- Protocol: Gnani WebSocket Streaming Interface (wss://api.vachana.ai/stt/v3/stream).
- Languages:
    - kn-IN: Kannada
    - hi-IN: Hindi
    - en-IN: Indian English
    - indic-auto: Automatic Indic language identification and code-mixed speech recognition.
- Audio Format: Signed 16-bit PCM Mono Little-Endian @ 16000 Hz.
- Security: Never log API keys or raw private voice audio.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List, Optional, Set
import websockets
from websockets.exceptions import ConnectionClosed

from app.config.settings import get_settings
from app.utils.logger import configure_logger
from app.voice.audio import (
    SAMPLE_RATE_16K,
    STREAM_CHUNK_BYTES,
    validate_pcm_chunk,
)

logger = configure_logger("bolkhata.voice.stt")

# Strict Prisma Model Identifier
PRISMA_V3_MODEL = "prisma-v3.0"

# Supported Language Codes
SUPPORTED_STT_LANGUAGES: Dict[str, str] = {
    "kn-IN": "Kannada",
    "hi-IN": "Hindi",
    "en-IN": "English (India)",
    "indic-auto": "Indic Auto Language Identification (Code-Mixed)",
}

# Formats supported by Prisma v3.0
PRISMA_V3_FORMATS: Set[str] = {"transcribe", "codemix", "verbatim", "transliterate"}


class GnaniSTTError(Exception):
    """Base exception for Gnani STT operations."""
    pass


class GnaniAuthenticationError(GnaniSTTError):
    """Raised when authentication fails with Gnani API key."""
    pass


class GnaniConnectionError(GnaniSTTError):
    """Raised when WebSocket connection fails or terminates unexpectedly."""
    pass


class GnaniUnsupportedLanguageError(GnaniSTTError):
    """Raised when an unsupported language code is requested."""
    pass


@dataclass
class PrismaV3STTConfig:
    """Configuration parameters for Prisma v3.0 STT session."""
    model: str = PRISMA_V3_MODEL
    language_code: str = "kn-IN"
    sample_rate: int = SAMPLE_RATE_16K
    format: str = "codemix"  # "codemix" or "transcribe" for Indian Kirana voice
    enable_itn: bool = True  # Inverse Text Normalization (e.g. ₹250 instead of two hundred fifty rupees)
    itn_native_numerals: bool = False
    language_candidates: List[str] = field(default_factory=lambda: ["kn-IN", "hi-IN", "en-IN"])
    vad_threshold: float = 0.7
    min_silence_ms: int = 500
    min_speech_ms: int = 100
    idle_timeout_sec: int = 60

    def validate(self) -> None:
        """Validates configuration parameters."""
        if self.model != PRISMA_V3_MODEL:
            raise ValueError(f"STT model must be explicitly '{PRISMA_V3_MODEL}', got '{self.model}'")
        if self.language_code not in SUPPORTED_STT_LANGUAGES:
            raise GnaniUnsupportedLanguageError(
                f"Language '{self.language_code}' is not supported. "
                f"Supported options: {list(SUPPORTED_STT_LANGUAGES.keys())}"
            )
        if self.format not in PRISMA_V3_FORMATS:
            raise ValueError(f"Format '{self.format}' not supported. Allowed: {PRISMA_V3_FORMATS}")
        if self.sample_rate not in (8000, 16000, 44100, 48000):
            raise ValueError(f"Sample rate {self.sample_rate} not supported.")


@dataclass
class PrismaTranscriptEvent:
    """Represents a speech recognition transcript event from Prisma v3.0."""
    text: str
    is_final: bool
    detected_language_code: Optional[str] = None
    confidence: Optional[float] = None
    words: Optional[List[Dict]] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    raw_payload: Optional[Dict] = None


class GnaniPrismaSTTClient:
    """Async WebSocket streaming client for Gnani Prisma v3.0 STT.
    
    Provides low-latency real-time voice streaming with server-side VAD,
    partial and final transcription events, and Indian language code-mixing.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[PrismaV3STTConfig] = None,
        ws_url: Optional[str] = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.GNANI_API_KEY
        self.config = config or PrismaV3STTConfig()
        self.config.validate()
        
        # Default canonical WebSocket endpoint: wss://api.vachana.ai/stt/v3/stream
        self.ws_url = ws_url or settings.GNANI_PRISMA_WS_URL
        if "api.gnani.ai" in self.ws_url:
            # Normalize to active production domain if default legacy domain was set
            self.ws_url = "wss://api.vachana.ai/stt/v3/stream"

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._session_id = str(uuid.uuid4())
        self._connected = False

    def _build_headers(self) -> Dict[str, str]:
        """Constructs headers for Gnani Prisma v3.0 WebSocket handshake."""
        if not self.api_key or self.api_key.startswith("your_"):
            raise GnaniAuthenticationError(
                "Missing or unconfigured GNANI_API_KEY. "
                "Provide a valid Gnani API key in backend environment."
            )

        headers = {
            "x-api-key-id": self.api_key,
            "x-model": self.config.model,
            "x-language": self.config.language_code,
            "x-sample-rate": str(self.config.sample_rate),
            "x-format": self.config.format,
            "x-enable-itn": "true" if self.config.enable_itn else "false",
            "x-api-request-id": self._session_id,
            "x-vad-threshold": str(self.config.vad_threshold),
            "x-min-silence-ms": str(self.config.min_silence_ms),
            "x-min-speech-ms": str(self.config.min_speech_ms),
        }

        # If indic-auto is active, pass candidate languages
        if self.config.language_code == "indic-auto" and self.config.language_candidates:
            headers["x-language-candidates"] = ",".join(self.config.language_candidates)

        return headers

    async def connect(self) -> None:
        """Opens the WebSocket connection to Prisma v3.0."""
        headers = self._build_headers()
        logger.info(
            "Connecting to Prisma v3.0 STT WebSocket [model=%s, lang=%s, format=%s, session=%s]...",
            self.config.model,
            self.config.language_code,
            self.config.format,
            self._session_id[:8],
        )

        try:
            self._ws = await websockets.connect(
                self.ws_url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10,
            )
            
            # Wait for the initial server confirmation message
            first_msg = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
            if isinstance(first_msg, str):
                data = json.loads(first_msg)
                msg_type = data.get("type", "")
                if msg_type == "connected":
                    logger.info("Prisma v3.0 WebSocket successfully connected.")
                    self._connected = True
                elif msg_type == "error":
                    err_msg = data.get("message", "Unknown error on connection")
                    raise GnaniConnectionError(f"Prisma v3.0 server error: {err_msg}")
                else:
                    self._connected = True
            else:
                self._connected = True

        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code in (401, 403):
                raise GnaniAuthenticationError(f"Gnani STT authentication failed (HTTP {e.status_code})")
            raise GnaniConnectionError(f"Prisma v3.0 connection failed with status {e.status_code}: {e}")
        except Exception as e:
            if isinstance(e, (GnaniAuthenticationError, GnaniUnsupportedLanguageError)):
                raise
            raise GnaniConnectionError(f"Failed to connect to Prisma v3.0 WebSocket: {e}")

    async def send_audio_chunk(self, chunk: bytes) -> None:
        """Sends a raw 16-bit PCM audio chunk over the WebSocket.
        
        Args:
            chunk: Signed 16-bit linear PCM audio chunk (1024 bytes recommended).
        """
        if not self._ws or not self._connected:
            raise GnaniConnectionError("Prisma v3.0 WebSocket is not connected.")
        if not validate_pcm_chunk(chunk):
            raise ValueError(f"Invalid PCM chunk: length must be even (got {len(chunk)} bytes).")

        try:
            await self._ws.send(chunk)
        except ConnectionClosed as e:
            self._connected = False
            raise GnaniConnectionError(f"Prisma v3.0 WebSocket closed during audio streaming: {e}")

    async def receive_events(self) -> AsyncGenerator[PrismaTranscriptEvent, None]:
        """Asynchronously yields transcript events as they arrive from the server."""
        if not self._ws or not self._connected:
            raise GnaniConnectionError("Prisma v3.0 WebSocket is not connected.")

        try:
            async for raw_message in self._ws:
                if isinstance(raw_message, bytes):
                    # Prisma STT sends text/JSON responses; binary responses are skipped
                    continue

                try:
                    payload = json.loads(raw_message)
                except json.JSONDecodeError:
                    logger.warning("Received unparseable JSON from Prisma STT")
                    continue

                event_type = payload.get("type", "")
                if event_type == "error":
                    err_message = payload.get("message", "Gnani STT error received")
                    logger.error("Prisma v3.0 error event: %s", err_message)
                    raise GnaniConnectionError(f"Prisma v3.0 error: {err_message}")

                # Process transcript payload
                # Structure: {"type": "transcript", "text": "...", "is_final": bool, ...}
                text = payload.get("text", "") or payload.get("transcript", "")
                if text:
                    is_final = bool(payload.get("is_final", False))
                    detected_lang = payload.get("detected_language_code") or payload.get("language")
                    confidence = payload.get("confidence")
                    words = payload.get("words")
                    start_time = payload.get("start_time")
                    end_time = payload.get("end_time")

                    yield PrismaTranscriptEvent(
                        text=text,
                        is_final=is_final,
                        detected_language_code=detected_lang,
                        confidence=confidence,
                        words=words,
                        start_time=start_time,
                        end_time=end_time,
                        raw_payload=payload,
                    )

        except ConnectionClosed:
            self._connected = False
            logger.info("Prisma v3.0 WebSocket closed cleanly.")

    async def close(self) -> None:
        """Closes the WebSocket connection cleanly."""
        self._connected = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
