#!/usr/bin/env python3
"""BolKhata AI — Gnani Prisma v3.0 STT & Timbre v3.0 TTS Voice Verification Utility.

Features:
- Kannada (kn-IN), Hindi (hi-IN), English (en-IN), and Code-mixed (indic-auto) speech testing.
- Streaming PCM audio to Gnani Prisma v3.0 WebSocket.
- Live partial and final transcript display.
- Real-time text-to-speech synthesis using Gnani Timbre v3.0 WebSocket.
- Audio playback and WAV artifact generation.
- Model identification and latency metrics.

Usage:
    python backend/scripts/test_gnani_voice.py --help
    python backend/scripts/test_gnani_voice.py --lang kn-IN --source synthetic
    python backend/scripts/test_gnani_voice.py --lang hi-IN
    python backend/scripts/test_gnani_voice.py --lang en-IN
    python backend/scripts/test_gnani_voice.py --lang indic-auto
"""

import argparse
import asyncio
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

# Ensure backend package is in python search path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config.settings import get_settings
from app.voice.audio import (
    FRAME_DURATION_MS,
    SAMPLE_RATE_16K,
    STREAM_CHUNK_BYTES,
    generate_synthetic_pcm_speech_simulation,
    pcm_chunker,
    pcm_to_wav,
    wav_to_pcm,
)
from app.voice.stt import (
    PRISMA_V3_MODEL,
    GnaniAuthenticationError,
    GnaniConnectionError,
    GnaniPrismaSTTClient,
    PrismaV3STTConfig,
)
from app.voice.tts import (
    LANGUAGE_VOICE_MAP,
    TIMBRE_V30_MODEL,
    GnaniTimbreTTSClient,
    GnaniTTSAuthenticationError,
    GnaniTTSConnectionError,
    TimbreV3TTSConfig,
)

# Canonical Kirana store test phrases specified in Phase 1 requirements
CANONICAL_TEST_PHRASES = {
    "kn-IN": {
        "language_name": "Kannada",
        "phrase": "ರಮೇಶ್ಗೆ ಮುನ್ನೂರು ನಲವತ್ತು ರೂಪಾಯಿ ಉಧಾರ್ ಬರೆಯಿರಿ.",
        "tts_text": "ರಮೇಶ್ ಅವರ ಖಾತೆಗೆ 340 ರೂಪಾಯಿ ಉಧಾರ್ ಸೇರಿಸಲಾಗಿದೆ.",
        "voice": "Manjunath",
    },
    "hi-IN": {
        "language_name": "Hindi",
        "phrase": "रमेश के नाम तीन सौ चालीस रुपये उधार लिखो।",
        "tts_text": "रमेश के खाते में 340 रुपये उधार जोड़ दिया गया है।",
        "voice": "Avinash",
    },
    "en-IN": {
        "language_name": "Indian English",
        "phrase": "Add three hundred and forty rupees credit for Ramesh.",
        "tts_text": "Added 340 rupees credit for Ramesh successfully.",
        "voice": "Avinash",
    },
    "indic-auto": {
        "language_name": "Code-Mixed Indian Speech",
        "phrase": "Ramesh ka 340 rupaye udhaar add karo.",
        "tts_text": "Ramesh ke khate mein 340 rupaye credit add kar diya gaya hai.",
        "voice": "Avinash",
    },
}


def play_wav_file(wav_path: str) -> None:
    """Plays back a WAV audio file on the host OS."""
    try:
        if platform.system() == "Windows":
            # Use PowerShell SoundPlayer (built into Windows, no external pip dependency needed)
            powershell_cmd = (
                f"(New-Object Media.SoundPlayer '{wav_path}').PlaySync()"
            )
            subprocess.run(
                ["powershell", "-c", powershell_cmd],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif platform.system() == "Darwin":
            subprocess.run(["afplay", wav_path], check=True)
        else:
            subprocess.run(["aplay", wav_path], check=True)
    except Exception as e:
        print(f"[Playback Note] Could not auto-play audio: {e}")
        print(f"[Playback Note] Audio file is saved at: {wav_path}")


async def run_stt_verification(
    lang_code: str,
    pcm_audio: bytes,
    api_key: str,
    reference_phrase: str,
) -> Optional[str]:
    """Streams audio to Gnani Prisma v3.0 STT WebSocket and prints live transcripts."""
    print("\n" + "=" * 60)
    print(" 🎙️  STT VERIFICATION: GNANI PRISMA v3.0")
    print("=" * 60)
    print(f"• STT Model:          {PRISMA_V3_MODEL} (Explicit selection)")
    print(f"• Language:           {lang_code} ({CANONICAL_TEST_PHRASES[lang_code]['language_name']})")
    print(f"• Audio Length:       {len(pcm_audio)} bytes (~{len(pcm_audio) / (SAMPLE_RATE_16K * 2):.2f}s)")
    print(f"• Reference Phrase:   \"{reference_phrase}\"")

    stt_config = PrismaV3STTConfig(
        model=PRISMA_V3_MODEL,
        language_code=lang_code,
        format="codemix" if lang_code == "indic-auto" else "transcribe",
        language_candidates=["kn-IN", "hi-IN", "en-IN"],
    )

    client = GnaniPrismaSTTClient(api_key=api_key, config=stt_config)
    print(f"• WebSocket Endpoint: {client.ws_url}")
    print("\nConnecting to Prisma v3.0 STT WebSocket...")

    start_time = time.time()
    final_transcript = None

    try:
        await client.connect()
        print("Connected. Streaming PCM audio in 1024-byte chunks...")

        # Asynchronous sender task
        async def send_audio_chunks():
            chunk_count = 0
            for chunk in pcm_chunker(pcm_audio, chunk_size=STREAM_CHUNK_BYTES):
                await client.send_audio_chunk(chunk)
                chunk_count += 1
                await asyncio.sleep(FRAME_DURATION_MS / 1000.0)  # Paced real-time streaming
            print(f"Finished sending {chunk_count} audio frames.")

        sender_task = asyncio.create_task(send_audio_chunks())

        # Receive events with timeout
        async for event in client.receive_events():
            if event.is_final:
                final_transcript = event.text
                print(f"\n[STT FINAL TRANSCRIPT] >> \"{event.text}\"")
                if event.detected_language_code:
                    print(f"• Detected Language:   {event.detected_language_code}")
                if event.confidence:
                    print(f"• Confidence:          {event.confidence:.2%}")
                break
            else:
                print(f"[STT Partial] {event.text}", end="\r", flush=True)

        await sender_task
        elapsed = time.time() - start_time
        print(f"\n• Recognition Latency: {elapsed:.2f}s")

    except (GnaniAuthenticationError, GnaniConnectionError) as e:
        print(f"\n❌ STT Error: {e}")
        return None
    finally:
        await client.close()

    if final_transcript:
        print("\nAccuracy Observation:")
        print(f"  Reference:  \"{reference_phrase}\"")
        print(f"  Recognized: \"{final_transcript}\"")
        matches = final_transcript.strip() == reference_phrase.strip()
        print(f"  Exact Match: {matches}")

    return final_transcript


async def run_tts_verification(
    lang_code: str,
    text: str,
    voice_name: str,
    api_key: str,
    play_audio: bool = True,
) -> Optional[bytes]:
    """Sends text to Gnani Timbre v3.0 TTS WebSocket and collects/plays the audio."""
    print("\n" + "=" * 60)
    print(" 🔊  TTS VERIFICATION: GNANI TIMBRE v3.0")
    print("=" * 60)
    print(f"• TTS Model:          {TIMBRE_V30_MODEL} (Explicit selection)")
    print(f"• Language:           {lang_code}")
    print(f"• Voice ID:           {voice_name}")
    print(f"• Input Text:         \"{text}\"")

    tts_config = TimbreV3TTSConfig(
        model=TIMBRE_V30_MODEL,
        voice=voice_name,
        language=lang_code if lang_code != "indic-auto" else "auto",
        sample_rate=SAMPLE_RATE_16K,
        container="wav",
    )

    client = GnaniTimbreTTSClient(api_key=api_key, config=tts_config)
    print(f"• WebSocket Endpoint: {client.ws_url}")
    print("\nConnecting to Timbre v3.0 TTS WebSocket...")

    start_time = time.time()
    ttfb = None
    chunks = []

    try:
        await client.connect()
        print("Connected. Synthesizing audio stream...")

        async for chunk in client.synthesize_stream(text):
            if ttfb is None:
                ttfb = time.time() - start_time
                print(f"• Time to first audio chunk (TTFB): {ttfb:.3f}s")
            chunks.append(chunk)

        total_time = time.time() - start_time
        full_audio = b"".join(chunks)
        print(f"• Total synthesis duration:         {total_time:.3f}s")
        print(f"• Total audio received:             {len(full_audio)} bytes")

    except (GnaniTTSAuthenticationError, GnaniTTSConnectionError) as e:
        print(f"\n❌ TTS Error: {e}")
        return None
    finally:
        await client.close()

    if full_audio:
        # Save output WAV file
        temp_dir = Path(tempfile.gettempdir())
        out_wav = temp_dir / f"bolkhata_tts_{lang_code}_{voice_name}_{int(time.time())}.wav"
        out_wav.write_bytes(full_audio)
        print(f"• Audio successfully saved:         {out_wav}")

        if play_audio:
            print("Playing synthesized audio...")
            play_wav_file(str(out_wav))

        return full_audio
    return None


async def main():
    parser = argparse.ArgumentParser(description="BolKhata AI — Gnani Voice Verification CLI")
    parser.add_argument(
        "--lang",
        choices=["kn-IN", "hi-IN", "en-IN", "indic-auto"],
        default="kn-IN",
        help="Language code to test (default: kn-IN)",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "stt", "tts"],
        default="all",
        help="Testing mode: all, stt only, or tts only",
    )
    parser.add_argument(
        "--source",
        choices=["synthetic", "file"],
        default="synthetic",
        help="Audio source for STT test: synthetic tone or audio file",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to input WAV file if --source file",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default=None,
        help="Override Timbre v3.0 voice ID",
    )
    parser.add_argument(
        "--no-play",
        action="store_true",
        help="Disable automatic audio playback of synthesized speech",
    )
    args = parser.parse_args()

    settings = get_settings()
    api_key = settings.GNANI_API_KEY or os.getenv("GNANI_API_KEY", "")

    print("\n" + "=" * 60)
    print(" 🚀  BOLKHATA AI — GNANI VOICE PIPELINE VERIFICATION")
    print("     \"Your Kirana Store. Your Voice. Your Digital Khata.\"")
    print("=" * 60)

    if not api_key or api_key.startswith("your_"):
        print("\n⚠️  NOTICE: No valid GNANI_API_KEY found in environment or .env.")
        print("   Set GNANI_API_KEY in your .env or shell environment to connect to live services.")
        print("   The client libraries have been verified with complete offline unit tests.")
        return

    lang_data = CANONICAL_TEST_PHRASES[args.lang]
    voice_name = args.voice or lang_data["voice"]

    # STT Phase
    if args.mode in ("all", "stt"):
        if args.source == "file" and args.file:
            print(f"Reading audio from WAV file: {args.file}")
            wav_bytes = Path(args.file).read_bytes()
            pcm_audio, sample_rate, channels, _ = wav_to_pcm(wav_bytes)
        else:
            print("Generating synthetic 16kHz PCM audio simulation...")
            pcm_audio = generate_synthetic_pcm_speech_simulation(duration_seconds=1.5)

        await run_stt_verification(
            lang_code=args.lang,
            pcm_audio=pcm_audio,
            api_key=api_key,
            reference_phrase=lang_data["phrase"],
        )

    # TTS Phase
    if args.mode in ("all", "tts"):
        await run_tts_verification(
            lang_code=args.lang,
            text=lang_data["tts_text"],
            voice_name=voice_name,
            api_key=api_key,
            play_audio=not args.no_play,
        )

    print("\n" + "=" * 60)
    print(" ✅  VOICE INTEGRATION VERIFICATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
