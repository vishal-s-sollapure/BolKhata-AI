"""Voice processing package for BolKhata AI.

Features:
- Gnani Prisma v3.0 STT WebSocket Streaming client.
- Gnani Timbre v3.0 TTS WebSocket Streaming client.
- Signed 16-bit PCM 16kHz audio framing and validation.
- Native support for Kannada (kn-IN), Hindi (hi-IN), English (en-IN), and Indic code-mixing.
"""

from .audio import (
    CHANNELS_MONO,
    FRAME_DURATION_MS,
    SAMPLE_RATE_8K,
    SAMPLE_RATE_16K,
    SAMPLE_RATE_48K,
    SAMPLE_WIDTH_16BIT,
    STREAM_CHUNK_BYTES,
    STREAM_CHUNK_SAMPLES,
    generate_synthetic_pcm_speech_simulation,
    pcm_chunker,
    pcm_to_wav,
    strip_wav_header,
    validate_pcm_chunk,
    wav_to_pcm,
)
from .stt import (
    PRISMA_V3_FORMATS,
    PRISMA_V3_MODEL,
    SUPPORTED_STT_LANGUAGES,
    GnaniAuthenticationError,
    GnaniConnectionError,
    GnaniPrismaSTTClient,
    GnaniSTTError,
    GnaniUnsupportedLanguageError,
    PrismaTranscriptEvent,
    PrismaV3STTConfig,
)
from .tts import (
    LANGUAGE_VOICE_MAP,
    SUPPORTED_TTS_LANGUAGES,
    TIMBRE_V30_MODEL,
    TIMBRE_V30_VOICES,
    GnaniTimbreTTSClient,
    GnaniTTSAuthenticationError,
    GnaniTTSConnectionError,
    GnaniTTSError,
    GnaniUnsupportedVoiceError,
    TimbreV3TTSConfig,
)

__all__ = [
    # Audio constants & functions
    "SAMPLE_RATE_16K",
    "SAMPLE_RATE_8K",
    "SAMPLE_RATE_48K",
    "SAMPLE_WIDTH_16BIT",
    "CHANNELS_MONO",
    "STREAM_CHUNK_SAMPLES",
    "STREAM_CHUNK_BYTES",
    "FRAME_DURATION_MS",
    "validate_pcm_chunk",
    "pcm_chunker",
    "generate_synthetic_pcm_speech_simulation",
    "pcm_to_wav",
    "wav_to_pcm",
    "strip_wav_header",
    # STT
    "PRISMA_V3_MODEL",
    "SUPPORTED_STT_LANGUAGES",
    "PRISMA_V3_FORMATS",
    "PrismaV3STTConfig",
    "PrismaTranscriptEvent",
    "GnaniPrismaSTTClient",
    "GnaniSTTError",
    "GnaniAuthenticationError",
    "GnaniConnectionError",
    "GnaniUnsupportedLanguageError",
    # TTS
    "TIMBRE_V30_MODEL",
    "TIMBRE_V30_VOICES",
    "SUPPORTED_TTS_LANGUAGES",
    "LANGUAGE_VOICE_MAP",
    "TimbreV3TTSConfig",
    "GnaniTimbreTTSClient",
    "GnaniTTSError",
    "GnaniTTSAuthenticationError",
    "GnaniTTSConnectionError",
    "GnaniUnsupportedVoiceError",
]
