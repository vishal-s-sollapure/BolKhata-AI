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
| **Intent LLM** | Groq (Llama 3.3 70B Versatile) | Groq SDK | Structured transaction proposal generation |
| **Testing** | Pytest, Pytest-asyncio, HTTPX | Pytest 9+ | Automated unit, API, and architectural tests |

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

## 📋 Phase 0 Completion Status

- [x] Monorepo directory structure established (`backend/`, `frontend/`, `docs/`, `tests/`).
- [x] Python dependencies configured and verified in virtual environment.
- [x] React + Vite + TypeScript + Tailwind CSS configured and built.
- [x] Pydantic `BaseSettings` environment configuration with secret safety.
- [x] `.env.example` created with all required configuration variables.
- [x] Comprehensive `.gitignore` protecting secrets, virtualenvs, databases, and logs.
- [x] FastAPI `/health` endpoint implemented and verified.
- [x] Health check and monorepo structural tests passing (5/5 tests passing).
- [x] Production build for frontend verified (`npm run build`).
- [x] Initial Git tracking and commits configured.

