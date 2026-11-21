"""Audio processing and framing utilities for Gnani Prisma STT and Timbre TTS.

Gnani Prisma v3.0 Realtime STT Requirements:
- Format: Signed 16-bit Little-Endian Linear PCM (audio/x-raw, format=S16LE)
- Channels: Mono (1 channel)
- Sample Rate: 16000 Hz (also supports 8000, 44100, 48000 Hz; 16kHz recommended for Indian speech)
- Chunk Size: 512 samples = 1024 bytes per frame (standard STREAM_CHUNK_BYTES)
- Cadence: ~32ms per 1024-byte chunk for real-time 16kHz streaming
"""

import io
import math
import struct
import wave
from typing import Generator, Tuple

# Audio constants strictly matching Gnani speech specification
SAMPLE_RATE_16K = 16000
SAMPLE_RATE_8K = 8000
SAMPLE_RATE_48K = 48000
SAMPLE_WIDTH_16BIT = 2  # 16-bit = 2 bytes per sample
CHANNELS_MONO = 1

# Standard streaming frame spec (512 samples * 2 bytes = 1024 bytes)
STREAM_CHUNK_SAMPLES = 512
STREAM_CHUNK_BYTES = STREAM_CHUNK_SAMPLES * SAMPLE_WIDTH_16BIT  # 1024 bytes
FRAME_DURATION_MS = (STREAM_CHUNK_SAMPLES / SAMPLE_RATE_16K) * 1000  # 32.0 ms


def validate_pcm_chunk(chunk: bytes, allow_partial: bool = False) -> bool:
    """Validates that a PCM chunk contains an integer number of 16-bit mono samples.
    
    Args:
        chunk: Raw bytes of PCM audio.
        allow_partial: If True, permits any even byte length. If False, checks chunk is > 0 and aligned.
    """
    if not isinstance(chunk, (bytes, bytearray)):
        return False
    if len(chunk) == 0 and not allow_partial:
        return False
    # Each sample is 2 bytes (16-bit), so length must be an even integer
    return len(chunk) % SAMPLE_WIDTH_16BIT == 0


def pcm_chunker(
    audio_bytes: bytes,
    chunk_size: int = STREAM_CHUNK_BYTES,
) -> Generator[bytes, None, None]:
    """Slices a raw PCM audio stream into fixed-size chunks for streaming.
    
    Args:
        audio_bytes: Raw 16-bit PCM bytes.
        chunk_size: Target bytes per chunk (defaults to 1024 bytes = 512 samples at 16kHz).
    """
    total_len = len(audio_bytes)
    for i in range(0, total_len, chunk_size):
        chunk = audio_bytes[i : i + chunk_size]
        # Pad final chunk with silence if unaligned to 16-bit sample boundary
        if len(chunk) % SAMPLE_WIDTH_16BIT != 0:
            chunk = chunk + b"\x00"
        yield chunk


def generate_synthetic_pcm_speech_simulation(
    duration_seconds: float = 1.0,
    frequency_hz: float = 440.0,
    sample_rate: int = SAMPLE_RATE_16K,
    amplitude: float = 0.5,
) -> bytes:
    """Generates synthetic 16-bit PCM tone for offline/synthetic testing without microphone.
    
    Args:
        duration_seconds: Duration of generated audio in seconds.
        frequency_hz: Tone frequency (e.g., 440Hz A4).
        sample_rate: Sample rate in Hz (defaults to 16000).
        amplitude: Peak amplitude between 0.0 and 1.0.
    
    Returns:
        Raw 16-bit signed little-endian PCM bytes.
    """
    total_samples = int(duration_seconds * sample_rate)
    pcm_buffer = bytearray(total_samples * SAMPLE_WIDTH_16BIT)
    max_amp = 32767.0 * min(max(amplitude, 0.0), 1.0)

    for i in range(total_samples):
        t = float(i) / float(sample_rate)
        # Apply smooth Hann envelope to avoid clicks at start/end
        envelope = 0.5 * (1.0 - math.cos(2.0 * math.pi * float(i) / float(total_samples)))
        val = int(max_amp * envelope * math.sin(2.0 * math.pi * frequency_hz * t))
        val = max(-32768, min(32767, val))
        struct.pack_into("<h", pcm_buffer, i * SAMPLE_WIDTH_16BIT, val)

    return bytes(pcm_buffer)


def pcm_to_wav(
    pcm_data: bytes,
    sample_rate: int = SAMPLE_RATE_16K,
    num_channels: int = CHANNELS_MONO,
    sample_width: int = SAMPLE_WIDTH_16BIT,
) -> bytes:
    """Wraps raw PCM audio bytes with a standard canonical WAV (RIFF) header.
    
    Args:
        pcm_data: Raw PCM audio bytes.
        sample_rate: Sampling frequency in Hz.
        num_channels: Number of audio channels (1 = mono).
        sample_width: Bytes per sample (2 = 16-bit).
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(num_channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return buffer.getvalue()


def wav_to_pcm(wav_bytes: bytes) -> Tuple[bytes, int, int, int]:
    """Extracts raw PCM audio samples from WAV file bytes.
    
    Args:
        wav_bytes: Complete WAV file bytes.
        
    Returns:
        Tuple of (pcm_bytes, sample_rate, num_channels, sample_width).
    """
    buffer = io.BytesIO(wav_bytes)
    with wave.open(buffer, "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        num_channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        pcm_data = wav_file.readframes(wav_file.getnframes())
    return pcm_data, sample_rate, num_channels, sample_width


def strip_wav_header(data: bytes) -> bytes:
    """Strips RIFF/WAV header if present, returning pure PCM samples.
    
    Handles Gnani streaming responses where the first chunk may contain a WAV header.
    """
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return data

    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
        if chunk_id == b"data":
            data_start = offset + 8
            return data[data_start : data_start + chunk_size]
        offset += 8 + chunk_size

    # Fallback standard 44-byte header stripping
    if len(data) > 44:
        return data[44:]
    return b""
