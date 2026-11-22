# BolKhata AI — Phase 5.1 Security & Privacy Findings

**Audit Date:** November 22, 2026  
**Auditor:** Independent Backend Security Engineer & Financial Systems Auditor  
**Scope:** Security posture, credential isolation, tenant boundaries, and DoS resilience across BolKhata AI (Phase 5)  

---

## 1. Executive Summary & Threat Model

BolKhata AI is designed as a financial ledger for Indian kirana merchants, relying on voice-first interactions. Because voice and LLM interpretations can be inherently non-deterministic, the primary security threat model requires that:
1. **Financial Mutation Decoupling:** Voice streams and LLM outputs must never directly execute financial transactions.
2. **Multi-Store Isolation:** Merchants must never be able to view, query, stage, or commit transactions belonging to other stores.
3. **Database Immutability:** Financial ledger entries (`khata_entries`) and audit logs (`audit_logs`) must be append-only and mathematically protected against modification or deletion.
4. **Credential Containment:** Upstream API keys (`GNANI_TOKEN`, `GNANI_API_KEY`, `GROQ_API_KEY`) must never leak to browsers or clients.

### Threat Model Evaluation Summary
| Area | Risk Level | Current State | Auditor Finding |
| :--- | :--- | :--- | :--- |
| **Speech-to-Ledger Boundary** | Critical | Enforced via HITL | **SECURE:** Zero direct mutations from speech or LLM |
| **Database Immutability** | Critical | Enforced via SQLite Triggers | **SECURE:** UPDATE and DELETE aborted at DB engine level |
| **Credential Containment** | High | Enforced via Server Architecture | **SECURE:** Zero client exposure of Gnani/Groq keys |
| **Store Tenant Isolation** | High | Enforced via Query Scoping | **ACCEPTABLE (DEV):** Needs JWT/Auth token in production |
| **WebSocket Audio Buffers** | Medium | 16-bit PCM alignment enforced | **FINDING:** Upper chunk size bound recommended |
| **Error Traceback Sanitization** | Low | Custom exception handlers | **SECURE:** No raw stack traces exposed to clients |

---

## 2. Detailed Security Findings

### Finding 1: Credential Isolation & Upstream API Key Protection
- **Status:** **PASS / VERIFIED**
- **Analysis:**
  - Upstream credentials for Gnani Prisma STT, Gnani Timbre TTS, and Groq Cloud are loaded exclusively from `backend/.env` using Pydantic Settings (`app.config.settings.Settings`).
  - No credentials appear in frontend source code, bundled JavaScript (`dist/assets/index-*.js`), or Vite environment files.
  - The WebSocket server communicates with `api.vachana.ai` as a secure backend proxy. The browser only sends raw microphone audio frames to the backend and receives transcripts or synthesized audio.
  - Automated tests verified that intentional errors (such as non-existent store IDs) return sanitized JSON error codes (`STORE_NOT_FOUND`) without leaking upstream API keys or internal endpoints.

---

### Finding 2: Store Authentication & Tenant Boundary Hardening
- **Status:** **HARDENING RECOMMENDATION (HIGH)**
- **Analysis:**
  - In the current implementation, tenant isolation is achieved by filtering all database queries on `store_id`. The store identity is passed by the client via query parameter on WebSocket (`/api/v1/voice/stream?store_id=<UUID>`) and via the `X-Store-Id` header on REST endpoints.
  - While cross-store attempts are strictly blocked when Store B attempts to query Store A's customer (`StoreMismatchError` / `CustomerNotFoundError`), there is currently **no cryptographic signature or bearer token** proving that the client actually owns or is authenticated as `store_id`.
- **Attack Scenario:**
  - If an attacker obtains another merchant's `store_id` (UUID), they could theoretically initiate a voice stream or submit transactions under that store ID.
- **Recommended Remediation:**
  - Implement JWT authentication for store owners.
  - Authenticate merchants via `/api/v1/auth/login` and require `Authorization: Bearer <JWT>` containing verified claims: `sub: user_id`, `store_id: store_id`, `exp: <timestamp>`.
  - Validate the JWT on WebSocket handshake and extract `store_id` from the verified token rather than from untrusted query parameters.

---

### Finding 3: WebSocket Audio Frame Validation & DoS Resilience
- **Status:** **HARDENING RECOMMENDATION (MEDIUM)**
- **Analysis:**
  - `validate_pcm_chunk(chunk: bytes)` in `backend/app/voice/audio.py` validates that incoming chunks are non-empty bytes and adhere to 16-bit alignment (`len(chunk) % 2 == 0`).
  - However, `validate_pcm_chunk` currently does not enforce an upper bound on buffer size (e.g. `MAX_CHUNK_BYTES = 65536`).
- **Attack Scenario:**
  - A malicious actor could open a WebSocket connection and stream arbitrary multi-megabyte binary payloads in a single frame, leading to excessive memory consumption on the backend event loop.
- **Recommended Remediation:**
  - Enforce a maximum frame size in `validate_pcm_chunk`:
    ```python
    MAX_PCM_CHUNK_BYTES = 65536  # 64 KB (~2 seconds of 16kHz mono audio)

    def validate_pcm_chunk(chunk: bytes, allow_partial: bool = False) -> bool:
        if not isinstance(chunk, (bytes, bytearray)):
            return False
        if len(chunk) == 0 and not allow_partial:
            return False
        if len(chunk) > MAX_PCM_CHUNK_BYTES:
            return False
        return len(chunk) % SAMPLE_WIDTH_16BIT == 0
    ```

---

### Finding 4: Database Immutability & Engine-Level Triggers
- **Status:** **PASS / VERIFIED**
- **Analysis:**
  - SQLite database triggers implemented in Phase 3.1:
    - `trg_prevent_khata_entry_update` (aborts UPDATE on `khata_entries`)
    - `trg_prevent_khata_entry_delete` (aborts DELETE on `khata_entries`)
    - `trg_prevent_audit_log_update` (aborts UPDATE on `audit_logs`)
    - `trg_prevent_audit_log_delete` (aborts DELETE on `audit_logs`)
  - Both ORM-level event listeners and direct SQL execution abort with `sqlite3.IntegrityError` / `DatabaseMutationError` when any modification or deletion is attempted.
  - Audit logs and khata entries are strictly append-only, satisfying core financial integrity requirements.

---

### Finding 5: Privacy & Audio Data Retention
- **Status:** **PASS / VERIFIED**
- **Analysis:**
  - Audio frames received from the browser are processed transiently in memory and forwarded to Gnani Prisma STT over WebSocket.
  - Audio files are **not** persisted to the local filesystem or database.
  - Only text transcripts (`raw_transcript`) and extracted proposal parameters are persisted in `pending_proposals` and `audit_logs` for merchant reconciliation and audit compliance.
  - Customer phone numbers and balances are isolated per store and protected against cross-store enumeration.

---

## 3. Prioritized Security Hardening Roadmap

| Priority | Component | Action Item | Target Phase |
| :--- | :--- | :--- | :--- |
| **P1** | Authentication | Replace `X-Store-Id` / query param with cryptographically signed Bearer JWTs | Production Deployment |
| **P2** | WebSocket API | Enforce `MAX_PCM_CHUNK_BYTES = 65536` on incoming binary frames | Minor Hardening |
| **P3** | Groq Cloud | Switch `GROQ_MODEL` to an accessible model or verify account quota | Cloud Config |
| **P4** | Rate Limiting | Add per-IP / per-store connection rate limiting on WebSocket endpoints | Production Deployment |
