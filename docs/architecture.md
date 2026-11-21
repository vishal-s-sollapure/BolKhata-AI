# BolKhata AI — System Architecture & Design Specification

> **Tagline:** "Your Kirana Store. Your Voice. Your Digital Khata."

---

## 1. Executive Summary

**BolKhata AI** is a production-minded digital ledger designed specifically for Indian kirana storekeepers (retail merchants). It enables shopkeepers to record credit sales (*udhaar*), customer payments, and query outstanding balances using natural voice commands in **Kannada**, **Hindi**, **English**, and Indian code-mixed speech.

---

## 2. Monorepo Organization

```
BolKhata-AI/
├── backend/
│   ├── app/
│   │   ├── api/            # REST and WebSocket endpoints (health, transactions, voice)
│   │   ├── config/         # Pydantic BaseSettings & env parsing
│   │   ├── database/       # SQLAlchemy engine, session maker, Base
│   │   ├── models/         # Database models (KiranaStore, Customer, KhataEntry, AuditLog)
│   │   ├── schemas/        # Pydantic schemas (Proposals, Confirmations, Balances)
│   │   ├── ledger/         # Deterministic ledger computation engine
│   │   ├── voice/          # Gnani Prisma v3.0 STT & Timbre v3.0 TTS WebSocket clients
│   │   ├── agent/          # Groq LLM multilingual intent parser (proposal generator)
│   │   ├── services/       # Customer, Khata, and Notification domain logic
│   │   ├── utils/          # Logging, security, sanitizers
│   │   └── main.py         # FastAPI application entry point
│   ├── tests/              # Backend pytest test suite
│   ├── requirements.txt    # Python 3.11+ dependencies
│   └── .env.example        # Backend environment template
├── frontend/               # React + Vite + TypeScript + Tailwind CSS
├── docs/                   # System design, architecture, and API documentation
├── tests/                  # Monorepo level integration tests
├── .gitignore              # Comprehensive git ignore policy
└── README.md               # Quickstart and developer setup guide
```

---

## 3. Critical Transaction Safety Architecture

Financial integrity in a voice-operated ledger is non-negotiable. BolKhata AI implements a strict **Human-In-The-Loop (HITL) deterministic ledger pipeline**:

```
[Voice Input: Kannada/Hindi/English]
                   │
                   ▼ (WebSocket Stream)
       [Gnani Prisma v3.0 STT]
                   │
                   ▼ (Transcript)
     [Groq Multilingual Intent LLM]
                   │
                   ▼ (Structured JSON)
    ┌───────────────────────────────┐
    │     TransactionProposal       │
    │  - Customer: "Ramesh"         │
    │  - Type: CREDIT (Udhaar)      │
    │  - Amount: ₹250               │
    │  - Items: "Sugar 2kg, Rice"   │
    │  - Language: "kn"             │
    │  - Proposal ID: UUIDv4        │
    └───────────────────────────────┘
                   │
                   ▼ (HTTP / WebSocket Push)
      [Kirana Merchant UI (React)]
       "Ramesh: Udhaar ₹250. Confirm?"
                   │
         Merchant Presses Confirm
                   │
                   ▼ (POST /api/v1/ledger/commit)
     [Deterministic Ledger Engine]
  - Idempotency & Deduplication Check
  - Customer Balance Increment
  - Append-Only Khata Entry
  - Complete Audit Trail Recording
                   │
                   ▼
     [Gnani Timbre v3.0 TTS Voice Response]
     "Ramesh avara khathege 250 rupaayi serisalaagide."
```

### Absolute Rules:
1. **Zero LLM Database Writes**: The Groq LLM only produces `TransactionProposal` schemas. It has no database connection and executes no SQL.
2. **Deterministic Calculations**: Balance computations are executed solely by Python arithmetic inside database transactions.
3. **Idempotency**: Every proposal is tagged with a unique UUID. Duplicate requests are rejected.
4. **Audit Trail**: Every modification preserves the original voice transcript, proposal metadata, and operator confirmation timestamp.

---

## 4. Voice Engine Integration Standards

- **Speech-To-Text (STT)**: **Gnani Prisma v3.0** via WebSocket streaming.
- **Speech-Synthesis (TTS)**: **Gnani Timbre v3.0** via WebSocket streaming.
- **Integrity**: Standardized streaming protocol without mock substitutions or fallback to legacy REST endpoints.
- **Languages**: Native Kannada, Hindi, and Indian English with code-mixing handling.

---

## 5. Technology Stack Summary

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS | High-performance merchant UI with Push-To-Talk |
| Backend | Python 3.12+, FastAPI, Uvicorn | Asynchronous API & WebSocket server |
| Audio Pipeline | Pipecat AI | Real-time audio stream pipeline orchestration |
| Speech Engine | Gnani Prisma v3.0 (STT) & Timbre v3.0 (TTS) | Low-latency Indian language voice streaming |
| Language AI | Groq Cloud (Llama 3.3 70B Versatile) | Low-latency voice transcript intent extraction |
| Database | SQLite (MVP) + SQLAlchemy ORM | Local-first, lightweight transactional ledger |
| Testing | Pytest, Pytest-asyncio, HTTPX | Comprehensive API and unit testing |
