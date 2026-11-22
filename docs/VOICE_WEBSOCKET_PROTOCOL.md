# BolKhata AI — Voice WebSocket Streaming Protocol

**Protocol Version:** 1.0.0  
**Endpoint:** `ws://<host>:<port>/api/v1/voice/stream` (also available as `/api/voice/stream`)  
**Transport:** Full-Duplex WebSocket (Binary Audio Frames + UTF-8 JSON Control Events)  

---

## 1. Handshake & Store Context

### Connection URL
```
ws://127.0.0.1:8000/api/v1/voice/stream?store_id=<STORE_UUID>&lang=<LANGUAGE_CODE>
```

### Parameters
- `store_id` *(optional in development)*: Kirana store tenant UUID. If omitted in dev mode, defaults to `00000000-0000-0000-0000-000000000001`.
- `lang` *(optional, default `indic-auto`)*: Initial STT language hint (`kn-IN`, `hi-IN`, `en-IN`, or `indic-auto`).

> [!IMPORTANT]
> Query parameter store identification is strictly a development-mode mechanism. In production deployment, the initial HTTP upgrade handshake will derive store identity from verified merchant session/JWT cookies, keeping credentials completely out of URLs.

---

## 2. Client-to-Server Messages

The client sends two types of WebSocket messages:
1. **Binary Frames:** Raw signed 16-bit linear PCM audio chunks (Little-Endian, Mono, 16000 Hz).
2. **Text Frames (JSON):** Client control events.

### Control Events

#### A. `START_SESSION`
Initiates or reconfigures a streaming session.
```json
{
  "action": "START_SESSION",
  "language": "indic-auto",
  "audio_config": {
    "sample_rate": 16000,
    "encoding": "pcm_s16le",
    "channels": 1
  }
}
```

#### B. `END_AUDIO`
Notifies the backend that the merchant has released the microphone button and no more audio chunks will follow for this utterance.
```json
{
  "action": "END_AUDIO"
}
```

#### C. `CANCEL_SESSION`
Immediately cancels the active session, interrupts pending provider requests, and resets the server state without committing any proposal.
```json
{
  "action": "CANCEL_SESSION"
}
```

#### D. `PING`
Client heartbeat frame to keep the connection alive.
```json
{
  "action": "PING"
}
```

---

## 3. Server-to-Client Messages

All server-to-client messages are JSON text frames with an `event` discriminator and an ISO-8601 timestamp.

### 1. `SESSION_STARTED`
Emitted immediately after the WebSocket handshake and Gnani STT initialization succeed.
```json
{
  "event": "SESSION_STARTED",
  "session_id": "c1f7a4e2-...",
  "store_id": "00000000-0000-0000-0000-000000000001",
  "language": "indic-auto",
  "timestamp": "2026-11-22T12:00:00.000Z"
}
```

### 2. `PARTIAL_TRANSCRIPT`
Emitted in real time as speech is recognized by Gnani Prisma v3.0 before utterance completion.
```json
{
  "event": "PARTIAL_TRANSCRIPT",
  "session_id": "c1f7a4e2-...",
  "text": "ರಮೇಶ್ ಗೆ 340",
  "is_final": false,
  "timestamp": "2026-11-22T12:00:01.200Z"
}
```

### 3. `FINAL_TRANSCRIPT`
Emitted when Gnani Prisma v3.0 detects utterance completion via Voice Activity Detection (VAD) or when `END_AUDIO` is received.
```json
{
  "event": "FINAL_TRANSCRIPT",
  "session_id": "c1f7a4e2-...",
  "text": "ರಮೇಶ್ ಗೆ 340 ರೂಪಾಯಿ ಉದಾರ್ ಬರೆಯಿರಿ.",
  "is_final": true,
  "detected_language_code": "kn-IN",
  "confidence": 0.98,
  "timestamp": "2026-11-22T12:00:02.500Z"
}
```

### 4. `PROCESSING`
Emitted when the server is executing the Groq LLM intent parser or staging the financial proposal.
```json
{
  "event": "PROCESSING",
  "session_id": "c1f7a4e2-...",
  "stage": "intent_parsing",
  "timestamp": "2026-11-22T12:00:02.600Z"
}
```

### 5. `PROPOSAL_READY`
Emitted when an executable financial proposal (`ADD_CREDIT` or `LOG_PAYMENT`) has been staged on the server awaiting human confirmation.
```json
{
  "event": "PROPOSAL_READY",
  "session_id": "c1f7a4e2-...",
  "proposal": {
    "proposal_id": "prop_8832a...",
    "intent": "ADD_CREDIT",
    "customer_name": "Ramesh Kumar",
    "amount": "340.00",
    "currency": "INR",
    "summary": "Add ₹340.00 credit for Ramesh Kumar",
    "confidence": 0.98,
    "requires_confirmation": true
  },
  "staged_proposal": {
    "proposal_id": "prop_8832a...",
    "store_id": "00000000-0000-0000-0000-000000000001",
    "customer_name": "Ramesh Kumar",
    "intent": "ADD_CREDIT",
    "amount": "340.00",
    "status": "PENDING",
    "expires_at": "2026-11-22T12:15:00.000Z"
  },
  "spoken_prompt": "I understood: Add ₹340 credit for Ramesh Kumar. Please confirm on screen.",
  "tts_audio": "<BASE64_ENCODED_WAV_AUDIO>",
  "timestamp": "2026-11-22T12:00:03.200Z"
}
```

### 6. `READ_ONLY_RESPONSE`
Emitted when the voice command was an informational query (`QUERY_BALANCE` or `LIST_DUES`). **Zero database writes occur.**
```json
{
  "event": "READ_ONLY_RESPONSE",
  "session_id": "c1f7a4e2-...",
  "intent": "QUERY_BALANCE",
  "customer_name": "Ramesh Kumar",
  "data": {
    "customer_id": "cust_9921...",
    "customer_name": "Ramesh Kumar",
    "total_credit": "540.00",
    "total_payment": "600.00",
    "outstanding_balance": "-60.00"
  },
  "spoken_response": "Ramesh Kumar has an advance balance of ₹60.",
  "tts_audio": "<BASE64_ENCODED_WAV_AUDIO>",
  "timestamp": "2026-11-22T12:00:03.100Z"
}
```

### 7. `CLARIFICATION_REQUIRED`
Emitted when the voice command is `UNKNOWN`, low confidence, missing an amount, or ambiguous.
```json
{
  "event": "CLARIFICATION_REQUIRED",
  "session_id": "c1f7a4e2-...",
  "question": "Which customer should this credit be recorded for?",
  "reasoning_code": "MISSING_CUSTOMER_NAME",
  "spoken_prompt": "Which customer should this credit be recorded for?",
  "tts_audio": "<BASE64_ENCODED_WAV_AUDIO>",
  "timestamp": "2026-11-22T12:00:03.000Z"
}
```

### 8. `TTS_AUDIO`
Emitted to deliver spoken audio feedback (e.g. after a successful UI commit or on assistant disclosure).
```json
{
  "event": "TTS_AUDIO",
  "session_id": "c1f7a4e2-...",
  "text": "₹340 credit has been recorded for Ramesh Kumar.",
  "mime_type": "audio/wav",
  "audio_base64": "<BASE64_ENCODED_WAV_AUDIO>",
  "timestamp": "2026-11-22T12:00:05.100Z"
}
```

### 9. `ERROR`
Emitted on validation failure, provider disconnect, or timeout.
```json
{
  "event": "ERROR",
  "session_id": "c1f7a4e2-...",
  "error_code": "STT_PROVIDER_ERROR",
  "message": "Gnani speech-to-text service disconnected unexpectedly.",
  "timestamp": "2026-11-22T12:00:04.000Z"
}
```

### 10. `SESSION_ENDED`
Emitted when a voice session closes cleanly.
```json
{
  "event": "SESSION_ENDED",
  "session_id": "c1f7a4e2-...",
  "reason": "completed",
  "timestamp": "2026-11-22T12:00:06.000Z"
}
```

---

## 4. Rate Limiting & Resource Constraints

1. **Max Session Duration:** 60 seconds (WebSocket automatically terminates if open longer).
2. **Idle Timeout:** 15 seconds of silence without audio or control messages.
3. **Max Frame Size:** 64 KB per binary audio frame (1024-byte chunks recommended).
4. **Max Total Audio Buffer:** 5 MB per session.
5. **Concurrency:** 1 active voice session per connection; previous tasks cleanly cancelled upon new `START_SESSION`.
