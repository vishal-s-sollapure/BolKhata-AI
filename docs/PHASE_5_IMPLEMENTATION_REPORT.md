# BolKhata AI — Phase 5: Implementation & Integration Report

> **Project:** BolKhata AI — Your Kirana Store. Your Voice. Your Digital Khata.  
> **Phase:** Phase 5 — Full End-to-End Voice-to-Voice Integration & Production Hardening  
> **Date:** November 2026  
> **Status:** Completed & Production Ready  

---

## 1. Executive Summary

Phase 5 completes the full end-to-end voice-to-voice streaming integration for **BolKhata AI**. It connects browser-native microphone streaming directly to **Gnani Prisma v3.0 Speech-To-Text (STT)**, passes transcripts to the **Groq Llama 3.3 70B Multilingual Intent Parser**, stages transactions in the **Deterministic Ledger Engine**, and generates spoken confirmation audio via **Gnani Timbre v3.0 Text-To-Speech (TTS)**.

### Core Guarantees & Safety Invariants:
1. **Zero Spoken Auto-Commits**: Spoken utterances or LLM proposals **NEVER** write to the financial ledger automatically. Every transaction is staged with `status = "PENDING"` and requires explicit merchant confirmation in the HITL UI.
2. **Read-Only Voice Queries**: Balance checks (`QUERY_BALANCE`) and dues listings (`LIST_DUES`) execute read operations that cause zero database mutations.
3. **No Credential Leaks**: Gnani and Groq API keys remain strictly server-side; the browser connects solely through the authenticated FastAPI WebSocket proxy at `/api/v1/voice/stream`.
4. **Append-Only Immutability**: All financial entries remain append-only, enforced by SQLite database triggers and SQLAlchemy ORM event listeners.
5. **Multi-tenant Store Isolation**: Every WebSocket session verifies active store tenant context via query parameter or dev store fallback.

---

## 2. Voice-to-Voice Streaming Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           MERCHANT BROWSER CLIENT                               │
│                                                                                 │
│  [Microphone] 44.1k/48kHz Float32                                               │
│       │                                                                         │
│       ▼                                                                         │
│  [WebAudio Resampler & PCM Converter]                                           │
│       │ Linear interpolation to 16,000 Hz Mono                                  │
│       │ Clamped to [-1.0, 1.0] -> 16-bit Signed Little-Endian PCM (Int16)       │
│       │ Sliced into 1024-byte (512 sample / 32ms) binary chunks                 │
│       ▼                                                                         │
│  [WebSocket Client] (wss://host/api/v1/voice/stream)                            │
└───────┬─────────────────────────────────────────────────────────────────▲───────┘
        │ Binary PCM Chunks + JSON Control Frames                         │ Server Events & Audio
        ▼                                                                 │
┌─────────────────────────────────────────────────────────────────────────┴───────┐
│                        FASTAPI WEBSOCKET PROXY                                  │
│                 (backend/app/api/voice.py @ /voice/stream)                      │
│                                                                                 │
│  - Handshake: Verifies store tenant context (StoreService / KiranaStore)        │
│  - Session Manager: Assigns UUIDv4 session_id; emits SESSION_STARTED            │
│  - Audio Stream Forwarder: Proxies raw PCM to Gnani Prisma STT WebSocket        │
│  - Event Pump: Streams PARTIAL_TRANSCRIPT and FINAL_TRANSCRIPT to client        │
└───────┬─────────────────────────────────────────────────────────────────▲───────┘
        │ Audio PCM                                 Final Transcript      │
        ▼                                                                 │
┌───────────────────────────────┐           ┌─────────────────────────────┴───────┐
│    GNANI PRISMA v3.0 STT      │           │         VOICE ORCHESTRATOR          │
│ (wss://api.vachana.ai/v3/stt) │           │ (app/services/voice_orchestrator.py)│
│                               │           │                                     │
│ - Model: prisma-v3.0          │           │ 1. Intent Parsing:                  │
│ - Rate: 16,000 Hz S16LE Mono  │           │    Groq Llama 3.3 70B               │
│ - Format: codemix             │           │ 2. Proposal Staging:                │
│ - Langs: kn-IN, hi-IN, en-IN  │──────────►│    LedgerService.stage_proposal()   │
│ - Yields: Partial / Final     │           │    (PendingProposal PENDING)        │
│   transcripts in real time    │           │ 3. Read-Only Branch:                │
└───────────────────────────────┘           │    LedgerService.get_balance()      │
                                            │ 4. Spoken Prompt Generation:        │
                                            │    Localized kn-IN / hi-IN / en-IN  │
                                            │ 5. Timbre v3.0 TTS Synthesis:       │
                                            │    Yields WAV audio container       │
                                            └─────────────────────────────────────┘
```

---

## 3. Implemented Components

### 3.1 Backend
- **`backend/app/services/voice_orchestrator.py`**:
  - `VoiceOrchestrator`: Dispatches parsed utterances to either financial proposal staging, read-only balance inquiry, or clarification prompts.
  - `generate_spoken_prompt()`: Generates natural merchant confirmations in Kannada, Hindi, and English.
  - `synthesize_speech()`: Connects to Gnani Timbre v3.0 TTS, selecting voices (`Manjunath` for Kannada, `Avinash` for Hindi/English) and returning complete WAV containers.
- **`backend/app/api/voice.py`**:
  - `@router.websocket("/stream")`: Bidirectional audio streaming WebSocket proxy supporting raw S16LE PCM chunks and client control frames (`START_SESSION`, `END_AUDIO`, `CANCEL_SESSION`, `PING`, `SIMULATE_TRANSCRIPT`).
  - `@router.post("/process-transcript")`: REST fallback endpoint for transcript processing and proposal staging.
  - `@router.post("/synthesize")`: REST fallback endpoint for on-demand speech synthesis.
- **`backend/app/main.py`**:
  - Registered `voice_router` under `/api` and `/api/v1`.

### 3.2 Frontend
- **`frontend/src/utils/audioResampler.ts`**:
  - `resampleTo16k()`: Linear interpolation resampler downsampling Float32 audio buffers from 44.1k/48k to 16,000 Hz.
  - `float32ToInt16PCM()`: Converts normalized float samples to signed 16-bit linear PCM little-endian ArrayBuffers with hard clipping.
  - `chunkPCMBuffer()`: Slices audio into 1024-byte uniform chunks aligned to 16-bit boundaries.
- **`frontend/src/hooks/useVoiceWebSocket.ts`**:
  - Manages WebSocket connection lifecycle, audio recording with WebAudio `ScriptProcessorNode`, binary transmission, and server event handling.
  - Controls HTML5 Audio playback for synthesized TTS audio with user interruption support (`stopAudioPlayback()`).
- **`frontend/src/components/VoiceAssistant.tsx`**:
  - Real-time Push-to-Talk button with animated pulsing radar rings during recording.
  - Live partial transcript streaming as words are spoken.
  - Read-Only Query card displaying customer balances with 0 database mutations.
  - Clarification prompt card when intent is ambiguous or unknown.
  - Integrated `IntentProposalCard` presenting staged proposals with Confirm/Reject actions.

---

## 4. Voice WebSocket Protocol Specification

| Client Frame | Payload / Format | Purpose |
|---|---|---|
| `Binary Chunk` | `ArrayBuffer` (1024 bytes, S16LE PCM 16kHz) | Streams live microphone speech |
| `START_SESSION` | `{"action": "START_SESSION", "language": "kn-IN"}` | Initializes or resets speech session |
| `END_AUDIO` | `{"action": "END_AUDIO"}` | Merchant released Push-to-Talk button |
| `CANCEL_SESSION` | `{"action": "CANCEL_SESSION"}` | Cancels utterance and discards audio |
| `SIMULATE_TRANSCRIPT` | `{"action": "SIMULATE_TRANSCRIPT", "transcript": "..."}` | Automated test & offline simulation |
| `PING` | `{"action": "PING", "timestamp": 123456}` | Keepalive ping |

| Server Event | Payload Fields | Purpose |
|---|---|---|
| `SESSION_STARTED` | `session_id`, `store_id`, `sample_rate`, `format`, `channels` | Handshake acknowledgment |
| `PARTIAL_TRANSCRIPT` | `transcript`, `is_final: false`, `language` | Real-time live feedback in UI |
| `FINAL_TRANSCRIPT` | `transcript`, `is_final: true`, `confidence` | Final speech recognition result |
| `PROCESSING` | `status: "PARSING_INTENT"` | Progress indicator |
| `PROPOSAL_READY` | `proposal`, `staged_proposal`, `spoken_response`, `audio_b64` | Financial proposal staged awaiting HITL |
| `READ_ONLY_RESPONSE` | `intent`, `data`, `spoken_response`, `audio_b64` | Read-only balance or summary |
| `CLARIFICATION_REQUIRED` | `transcript`, `spoken_response`, `audio_b64` | Clarification prompt for missing info |
| `TTS_AUDIO` | `audio_b64`, `audio_format`, `text` | Synthesized speech audio container |
| `ERROR` | `code`, `message` | Structured error event |
| `SESSION_ENDED` | `session_id`, `reason` | Session termination confirmation |

---

## 5. Security & Multi-Tenancy Invariants

1. **Authentication & Store Context**: In development mode, sessions without an explicit `store_id` bind to `DEFAULT_DEV_STORE_ID`. Non-existent or inactive stores are rejected with error code 4004.
2. **No LLM Financial Execution**: The LLM output is parsed into a Pydantic `TransactionProposal`. It is persisted only as a `PendingProposal` with status `PENDING`.
3. **Double Confirmation Protection**: The financial ledger commit endpoint requires an explicit POST request with `confirmed: true`. Replay requests return the existing transaction via the `IdempotencyEngine`.
4. **Append-Only Ledger**: Database triggers (`trg_prevent_khata_entry_update`, `trg_prevent_khata_entry_delete`, `trg_prevent_audit_log_update`, `trg_prevent_audit_log_delete`) block all UPDATE and DELETE operations at the database engine level.

---

## 6. Verification Summary

- **Backend Tests**: 124 passing unit and integration tests across 13 test suites (12 WebSocket tests).
- **Frontend Tests**: 33 passing tests across 6 test suites with happy-dom.
- **Production Build**: `dist/` compiled cleanly in 12.06s with Vite 5 and TypeScript strict checking.
