# BolKhata AI 🎙️📖

> **"Your Kirana Store. Your Voice. Your Digital Khata."**

BolKhata AI is a production-minded, multilingual voice-operated digital ledger designed specifically for Indian kirana storekeepers (retail merchants). It enables shopkeepers to record customer credit (*udhaar*), log customer repayments, and query outstanding balances using natural voice commands in **Kannada**, **Hindi**, **English**, and Indian code-mixed speech.

---

## 🌟 Key Capabilities & Architectural Principles

- **Push-To-Talk Voice Interaction**: Designed for noisy retail store environments.
- **Multilingual & Code-Mixing**: First-class support for native Kannada (`kn`), Hindi (`hi`), Indian English (`en-IN`), and regional code-mixing.
- **Strict Human-In-The-Loop (HITL) Safety**:
  - LLMs **only** generate structured `TransactionProposal` schemas.
  - The LLM is **strictly forbidden** from writing SQL or modifying balances directly.
  - Every financial transaction requires merchant confirmation before committing.
  - The deterministic ledger engine guarantees balance mathematical integrity, idempotency, and audit trails.
- **Enterprise-Grade Voice Streaming**: Gnani Prisma v3.0 (STT) and Gnani Timbre v3.0 (TTS) via WebSocket streaming.

---

## 🏗️ Monorepo Structure

```
BolKhata-AI/
├── backend/
│   ├── app/
│   │   ├── api/            # API endpoints & health router
│   │   ├── config/         # Pydantic BaseSettings & env parsing
│   │   ├── database/       # SQLAlchemy engine & session factory
│   │   ├── models/         # Database models (KiranaStore, Customer, KhataEntry, Audit)
│   │   ├── schemas/        # Pydantic schemas (Proposals, Confirmations, Balances)
│   │   ├── ledger/         # Deterministic ledger transaction engine
│   │   ├── voice/          # Gnani Prisma v3.0 STT & Timbre v3.0 TTS WebSocket connectors
│   │   ├── agent/          # Groq LLM multilingual intent parser
│   │   ├── services/       # Domain business logic & customer management
│   │   ├── utils/          # Structured logging & secret sanitization
│   │   └── main.py         # FastAPI application entrypoint
│   ├── tests/              # Backend test suite (Pytest, HTTPX)
│   ├── requirements.txt    # Python 3.11+ dependencies
│   └── .env.example        # Backend environment variables template
├── frontend/               # React 18/19 + Vite + TypeScript + Tailwind CSS
├── docs/
│   └── architecture.md     # System architecture & safety guarantees specification
├── tests/                  # Monorepo level structure and security tests
├── .env.example            # Root environment template
├── .gitignore              # Comprehensive git ignore policy (secrets, db, node_modules)
├── pytest.ini              # Pytest configuration
└── README.md               # Project documentation & setup instructions
```

---

## 🛠️ Technology Stack

| Component | Technology | Version | Purpose |
|---|---|---|---|
| **Frontend** | React, TypeScript, Vite, Tailwind CSS | React 18+, Vite 5+ | Fast, touch-friendly merchant UI |
| **Backend** | Python, FastAPI, Uvicorn | Python 3.11+, FastAPI 0.115+ | Asynchronous REST & WebSocket server |
| **Database** | SQLite + SQLAlchemy ORM | SQLAlchemy 2.0+ | Lightweight transactional digital ledger |
| **Speech STT** | Gnani Prisma v3.0 | WebSocket Streaming | Real-time multilingual voice transcription |
| **Speech TTS** | Gnani Timbre v3.0 | WebSocket Streaming | Real-time Indian language audio feedback |
| **Intent LLM** | Groq (Qwen 27B / Llama 3.3 70B) | Groq SDK | Structured transaction proposal generation |
| **Testing** | Pytest, Vitest, HTTPX | Pytest 9+, Vitest 4+ | 136 backend tests & 33 frontend tests |

---

## 🎬 Live Demonstration & Judge Presentation Guide

For a 2–3 minute video demonstration script, judge Q&A defense cheat sheet, and exact spoken Kannada/Hindi/English phrases, refer to:
👉 **[Phase 5.2 Demo Readiness & Judge Presentation Guide](docs/PHASE_5_2_DEMO_READINESS_GUIDE.md)**

---

## 🚀 Quickstart & Setup Instructions

### 1. Prerequisites
- **Python 3.11+** (tested with Python 3.12)
- **Node.js v20+** and **npm**
- **Git**

### 2. Environment Configuration
Copy `.env.example` to `.env` in the root or `backend/` directory:

```bash
cp .env.example .env
```

> **Security Note:** Never commit `.env` to version control. The repository `.gitignore` automatically blocks `.env*` and `*.db` files.

### 3. Backend Setup

```bash
# Navigate to repository root
# Create a Python virtual environment
python -m venv backend/.venv

# Activate the virtual environment
# Windows (PowerShell):
backend\.venv\Scripts\Activate.ps1
# Linux / macOS:
source backend/.venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run backend test suite
python -m pytest

# Start the FastAPI backend server
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

The backend will start at `http://127.0.0.1:8000`.
- Health Check: `http://127.0.0.1:8000/health`
- Interactive API Docs: `http://127.0.0.1:8000/docs`

### 4. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install npm dependencies
npm install

# Start Vite development server
npm run dev
```

The frontend will run at `http://localhost:5173`.

---

## 🧪 Running Tests

Run the complete test suite across backend and monorepo structure:

```bash
backend\.venv\Scripts\python -m pytest -v
```

Expected output:
```
backend/tests/test_health.py::test_root_endpoint PASSED
backend/tests/test_health.py::test_health_endpoint PASSED
backend/tests/test_health.py::test_api_health_endpoint PASSED
tests/test_monorepo.py::test_no_env_committed PASSED
tests/test_monorepo.py::test_monorepo_structure PASSED
5 passed
```

---

## 🔒 Transaction Safety Specification

1. **Deterministic Ledger Engine**:
   - Financial balances are updated **exclusively** by the ledger service within database transactions.
   - LLMs never execute SQL statements or modify balances directly.
2. **Idempotency & Deduplication**:
   - Every transaction proposal is assigned a unique UUID.
   - Repeated voice inputs or double-tap confirmations are deduplicated.
3. **Auditable History**:
   - Full history of original voice transcript, proposed values, merchant confirmation timestamp, and balance delta is maintained.

---

## 📋 Project Implementation Phases

### Phase 0: Monorepo Foundation & Setup (Completed)
- [x] Monorepo directory structure established (`backend/`, `frontend/`, `docs/`, `tests/`).
- [x] Python dependencies configured and verified in virtual environment.
- [x] React + Vite + TypeScript + Tailwind CSS configured and built.
- [x] Pydantic `BaseSettings` environment configuration with secret safety.
- [x] `.env.example` created with all required configuration variables.
- [x] Comprehensive `.gitignore` protecting secrets, virtualenvs, databases, and logs.
- [x] FastAPI `/health` endpoint implemented and verified.
- [x] Monorepo structural and health check tests passing.

### Phase 1: Real-Time Multilingual Voice Engine (Completed)
- [x] Gnani Prisma v3.0 WebSocket streaming STT integration (`app/voice/stt.py`).
- [x] Gnani Timbre v3.0 WebSocket streaming TTS integration (`app/voice/tts.py`).
- [x] Audio streaming and linear PCM processing utilities (`app/voice/audio.py`).
- [x] Unit test suite covering STT and TTS streaming protocols (23 tests passing).

### Phase 2: Multilingual Intent Understanding & HITL Proposals (Completed)
- [x] Groq LLM (`llama-3.3-70b-versatile`) intent parser with JSON schema enforcement (`app/agent/intent_parser.py`).
- [x] Multilingual prompt engineering for Kannada, Hindi, English, and code-mixed speech (`app/agent/prompts.py`).
- [x] Strict HITL TransactionProposal schemas with UUIDs and confirmation requirements (`app/schemas/intent.py`).
- [x] REST API `/api/v1/intent/parse` with zero direct database mutation access.
- [x] Comprehensive intent parser test suite (25 tests passing).

### Phase 3: Deterministic Ledger Engine & Database Models (Completed)
- [x] SQLAlchemy 2.0 database models: `KiranaStore`, `Customer`, `KhataEntry`, `AuditLog`, `PendingProposal` (`app/models/`).
- [x] Strict append-only financial ledger design with ORM and SQLite immutability protections.
- [x] Deterministic Decimal balance calculator: $\text{Outstanding Balance} = \sum \text{CREDIT} - \sum \text{PAYMENT}$.
- [x] Idempotency & deduplication engine with store-scoped replay detection (`app/ledger/idempotency.py`).
- [x] Human-In-The-Loop proposal staging & verified commit workflow (`app/ledger/service.py`).
- [x] REST API endpoints for customer management (`/api/v1/customers`) and ledger operations (`/api/v1/ledger`).
- [x] Critical safety test proving zero database mutations from intent parsing alone.
- [x] 97 unit, model, ledger, idempotency, HITL, audit, API, and safety tests passing.

### Phase 3.1: Financial Integrity, Security & Concurrency Verification (Completed)
- [x] Database-level immutability triggers on `khata_entries` and `audit_logs` preventing raw SQL UPDATE/DELETE.
- [x] Real multi-threaded concurrency verification with thread-safe idempotent replay handling.
- [x] Server-side authoritative HITL proposal tamper-proofing and explicit proposal rejection endpoint (`/proposals/{id}/reject`).
- [x] Anti-merging customer identity disambiguation with `CustomerAmbiguityError` (HTTP 409).
- [x] 112 unit, model, ledger, idempotency, HITL, audit, API, and concurrency tests passing.

### Phase 4: Push-To-Talk Merchant Frontend & HITL Confirmation UI (Completed)
- [x] Mobile-first merchant UI in warm ivory/cream palette with accessible 48px+ tap targets.
- [x] Push-To-Talk browser microphone interface using MediaRecorder API with audio preview playback.
- [x] Authoritative HITL proposal confirmation card with stable idempotency keys and double-click prevention.
- [x] Trilingual localization for Kannada (ಕನ್ನಡ), Hindi (हिन्दी), and Indian English.
- [x] Customer management, disambiguation selector, and chronological immutable ledger history.
- [x] 20 frontend Vitest/Testing Library unit tests passing (100% pass rate).
- [x] Clean frontend production build (`tsc -b && vite build`).

### Phase 5: Full End-to-End Voice-to-Voice Integration & Production Hardening (Completed)
- [x] Bidirectional WebSocket streaming proxy at `/api/v1/voice/stream` between browser microphone, Gnani Prisma v3.0 STT, Groq IntentParser, Ledger Staging Engine, and Gnani Timbre v3.0 TTS.
- [x] Client WebAudio resampler converting 44.1k/48k Float32 audio to 16,000 Hz Mono Signed 16-bit Linear PCM (`frontend/src/utils/audioResampler.ts`).
- [x] Live partial transcript streaming as words are spoken, displaying instant visual feedback.
- [x] Read-only voice query handling (`QUERY_BALANCE`, `LIST_DUES`) executing with 0 ledger mutations.
- [x] Clarification dialogue prompt generation for ambiguous or unknown intents (`UNKNOWN`).
- [x] Localized voice confirmations in Kannada (`Manjunath`), Hindi (`Avinash`), and Indian English (`Avinash`) with HTML5 Audio playback and interruption support.
- [x] 124 backend unit and integration tests passing (12 voice WebSocket tests).
- [x] 33 frontend Vitest unit tests passing across 6 test suites.
- [x] Verified zero voice auto-commits: all financial entries require explicit merchant confirmation.




