# BolKhata AI (ಬೋಲ್‌ಖಾತಾ AI / बोलखाता AI)

> **"Your Kirana Store. Your Voice. Your Digital Khata."**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5+-3178C6.svg?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Vite](https://img.shields.io/badge/Vite-5+-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3+-38B2AC.svg?logo=tailwind-css&logoColor=white)](https://tailwindcss.com)

A production-minded, multilingual AI-powered digital ledger designed specifically for Indian kirana storekeepers (*vyaparigalu* / *vyapari*). BolKhata AI enables retail merchants to manage customer credit (*udhaar*), repayments, and outstanding balances using natural voice commands in **Kannada**, **Hindi**, **English**, and natural code-mixed speech.

---

## 1. Key Highlights & Safety Architecture

- **Multilingual Push-To-Talk Voice Interface**: Native support for Kannada (ಕನ್ನಡ), Hindi (हिन्दी), English, and Indian code-mixing (Kanglish / Hinglish).
- **Strict Non-Destructive Ledger Pipeline**:
  1. **Voice Input** $\to$ Audio streamed to **Gnani Prisma v3.0** via WebSocket.
  2. **Intent Parsing** $\to$ **Groq LLM** extracts structured `TransactionProposal` schemas. *The LLM has zero direct database permissions and never writes SQL.*
  3. **Merchant Confirmation (HITL)** $\to$ Shopkeeper confirms the parsed credit/payment proposal on screen or via voice.
  4. **Deterministic Ledger Engine** $\to$ Only the backend ledger service updates financial records in SQLite with idempotency UUIDs and a tamper-evident audit history.
  5. **Spoken Confirmation** $\to$ Spoken response synthesized via **Gnani Timbre v3.0** WebSocket interface.

---

## 2. Monorepo Organization

```
BolKhata-AI/
├── backend/
│   ├── app/
│   │   ├── api/            # Health, Transaction, and WebSocket endpoints
│   │   ├── config/         # Pydantic BaseSettings & environment validation
│   │   ├── database/       # SQLAlchemy engine & session factory (SQLite)
│   │   ├── models/         # Database models (KiranaStore, Customer, KhataEntry)
│   │   ├── schemas/        # Pydantic schemas (Proposals, Confirmations, Balances)
│   │   ├── ledger/         # Deterministic ledger calculation engine
│   │   ├── voice/          # Gnani Prisma v3.0 & Timbre v3.0 WebSocket streaming
│   │   ├── agent/          # Groq LLM multilingual intent parser
│   │   ├── services/       # Domain business services
│   │   ├── utils/          # Structured logging & security sanitizers
│   │   └── main.py         # FastAPI application entry point
│   ├── tests/              # Backend pytest test suite (health, api, contracts)
│   ├── requirements.txt    # Python dependencies
│   └── .env.example        # Backend environment template
├── frontend/
│   ├── src/
│   │   ├── App.tsx         # BolKhata UI dashboard & Push-To-Talk interface
│   │   ├── main.tsx        # React entry point
│   │   └── index.css       # Tailwind CSS styles
│   ├── index.html          # HTML entry point
│   ├── package.json        # Frontend scripts and dependencies
│   ├── tailwind.config.js  # Tailwind theme configuration
│   └── vite.config.ts      # Vite bundler & reverse proxy setup
├── docs/
│   └── architecture.md     # Architectural design & safety specifications
├── tests/
│   └── test_monorepo.py    # Monorepo safety & structure verification tests
├── .gitignore              # Comprehensive Git ignore rules
├── pytest.ini              # Pytest configuration
└── README.md               # Project documentation
```

---

## 3. Prerequisites

- **Python**: Version `3.11` or higher (tested on Python `3.12.10`)
- **Node.js**: Version `20.18.0` or higher
- **npm**: Version `10.0.0` or higher

---

## 4. Quickstart Guide

### Backend Setup

1. **Navigate to the backend directory and configure the environment**:
   ```bash
   cd backend
   cp .env.example .env
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run backend automated tests**:
   ```bash
   # From root directory
   pytest
   ```

5. **Start the FastAPI backend server**:
   ```bash
   # From backend directory
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

   # Or from root directory
   uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
   ```
   - API Root: [http://localhost:8000/](http://localhost:8000/)
   - Health Check: [http://localhost:8000/health](http://localhost:8000/health)
   - Interactive Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Frontend Setup

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Start the Vite development server**:
   ```bash
   npm run dev
   ```
   Open your browser at [http://localhost:5173/](http://localhost:5173/).

4. **Build for production and test preview**:
   ```bash
   npm run build
   npm run preview
   ```

---

## 5. Technology Stack

| Layer | Component | Specification |
|---|---|---|
| **Frontend** | React 18, TypeScript, Tailwind CSS, Vite | Fast, responsive merchant interface with push-to-talk |
| **Backend** | Python 3.12+, FastAPI, Uvicorn | Asynchronous high-performance REST and WebSocket server |
| **Streaming Pipeline** | Pipecat AI | Real-time audio streaming orchestration |
| **Speech-To-Text (STT)** | Gnani Prisma v3.0 | Low-latency Kannada, Hindi, and English WebSocket stream |
| **Speech-Synthesis (TTS)**| Gnani Timbre v3.0 | Natural-sounding regional speech WebSocket stream |
| **Language AI** | Groq (Llama 3.3 70B Versatile) | Structured transaction proposal generation (no DB writes) |
| **Ledger & DB** | SQLite + SQLAlchemy ORM | Deterministic balance calculations, unique IDs, audit log |
| **Testing** | Pytest, Pytest-Asyncio, HTTPX | Contract and API test automation |

---

## 6. Environment Configuration

Copy `.env.example` to `.env` (never commit real credentials). Key settings:

```ini
APP_ENV=development
DEBUG=True
APP_HOST=0.0.0.0
APP_PORT=8000
DATABASE_URL=sqlite:///./bolkhata.db

# Groq LLM Key (used for intent extraction only)
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Gnani Voice Streaming Credentials (WebSocket interfaces)
GNANI_PRISMA_WS_URL=wss://api.gnani.ai/v3/prisma/stream
GNANI_TIMBRE_WS_URL=wss://api.gnani.ai/v3/timbre/stream
GNANI_API_KEY=your_gnani_api_key_here
GNANI_TOKEN=your_gnani_token_here
GNANI_ACCESS_KEY=your_gnani_access_key_here

DEFAULT_LANGUAGE=kannada
LOG_LEVEL=INFO
```

---

## 7. Phase 0 Verification Status

- [x] Monorepo directory structure established (`backend/`, `frontend/`, `docs/`, `tests/`)
- [x] Backend Python 3.11+ dependencies configured & installed
- [x] React + Vite + TypeScript + Tailwind CSS configured & built
- [x] Environment configuration with Pydantic settings & `.env.example` templates
- [x] Comprehensive `.gitignore` protecting secrets, SQLite DBs, and virtual environments
- [x] FastAPI `/health` and root `/` endpoints verified live with HTTP 200
- [x] React UI verified live with Vite preview & health badge
- [x] Automated tests (Pytest) passing with 100% success rate
- [x] Git tracking initialized with clean commit
