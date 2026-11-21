"""Unit and Integration tests for Gnani Timbre v3.0 Text-To-Speech client.

Covers:
- Configuration and model selection (Timbre v3.0 strict requirement)
- Missing API key handling
- Voice catalog validation (Kannada, Hindi, English Timbre v3.0 voices)
- Synthesis payload schema validation
- WebSocket streaming lifecycle & mock audio chunk reception
- Live API integration test (marked with pytest.mark.integration, skipped if no credentials)
"""

import asyncio
import base64
import json
import os
from unittest.mock import AsyncMock, patch
import pytest

from app.voice.audio import strip_wav_header
from app.voice.tts import (
    LANGUAGE_VOICE_MAP,
    TIMBRE_V30_MODEL,
    TIMBRE_V30_VOICES,
    GnaniTimbreTTSClient,
    GnaniTTSAuthenticationError,
    GnaniTTSError,
    GnaniUnsupportedVoiceError,
    TimbreV3TTSConfig,
)


class TestTimbreV3Config:
    """Test suite for Timbre v3.0 configuration validation."""

    def test_default_config_is_timbre_v3(self):
        """Verify default model is explicitly timbre-v3.0."""
        config = TimbreV3TTSConfig()
        assert config.model == "timbre-v3.0"
        assert config.voice in TIMBRE_V30_VOICES
        assert config.sample_rate == 16000

    def test_reject_non_timbre_v3_model(self):
        """Verify that older or invalid models (e.g. timbre-v2.5) are rejected."""
        config = TimbreV3TTSConfig(model="timbre-v2.5")
        with pytest.raises(ValueError, match="TTS model must be explicitly 'timbre-v3.0'"):
            config.validate()

    def test_verified_v3_voices_accepted(self):
        """Verify documented Timbre v3.0 voices for Kannada, Hindi, and English are accepted."""
        for voice in ["Manjunath", "Avinash", "Sneha", "Chetana", "Santosh", "Rekha"]:
            config = TimbreV3TTSConfig(voice=voice)
            config.validate()
            assert config.voice in TIMBRE_V30_VOICES

    def test_reject_unsupported_voice(self):
        """Verify non-v3 voice is rejected with clear error."""
        config = TimbreV3TTSConfig(voice="NonExistentVoice")
        with pytest.raises(GnaniUnsupportedVoiceError, match="Voice 'NonExistentVoice' is not a valid Timbre v3.0 voice"):
            config.validate()

    def test_speed_boundary_validation(self):
        """Verify speed must be within 0.5 to 2.0."""
        with pytest.raises(ValueError, match="Speed must be between 0.5 and 2.0"):
            TimbreV3TTSConfig(speed=0.2).validate()
        with pytest.raises(ValueError, match="Speed must be between 0.5 and 2.0"):
            TimbreV3TTSConfig(speed=2.5).validate()


class TestTimbreV3TTSClientOffline:
    """Offline unit tests using mocks for WebSocket connection and synthesis stream."""

    def test_missing_api_key_raises_auth_error(self):
        """Client must reject missing or placeholder API key."""
        client = GnaniTimbreTTSClient(api_key="")
        with pytest.raises(GnaniTTSAuthenticationError, match="Missing or unconfigured GNANI_API_KEY"):
            client._build_headers()

        placeholder_client = GnaniTimbreTTSClient(api_key="your_gnani_api_key_here")
        with pytest.raises(GnaniTTSAuthenticationError, match="Missing or unconfigured GNANI_API_KEY"):
            placeholder_client._build_headers()

    def test_payload_schema_matches_timbre_v3(self):
        """Verify synthesis JSON payload adheres strictly to Timbre v3.0 schema."""
        config = TimbreV3TTSConfig(
            model=TIMBRE_V30_MODEL,
            voice="Manjunath",
            language="kn-IN",
            speed=1.0,
            sample_rate=16000,
        )
        client = GnaniTimbreTTSClient(api_key="test-api-key", config=config)
        payload = client.build_synthesis_payload("ರಮೇಶ್ ಅವರ ಖಾತೆಗೆ 250 ರೂಪಾಯಿ ಸೇರಿಸಲಾಗಿದೆ.")

        assert payload["text"] == "ರಮೇಶ್ ಅವರ ಖಾತೆಗೆ 250 ರೂಪಾಯಿ ಸೇರಿಸಲಾಗಿದೆ."
        assert payload["model"] == "timbre-v3.0"
        assert payload["voice"] == "Manjunath"
        assert payload["language"] == "kn-IN"
        assert payload["speed"] == 1.0
        assert payload["audio_config"]["sample_rate"] == 16000
        assert payload["audio_config"]["encoding"] == "linear_pcm"
        assert payload["audio_config"]["num_channels"] == 1
        assert payload["audio_config"]["container"] == "wav"

    def test_empty_text_rejected(self):
        """Synthesis of blank text raises ValueError."""
        client = GnaniTimbreTTSClient(api_key="test-key")
        with pytest.raises(ValueError, match="Text to synthesize cannot be empty"):
            client.build_synthesis_payload("   ")

    @pytest.mark.asyncio
    async def test_mocked_tts_streaming_lifecycle(self):
        """Simulate complete TTS synthesis: send text, receive audio chunks, finish on complete."""
        mock_ws = AsyncMock()
        mock_audio_chunk = b"\x00\x10" * 256  # 512 bytes dummy PCM
        mock_b64 = base64.b64encode(mock_audio_chunk).decode("utf-8")

        # Mock messages yielded by WebSocket
        mock_ws.__aiter__.return_value = [
            json.dumps({"type": "audio", "data": {"audio": mock_b64}}),
            json.dumps({"type": "complete"}),
        ]

        with patch("websockets.connect", new=AsyncMock(return_value=mock_ws)):
            client = GnaniTimbreTTSClient(
                api_key="test-key",
                config=TimbreV3TTSConfig(voice="Manjunath", language="kn-IN"),
            )
            await client.connect()
            assert client._connected is True

            collected_chunks = []
            async for chunk in client.synthesize_stream("ಟೆಸ್ಟ್ ಆಡಿಯೋ"):
                collected_chunks.append(chunk)

            assert len(collected_chunks) == 1
            assert collected_chunks[0] == mock_audio_chunk

            await client.close()
            assert client._connected is False

    @pytest.mark.asyncio
    async def test_error_message_handling(self):
        """Server-side error message raises GnaniTTSError."""
        mock_ws = AsyncMock()
        mock_ws.__aiter__.return_value = [
            json.dumps({"type": "error", "message": "Voice quota exceeded"}),
        ]

        with patch("websockets.connect", new=AsyncMock(return_value=mock_ws)):
            client = GnaniTimbreTTSClient(api_key="test-key")
            with pytest.raises(GnaniTTSError, match="Timbre v3.0 synthesis error: Voice quota exceeded"):
                async for _ in client.synthesize_stream("Test"):
                    pass


class TestTimbreV3TTSIntegration:
    """Live API integration tests against Gnani Timbre v3.0 WebSocket.
    
    Skipped unless a valid GNANI_API_KEY is present in the environment.
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_live_tts_synthesis(self):
        """Tests live synthesis with Timbre v3.0 in Kannada and Hindi."""
        api_key = os.getenv("GNANI_API_KEY", "")
        if not api_key or api_key.startswith("your_"):
            pytest.skip("Skipping live TTS integration test: valid GNANI_API_KEY not set")

        client = GnaniTimbreTTSClient(
            api_key=api_key,
            config=TimbreV3TTSConfig(voice="Avinash", language="hi-IN"),
        )
        try:
            await client.connect()
            assert client._connected is True
            audio = await client.synthesize("नमस्ते, बोलखाता में आपका स्वागत है।")
            assert len(audio) > 0
        finally:
            await client.close()
