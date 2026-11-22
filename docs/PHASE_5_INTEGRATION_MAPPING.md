# BolKhata AI — Phase 5 Integration Mapping Specification

**Document Version:** 1.0.0  
**Date:** November 22, 2026  
**Status:** Canonical Architectural Integration Map  

---

## 1. System Integration Overview

Phase 5 unifies the BolKhata AI monorepo into a real-time voice-to-voice streaming system. The architecture connects the frontend browser microphone to the backend voice proxy, passes raw audio frames to Gnani Prisma v3.0, orchestrates Groq LLM intent parsing, stages proposals in the deterministic ledger, enforces Human-In-The-Loop (HITL) merchant confirmation, and plays synthesized speech audio via Gnani Timbre v3.0.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               MERCHANT BROWSER                                  │
│                                                                                 │
│  [Microphone] ──(Float32 @ 44.1/48kHz)──> [Resampler & S16LE PCM Converter]     │
│                                                         │                       │
│                                            (Binary PCM @ 16kHz)                 │
│                                                         ▼                       │
│  [Audio Player] <──(Base64 WAV)── [WebSocket Client] <══════> (WS Control JSON) │
│                                         │                                       │
└─────────────────────────────────────────┼───────────────────────────────────────┘
                                          │ ws://127.0.0.1:8000/api/v1/voice/stream
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            FASTAPI BACKEND PROXY                                │
│                                                                                 │
│  [WebSocket Handler: /api/v1/voice/stream]                                      │
│    ├── Store Context Resolution (X-Store-Id or dev query param)                │
│    ├── Binary PCM Validation (validate_pcm_chunk)                               │
│    ├── Max Frame (64KB) & Max Session (60s) Buffer Checks                       │
│    └── Ephemeral In-Memory Pipeline (Zero raw audio disk persistence)          │
│                                         │                                       │
│          ┌──────────────────────────────┴──────────────────────────────┐        │
│          ▼                                                             ▼        │
│  [GnaniPrismaSTTClient]                                    [GnaniTimbreTTSClient]│
│  - wss://api.vachana.ai/stt/v3/stream                      - Linear PCM / WAV   │
│  - Prisma v3.0 Strict Model                                - Timbre v3.0 Voices │
│  - Streaming VAD & ITN                                     - kn-IN, hi-IN, en-IN│
│          │                                                             ▲        │
│    (Final Transcript)                                                  │        │
│          ▼                                                             │        │
│  [Voice Orchestrator]                                                  │        │
│    │                                                                   │        │
│    ├── 1. Determine Utterance Language                                 │        │
│    ├── 2. Invoke GroqIntentParser.parse() ─────────────────────────────┘        │
│    │       └── Returns: TransactionProposal (Zero DB Mutation)         (TTS)    │
│    │                                                                            │
│    ├── 3. If Financial (ADD_CREDIT / LOG_PAYMENT):                              │
│    │       └── Stage via LedgerService.stage_proposal()                         │
│    │       └── Emit PROPOSAL_READY & Audio confirmation prompt                  │
│    │                                                                            │
│    ├── 4. If Read-Only (QUERY_BALANCE / LIST_DUES):                             │
│    │       └── Query LedgerService.get_customer_balance()                       │
│    │       └── Emit READ_ONLY_RESPONSE & Spoken balance response                │
│    │                                                                            │
│    └── 5. If UNKNOWN / Clarification:                                           │
│            └── Emit CLARIFICATION_REQUIRED & Spoken clarification prompt        │
└─────────────────────────────────────────────────────────────────────────────────┘
                                          │
                         Merchant Confirms via UI (HITL)
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        DETERMINISTIC LEDGER ENGINE                              │
│                                                                                 │
│  [POST /api/v1/ledger/commit]                                                   │
│    ├── Requires confirmed=True                                                  │
│    ├── Enforces IdempotencyEngine replay cache (uq_khata_entries_store_idempotency)│
│    ├── Authoritative DB proposal lookup (Ignores client-supplied amount/intent) │
│    ├── Atomic Commit (KhataEntry + PendingProposal.COMMITTED + AuditLog)       │
│    └── Engine-Level Triggers prevent direct SQL UPDATE/DELETE                   │
│                                         │                                       │
│    (Successful Commit Receipt)          ▼                                       │
│  [Synthesize Spoken Receipt] ──> "₹340 credit recorded for Ramesh."             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Integration Matrix

| Component | Existing Module | Target Consumer in Phase 5 | Integration Mechanism | Public Interface / Contract |
|---|---|---|---|---|
| **Gnani STT Client** | `app.voice.stt.GnaniPrismaSTTClient` | Voice WebSocket Proxy (`app.api.voice`) | Async WebSocket Streaming | `connect()`, `send_audio_chunk(bytes)`, `receive_events() -> AsyncGenerator[PrismaTranscriptEvent]`, `close()` |
| **Gnani TTS Client** | `app.voice.tts.GnaniTimbreTTSClient` | Voice Orchestrator (`app.services.voice_orchestrator`) | Async WebSocket / Single Utterance | `synthesize(text: str) -> bytes`, `synthesize_stream(text) -> AsyncGenerator[bytes]` |
| **Audio Validator** | `app.voice.audio` | Voice WebSocket Proxy | Direct Import | `validate_pcm_chunk(chunk, allow_partial)`, `pcm_to_wav(pcm, 16000)` |
| **Groq Intent Parser** | `app.agent.intent_parser.GroqIntentParser` | Voice Orchestrator | Async Method Invocation | `parse(transcript: str, language: str) -> TransactionProposal` |
| **Ledger Service** | `app.ledger.service.LedgerService` | Voice Orchestrator & REST API | Database Session Scope | `stage_proposal(store_id, req, db)`, `commit_proposal(store_id, req, db)`, `get_customer_balance(store_id, cust_id, db)` |
| **Customer Service** | `app.services.customer_service.CustomerService` | Voice Orchestrator | Database Session Scope | `find_customer_by_name(store_id, name, db)`, `list_customers(store_id, db, query)` |
| **Voice Proxy Router** | `app.api.voice` (New) | Browser React Frontend | WebSocket: `/api/v1/voice/stream` | Binary PCM Frames + JSON Control Protocol |
| **Audio Resampler** | `frontend/src/utils/audioResampler.ts` (New) | Voice Assistant Hook | AudioContext ScriptProcessor / WebAudio | Resamples 44.1/48kHz Float32 to 16kHz Int16 S16LE PCM chunks |
| **Voice Streaming Hook**| `frontend/src/hooks/useVoiceWebSocket.ts` (New) | `frontend/src/components/VoiceAssistant.tsx` | WebSocket React Hook | Manages WebSocket connection, real-time partial/final transcripts, and TTS playback |

---

## 3. Strict Safety & Financial Invariants

1. **Zero Financial Commits from Voice Stream Alone:**
   - Receiving audio or final transcripts **never** executes a financial transaction.
   - The stream only produces a staged `PendingProposal` with status `PENDING`.
   - The merchant must explicitly click the physical **Confirm Transaction** button in the React UI.
2. **Intent Parsing Isolation:**
   - Intent parsing is strictly read-only and stateless.
   - Non-executable intents (`QUERY_BALANCE`, `LIST_DUES`, `UNKNOWN`) are permanently blocked from staging financial debit/credit proposals.
3. **Double-Click & Concurrent Replay Safeguards:**
   - Every confirmed transaction carries a stable idempotency key (`idempotency_key`).
   - Any replayed submission safely returns `is_duplicate=True` without mutating balances twice.
4. **Credential Isolation:**
   - No Groq or Gnani API keys are exposed to the browser.
   - All external provider communication occurs strictly within backend services.
5. **Privacy & Ephemeral Audio:**
   - Audio chunks are processed in-memory and discarded upon session completion.
   - Zero raw audio is written to disk or recorded in application logs.
