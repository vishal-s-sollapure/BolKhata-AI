"""Unit and Integration tests for Gnani Prisma v3.0 Speech-To-Text client.

Covers:
- Configuration and model selection (Prisma v3.0 strict requirement)
- Missing API key handling
- Unsupported language validation
- Audio PCM framing and validation
- WebSocket connection lifecycle & mock streaming
- Live API integration test (marked with pytest.mark.integration, skipped if no credentials)
"""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.voice.audio import (
    SAMPLE_RATE_16K,
    STREAM_CHUNK_BYTES,
    generate_synthetic_pcm_speech_simulation,
    pcm_chunker,
    validate_pcm_chunk,
)
from app.voice.stt import (
    PRISMA_V3_MODEL,
    SUPPORTED_STT_LANGUAGES,
    GnaniAuthenticationError,
    GnaniConnectionError,
    GnaniPrismaSTTClient,
    GnaniUnsupportedLanguageError,
    PrismaTranscriptEvent,
    PrismaV3STTConfig,
)


class TestPrismaV3Config:
    """Test suite for Prisma v3.0 configuration validation."""

    def test_default_config_is_prisma_v3(self):
        """Verify default model is explicitly prisma-v3.0."""
        config = PrismaV3STTConfig()
        assert config.model == "prisma-v3.0"
        assert config.language_code == "kn-IN"
        assert config.sample_rate == 16000
        assert config.format == "codemix"

    def test_reject_non_prisma_model(self):
        """Verify that any non-prisma-v3.0 model is rejected."""
        config = PrismaV3STTConfig(model="older-model-v2")
        with pytest.raises(ValueError, match="STT model must be explicitly 'prisma-v3.0'"):
            config.validate()

    def test_supported_languages(self):
        """Verify Kannada, Hindi, English, and indic-auto are accepted."""
        for lang in ["kn-IN", "hi-IN", "en-IN", "indic-auto"]:
            config = PrismaV3STTConfig(language_code=lang)
            config.validate()
            assert config.language_code in SUPPORTED_STT_LANGUAGES

    def test_reject_unsupported_language(self):
        """Verify that unsupported language codes raise GnaniUnsupportedLanguageError."""
        config = PrismaV3STTConfig(language_code="fr-FR")
        with pytest.raises(GnaniUnsupportedLanguageError, match="Language 'fr-FR' is not supported"):
            config.validate()

    def test_reject_unsupported_format(self):
        """Verify format validation."""
        config = PrismaV3STTConfig(format="invalid-format")
        with pytest.raises(ValueError, match="Format 'invalid-format' not supported"):
            config.validate()


class TestPrismaV3AudioValidation:
    """Test suite for audio framing matching Gnani Prisma specifications."""

    def test_valid_pcm_chunk_alignment(self):
        """PCM chunk must be aligned to 16-bit boundaries (even byte count)."""
        valid_chunk = b"\x00\x00" * 256  # 512 bytes = 256 samples
        assert validate_pcm_chunk(valid_chunk) is True

    def test_invalid_odd_pcm_chunk(self):
        """Odd number of bytes violates 16-bit sample alignment."""
        odd_chunk = b"\x00\x00\x01"
        assert validate_pcm_chunk(odd_chunk) is False

    def test_empty_pcm_chunk(self):
        """Empty chunk is rejected unless partial allowed."""
        assert validate_pcm_chunk(b"") is False
        assert validate_pcm_chunk(b"", allow_partial=True) is True

    def test_pcm_chunker_generates_exact_frame_size(self):
        """Chunker produces 1024-byte chunks matching Gnani STREAM_CHUNK_BYTES."""
        raw_pcm = generate_synthetic_pcm_speech_simulation(duration_seconds=0.1, sample_rate=16000)
        chunks = list(pcm_chunker(raw_pcm, chunk_size=STREAM_CHUNK_BYTES))
        assert len(chunks) > 0
        # All chunks except possibly the last should be exactly 1024 bytes
        for chunk in chunks[:-1]:
            assert len(chunk) == STREAM_CHUNK_BYTES
            assert validate_pcm_chunk(chunk) is True
        assert validate_pcm_chunk(chunks[-1]) is True


class TestPrismaV3STTClientOffline:
    """Offline unit tests using mocks for WebSocket connection and message flow."""

    def test_missing_api_key_raises_auth_error(self):
        """Client must reject missing or placeholder API key before connecting."""
        client = GnaniPrismaSTTClient(api_key="")
        with pytest.raises(GnaniAuthenticationError, match="Missing or unconfigured GNANI_API_KEY"):
            client._build_headers()

        placeholder_client = GnaniPrismaSTTClient(api_key="your_gnani_api_key_here")
        with pytest.raises(GnaniAuthenticationError, match="Missing or unconfigured GNANI_API_KEY"):
            placeholder_client._build_headers()

    def test_headers_include_prisma_v3_parameters(self):
        """Handshake headers must include required Prisma v3.0 parameters."""
        config = PrismaV3STTConfig(
            model=PRISMA_V3_MODEL,
            language_code="indic-auto",
            language_candidates=["kn-IN", "hi-IN", "en-IN"],
            format="codemix",
        )
        client = GnaniPrismaSTTClient(api_key="test-api-key-12345", config=config)
        headers = client._build_headers()

        assert headers["x-api-key-id"] == "test-api-key-12345"
        assert headers["x-model"] == "prisma-v3.0"
        assert headers["x-language"] == "indic-auto"
        assert headers["x-language-candidates"] == "kn-IN,hi-IN,en-IN"
        assert headers["x-format"] == "codemix"
        assert headers["x-sample-rate"] == "16000"
        assert headers["x-enable-itn"] == "true"

    @pytest.mark.asyncio
    async def test_mocked_websocket_streaming_lifecycle(self):
        """Simulate complete WebSocket lifecycle: connect, send audio, receive transcripts."""
        mock_ws = AsyncMock()
        # Mock initial 'connected' message, an interim transcript, and a final transcript
        messages = [
            json.dumps({"type": "connected", "message": "Prisma v3.0 session established"}),
            json.dumps({
                "type": "transcript",
                "text": "ರಮೇಶ್ಗೆ ಮುನ್ನೂರು",
                "is_final": False,
                "detected_language_code": "kn-IN",
            }),
            json.dumps({
                "type": "transcript",
                "text": "ರಮೇಶ್ಗೆ ಮುನ್ನೂರು ನಲವತ್ತು ರೂಪಾಯಿ ಉಧಾರ್ ಬರೆಯಿರಿ.",
                "is_final": True,
                "detected_language_code": "kn-IN",
                "confidence": 0.94,
            }),
        ]

        async def mock_recv():
            if messages:
                return messages.pop(0)
            await asyncio.sleep(0.01)
            raise websockets.exceptions.ConnectionClosed(1000, "Normal closure")

        mock_ws.recv.side_effect = mock_recv
        mock_ws.__aiter__.return_value = [
            messages[1],  # interim
            messages[2],  # final
        ]

        with patch("websockets.connect", new=AsyncMock(return_value=mock_ws)):
            client = GnaniPrismaSTTClient(
                api_key="valid-test-key",
                config=PrismaV3STTConfig(language_code="kn-IN"),
            )
            await client.connect()
            assert client._connected is True

            # Send a synthetic audio chunk
            chunk = generate_synthetic_pcm_speech_simulation(duration_seconds=0.032)
            await client.send_audio_chunk(chunk[:STREAM_CHUNK_BYTES])
            mock_ws.send.assert_awaited_once_with(chunk[:STREAM_CHUNK_BYTES])

            # Receive transcript events
            events = []
            async for event in client.receive_events():
                events.append(event)

            assert len(events) == 2
            assert events[0].is_final is False
            assert events[0].text == "ರಮೇಶ್ಗೆ ಮುನ್ನೂರು"
            assert events[1].is_final is True
            assert events[1].text == "ರಮೇಶ್ಗೆ ಮುನ್ನೂರು ನಲವತ್ತು ರೂಪಾಯಿ ಉಧಾರ್ ಬರೆಯಿರಿ."
            assert events[1].detected_language_code == "kn-IN"

            await client.close()
            assert client._connected is False

    @pytest.mark.asyncio
    async def test_error_event_handling(self):
        """Server-side error message should raise GnaniConnectionError."""
        mock_ws = AsyncMock()
        mock_ws.recv.return_value = json.dumps({"type": "connected"})
        mock_ws.__aiter__.return_value = [
            json.dumps({"type": "error", "message": "Audio stream buffer overflow"}),
        ]

        with patch("websockets.connect", new=AsyncMock(return_value=mock_ws)):
            client = GnaniPrismaSTTClient(api_key="valid-test-key")
            await client.connect()
            with pytest.raises(GnaniConnectionError, match="Prisma v3.0 error: Audio stream buffer overflow"):
                async for _ in client.receive_events():
                    pass


class TestPrismaV3STTIntegration:
    """Live API integration tests against Gnani Prisma v3.0 WebSocket.
    
    Skipped unless a valid GNANI_API_KEY is present in the environment.
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_live_stt_connection(self):
        """Tests live WebSocket handshake with Prisma v3.0."""
        api_key = os.getenv("GNANI_API_KEY", "")
        if not api_key or api_key.startswith("your_"):
            pytest.skip("Skipping live STT integration test: valid GNANI_API_KEY not set")

        client = GnaniPrismaSTTClient(
            api_key=api_key,
            config=PrismaV3STTConfig(language_code="kn-IN"),
        )
        try:
            await client.connect()
            assert client._connected is True
            # Stream 0.5s of synthetic test audio
            pcm = generate_synthetic_pcm_speech_simulation(duration_seconds=0.5)
            for chunk in pcm_chunker(pcm):
                await client.send_audio_chunk(chunk)
                await asyncio.sleep(0.032)
        finally:
            await client.close()
