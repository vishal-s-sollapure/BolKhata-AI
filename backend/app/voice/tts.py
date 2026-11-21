"""Gnani Timbre v3.0 Text-To-Speech (TTS) WebSocket Streaming Client.

Requirements:
- Model: Strictly 'timbre-v3.0' (no silent fallbacks or legacy models).
- Protocol: Gnani WebSocket Streaming Interface (wss://api.vachana.ai/api/v1/tts).
- Languages:
    - kn-IN: Kannada (Voices: Manjunath, Chetana, Lakshmi, Avinash)
    - hi-IN: Hindi (Voices: Avinash, Sneha, Santosh, Rekha)
    - en-IN: Indian English (Voices: Avinash, Sneha, Riyaa, Devansh)
- Audio Output: Linear 16-bit PCM Mono @ 16000 Hz or WAV container.
- Security: Never log API keys.
"""

import asyncio
import base64
import json
import uuid
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, List, Optional, Set
import websockets
from websockets.exceptions import ConnectionClosed

from app.config.settings import get_settings
from app.utils.logger import configure_logger
from app.voice.audio import (
    SAMPLE_RATE_16K,
    strip_wav_header,
)

logger = configure_logger("bolkhata.voice.tts")

# Strict Timbre Model Identifier
TIMBRE_V30_MODEL = "timbre-v3.0"

# Verified Timbre v3.0 Voice Catalogue
TIMBRE_V30_VOICES: Set[str] = {
    "Harshad", "Rekha", "Santosh", "Rajeev", "Vikramdasu", "Rajni",
    "Avinash", "Arko", "Manjunath", "Yashraj", "Tarika", "Lakshmidevi",
    "Sneha", "Riyaa", "Shubham", "Rahulmehta", "Rakesh", "Priyasharm",
    "Vasudha", "Anitasingh", "Sohini", "Nitin", "Chetana", "Lakshmi",
    "Swathi", "Prakash", "Vinod", "Neelam", "Devansh", "Mahendra",
    "Kalpana", "Shivani", "Sunaina", "Shruthi",
}

# Recommended Voices per Language for BolKhata AI
LANGUAGE_VOICE_MAP: Dict[str, Dict[str, str]] = {
    "kn-IN": {
        "default": "Manjunath",
        "male": "Manjunath",
        "female": "Chetana",
        "alt": "Lakshmi",
    },
    "hi-IN": {
        "default": "Avinash",
        "male": "Avinash",
        "female": "Sneha",
        "alt": "Santosh",
    },
    "en-IN": {
        "default": "Avinash",
        "male": "Avinash",
        "female": "Sneha",
        "alt": "Devansh",
    },
}

SUPPORTED_TTS_LANGUAGES: Set[str] = {"kn-IN", "hi-IN", "en-IN", "auto"}


class GnaniTTSError(Exception):
    """Base exception for Gnani TTS operations."""
    pass


class GnaniTTSAuthenticationError(GnaniTTSError):
    """Raised when authentication fails with Gnani API key."""
    pass


class GnaniTTSConnectionError(GnaniTTSError):
    """Raised when WebSocket connection fails or terminates unexpectedly."""
    pass


class GnaniUnsupportedVoiceError(GnaniTTSError):
    """Raised when an unsupported voice or language combination is requested."""
    pass


@dataclass
class TimbreV3TTSConfig:
    """Configuration parameters for Timbre v3.0 TTS session."""
    model: str = TIMBRE_V30_MODEL
    voice: str = "Avinash"
    language: str = "kn-IN"
    speed: float = 1.0
    sample_rate: int = SAMPLE_RATE_16K
    encoding: str = "linear_pcm"
    container: str = "wav"  # "wav" or "raw"

    def validate(self) -> None:
        """Validates configuration parameters against official Timbre v3.0 rules."""
        if self.model != TIMBRE_V30_MODEL:
            raise ValueError(f"TTS model must be explicitly '{TIMBRE_V30_MODEL}', got '{self.model}'")
        if self.voice not in TIMBRE_V30_VOICES:
            raise GnaniUnsupportedVoiceError(
                f"Voice '{self.voice}' is not a valid Timbre v3.0 voice. "
                f"Allowed voices include: {sorted(list(TIMBRE_V30_VOICES))[:10]}..."
            )
        if self.language not in SUPPORTED_TTS_LANGUAGES:
            raise GnaniTTSError(
                f"Language '{self.language}' not supported. Allowed: {SUPPORTED_TTS_LANGUAGES}"
            )
        if not (0.5 <= self.speed <= 2.0):
            raise ValueError(f"Speed must be between 0.5 and 2.0, got {self.speed}")


class GnaniTimbreTTSClient:
    """Async WebSocket streaming client for Gnani Timbre v3.0 TTS.
    
    Provides low-latency speech synthesis over a persistent WebSocket connection.
    Yields synthesized audio chunks as they arrive from the server.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[TimbreV3TTSConfig] = None,
        ws_url: Optional[str] = None,
    ):
        settings = get_settings()
        self.api_key = settings.GNANI_API_KEY if api_key is None else api_key
        self.config = config or TimbreV3TTSConfig()
        self.config.validate()

        # Default canonical WebSocket endpoint: wss://api.vachana.ai/api/v1/tts
        self.ws_url = ws_url or settings.GNANI_TIMBRE_WS_URL
        if "api.gnani.ai" in self.ws_url:
            self.ws_url = "wss://api.vachana.ai/api/v1/tts"

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._session_id = str(uuid.uuid4())
        self._connected = False

    def _build_headers(self) -> Dict[str, str]:
        """Constructs headers for Gnani Timbre v3.0 WebSocket handshake."""
        if not self.api_key or self.api_key.startswith("your_"):
            raise GnaniTTSAuthenticationError(
                "Missing or unconfigured GNANI_API_KEY. "
                "Provide a valid Gnani API key in backend environment."
            )

        return {
            "Content-Type": "application/json",
            "X-API-Key-ID": self.api_key,
            "X-API-Request-ID": self._session_id,
        }

    async def connect(self) -> None:
        """Opens the persistent WebSocket connection to Timbre v3.0."""
        headers = self._build_headers()
        logger.info(
            "Connecting to Timbre v3.0 TTS WebSocket [model=%s, voice=%s, lang=%s]...",
            self.config.model,
            self.config.voice,
            self.config.language,
        )

        try:
            self._ws = await websockets.connect(
                self.ws_url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10,
            )
            self._connected = True
            logger.info("Timbre v3.0 TTS WebSocket connected successfully.")

        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "403" in err_str or (hasattr(e, "status_code") and e.status_code in (401, 403)):
                raise GnaniTTSAuthenticationError(f"Gnani TTS authentication failed (Unauthorized / Invalid GNANI_API_KEY): {e}")
            if isinstance(e, (GnaniTTSAuthenticationError, GnaniUnsupportedVoiceError)):
                raise
            raise GnaniTTSConnectionError(f"Failed to connect to Timbre v3.0 WebSocket: {e}")

    def build_synthesis_payload(self, text: str) -> Dict:
        """Creates the JSON payload for a synthesis request adhering to Timbre v3.0 schema."""
        if not text or not text.strip():
            raise ValueError("Text to synthesize cannot be empty.")

        return {
            "text": text.strip(),
            "model": self.config.model,
            "voice": self.config.voice,
            "language": self.config.language,
            "speed": self.config.speed,
            "audio_config": {
                "sample_rate": self.config.sample_rate,
                "encoding": self.config.encoding,
                "num_channels": 1,
                "sample_width": 2,
                "container": self.config.container,
            },
        }

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Sends synthesis request and yields audio chunks as they arrive.
        
        Args:
            text: Text to synthesize into speech.
            
        Yields:
            Raw audio chunks (bytes).
        """
        if not self._ws or not self._connected:
            await self.connect()

        payload = self.build_synthesis_payload(text)
        await self._ws.send(json.dumps(payload))

        try:
            async for raw_message in self._ws:
                if isinstance(raw_message, bytes):
                    # Direct binary PCM frame
                    if raw_message:
                        yield raw_message
                    continue

                try:
                    data = json.loads(raw_message)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type", "")

                if msg_type == "audio":
                    nested_data = data.get("data", {})
                    audio_b64 = nested_data.get("audio") if isinstance(nested_data, dict) else data.get("audio")
                    if audio_b64:
                        audio_chunk = base64.b64decode(audio_b64)
                        if audio_chunk:
                            yield audio_chunk

                elif msg_type == "complete":
                    # Synthesis for this utterance is complete
                    break

                elif msg_type == "error":
                    err_msg = data.get("message", "Error during Timbre TTS synthesis")
                    raise GnaniTTSError(f"Timbre v3.0 synthesis error: {err_msg}")

        except ConnectionClosed:
            self._connected = False
            logger.info("Timbre v3.0 WebSocket closed.")

    async def synthesize(self, text: str, strip_header: bool = False) -> bytes:
        """Convenience method to synthesize text and collect full audio bytes.
        
        Args:
            text: Text to synthesize.
            strip_header: If True and container is WAV, strips the header and returns raw PCM.
        """
        chunks = []
        async for chunk in self.synthesize_stream(text):
            chunks.append(chunk)

        full_audio = b"".join(chunks)
        if strip_header and self.config.container == "wav":
            return strip_wav_header(full_audio)
        return full_audio

    async def close(self) -> None:
        """Closes the WebSocket connection."""
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
