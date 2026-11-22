# BolKhata AI — System Architecture & Design Specification

> **Tagline:** "Your Kirana Store. Your Voice. Your Digital Khata."

---

## 1. Executive Summary

**BolKhata AI** is a production-minded digital ledger designed specifically for Indian kirana storekeepers (retail merchants). It enables shopkeepers to record credit sales (*udhaar*), customer payments (*jama*), and query outstanding balances using natural voice commands in **Kannada**, **Hindi**, **English**, and Indian code-mixed speech.

---

## 2. Monorepo Organization

```
BolKhata-AI/
├── backend/
│   ├── app/
│   │   ├── api/            # REST endpoints (health, intent, customers, ledger)
│   │   ├── config/         # Pydantic BaseSettings & env parsing
│   │   ├── database/       # SQLAlchemy engine, session maker, Base
│   │   ├── models/         # Database models (KiranaStore, Customer, KhataEntry, AuditLog, PendingProposal)
│   │   ├── schemas/        # Pydantic schemas (Proposals, Confirmations, Balances, Customers)
│   │   ├── ledger/         # Deterministic ledger computation engine & balance calculator
│   │   ├── voice/          # Gnani Prisma v3.0 STT & Timbre v3.0 TTS WebSocket clients
│   │   ├── agent/          # Groq LLM multilingual intent parser (proposal generator)
│   │   ├── services/       # Domain services (Customer, Store, Intent)
│   │   ├── utils/          # Structured logging & secret sanitization
│   │   └── main.py         # FastAPI application entry point
│   ├── tests/              # Pytest backend test suite (unit, model, ledger, api, safety)
│   ├── requirements.txt    # Python 3.12+ dependencies
│   └── .env.example        # Backend environment template
├── frontend/               # React + Vite + TypeScript + Tailwind CSS
├── docs/                   # System design, architecture, and API documentation
├── tests/                  # Monorepo level integration tests
├── .gitignore              # Comprehensive git ignore policy
└── README.md               # Quickstart and developer setup guide
```

---

## 3. End-to-End Pipeline & HITL Architecture

Financial integrity in a voice-operated ledger is non-negotiable. BolKhata AI implements a strict **Human-In-The-Loop (HITL) deterministic ledger pipeline**:

```
Gnani STT
   │  (Raw Audio Stream -> Text Transcript)
   ▼
Groq Intent Parser (Llama 3.3 70B)
   │  (Zero DB writes; produces structured schema only)
   ▼
Validated Transaction Proposal
   │  (UUIDv4, amount, intent, requires_confirmation=True)
   ▼
Pending Proposal (Persisted Server-Side)
   │  (status=PENDING, expires_at = now + 15m)
   ▼
Explicit Shopkeeper Confirmation
   │  (Merchant reviews proposal summary on screen / audio prompt)
   ▼
Proposal Verification & Idempotency Check
   │  (Verify store ownership, TTL, confirmed=True, deduplication)
   ▼
Deterministic Ledger Service
   │  (Exact Decimal arithmetic; credit increases balance, payment decreases)
   ▼
Atomic Database Commit
   │  (KhataEntry inserted, PendingProposal marked COMMITTED)
   ▼
Audit Log Record
   │  (Immutable event logged with actor, entity ID, metadata)
   ▼
Updated Balance Computed & Returned
   │  (Outstanding = Total CREDIT - Total PAYMENT)
   ▼
Gnani Timbre v3.0 TTS Voice Response
      "Ramesh avara khathege 340 rupaayi serisalaagide."
```

### Absolute Architectural Invariants:
1. **Zero LLM Database Writes**: The Groq LLM only produces `TransactionProposal` schemas. It has no database connection and executes no SQL.
2. **Deterministic Calculations**: Balance computations are executed solely by Python `Decimal` arithmetic.
3. **Append-Only Immutability**: Khata entries are immutable. No financial record can be updated or deleted.
4. **Idempotency Protection**: Every transaction has a unique store-scoped idempotency key. Network retries return original results without double-charging.
5. **Human-In-The-Loop**: A proposal requires explicit merchant confirmation (`confirmed=True`).

---

## 4. Database Models & Schema Relationships

### A. KiranaStore (`kirana_stores`)
- `id`: String(36) UUID primary key
- `store_name`: String(255) non-null business name
- `owner_name`: String(255) non-null merchant name
- `phone_number`: String(20) optional contact phone
- `preferred_language`: String(20) default `'kannada'`
- `is_active`: Boolean default `True`
- `created_at`, `updated_at`: DateTime(timezone=True)
- *Relationships*: `customers` (1:N), `khata_entries` (1:N), `audit_logs` (1:N), `pending_proposals` (1:N) with `cascade="none"`.

### B. Customer (`customers`)
- `id`: String(36) UUID primary key
- `store_id`: String(36) FK to `kirana_stores.id` (`ondelete="RESTRICT"`)
- `customer_name`: String(255) non-null
- `normalized_name`: String(255) non-null lowercase searchable name
- `phone_number`: String(20) optional customer mobile
- `is_active`: Boolean default `True` (soft-delete flag)
- `created_at`, `updated_at`: DateTime(timezone=True)
- *Indexes*: `(store_id, normalized_name)`, `(store_id, phone_number)`
- *Cascade Policy*: Customer records can be soft-deactivated; financial history is never deleted.

### C. KhataEntry (`khata_entries`)
- `id`: String(36) UUID primary key
- `store_id`: String(36) FK to `kirana_stores.id` (`ondelete="RESTRICT"`)
- `customer_id`: String(36) FK to `customers.id` (`ondelete="RESTRICT"`)
- `entry_type`: String(20) `'CREDIT'` or `'PAYMENT'`
- `amount`: Numeric(12, 2) positive monetary amount in INR
- `currency`: String(3) strictly `'INR'`
- `description`: String(500) optional merchant note
- `reference_id`: String(100) optional external invoice/bill
- `idempotency_key`: String(100) unique idempotency key
- `proposal_id`: String(100) optional associated proposal UUID
- `created_at`: DateTime(timezone=True) immutable creation timestamp
- `created_by`: String(100) actor identifier
- `metadata_json`: Text sanitized JSON
- *Constraints*:
  - `CheckConstraint("amount > 0", name="chk_khata_positive_amount")`
  - `CheckConstraint("currency = 'INR'", name="chk_khata_currency_inr")`
  - `CheckConstraint("entry_type IN ('CREDIT', 'PAYMENT')", name="chk_khata_entry_type")`
  - `UniqueConstraint("store_id", "idempotency_key", name="uq_khata_store_idempotency")`
- *Immutability*: Protected by SQLAlchemy `before_update` and `before_delete` ORM event listeners.

### D. AuditLog (`audit_logs`)
- `id`: String(36) UUID primary key
- `store_id`: String(36) FK to `kirana_stores.id` (`ondelete="RESTRICT"`)
- `actor_type`: String(50) `'merchant'`, `'system'`, `'api'`
- `actor_id`: String(100) optional terminal/user ID
- `action`: String(100) non-null audit event
- `entity_type`: String(50) affected model name
- `entity_id`: String(100) primary key of target entity
- `request_id`: String(100) optional correlation ID
- `timestamp`: DateTime(timezone=True) event timestamp
- `metadata_json`: Text sanitized metadata (no secrets/passwords)
- *Immutability*: Protected against updates and deletions.

### E. PendingProposal (`pending_proposals`)
- `id`: String(36) UUID primary key
- `store_id`: String(36) FK to `kirana_stores.id` (`ondelete="RESTRICT"`)
- `proposal_id`: String(100) non-null proposal UUID
- `customer_name`: String(255) non-null customer name
- `customer_id`: String(36) nullable FK to `customers.id`
- `intent`: String(50) non-null (`ADD_CREDIT` or `RECORD_PAYMENT` / `LOG_PAYMENT`)
- `amount`: Numeric(12, 2) non-null positive INR amount
- `currency`: String(3) strictly `'INR'`
- `summary`: String(500) human-readable summary
- `status`: String(20) `'PENDING'`, `'COMMITTED'`, `'REJECTED'`, `'EXPIRED'`
- `requires_confirmation`: Boolean default `True`
- `khata_entry_id`: String(36) FK to `khata_entries.id`
- `created_at`, `expires_at`, `committed_at`: DateTime(timezone=True)
- `raw_transcript`: String(1000) original transcription text
- *Constraints*: `UniqueConstraint("store_id", "proposal_id")`

---

## 5. Deterministic Balance Calculation Engine

All monetary calculations use Python `Decimal` with two decimal places (`quantize(Decimal("0.01"))`). Floating-point arithmetic is strictly prohibited.

### Balance Formula:
$$\text{Outstanding Balance} = \sum \text{CREDIT} - \sum \text{PAYMENT}$$

### Concrete Example:
1. **Opening Balance**: ₹0.00
2. **Credit (Udhaar)**: ₹340.00 $\rightarrow$ Balance = ₹340.00
3. **Payment (Jama)**: ₹100.00 $\rightarrow$ Balance = ₹240.00
4. **Credit (Udhaar)**: ₹200.00 $\rightarrow$ Balance = ₹440.00

### Overpayment Handling:
If $\sum \text{PAYMENT} > \sum \text{CREDIT}$, the resulting balance is negative (e.g. ₹-50.00), explicitly representing an advance customer deposit/credit held with the kirana store.

---

## 6. Idempotency & Deduplication Engine

To protect against network dropouts and repeated button presses in busy retail store environments:
1. Every commit request checks `IdempotencyEngine.check_idempotency(...)`.
2. If the same `(store_id, idempotency_key)` exists with matching payload (customer, type, amount, currency), the existing `KhataEntry` is returned with `is_duplicate=True` and the balance is **not** altered again.
3. If an idempotency key is reused with conflicting parameters, an `IdempotencyConflictError` (HTTP 409) is raised.

---

## 7. Store Isolation & Tenant Security

1. **Store Scoping**: Every customer, ledger entry, pending proposal, and audit log belongs to exactly one `KiranaStore`.
2. **Context Resolution**: The store context is resolved via the `X-Store-Id` HTTP header.
3. **Development Fallback**: In development mode, omitting `X-Store-Id` automatically falls back to a seeded default store (`DEFAULT_DEV_STORE_ID: 00000000-0000-0000-0000-000000000001`).
4. **Production Security Roadmap**: In future phases, store context will be populated exclusively from cryptographically signed JWT tokens issued upon merchant authentication.

---

## 8. API Endpoints Reference

### Customer Management (`/api/v1/customers`)
- `POST /api/v1/customers`: Register a new customer
- `GET /api/v1/customers`: List/search customers for current store
- `GET /api/v1/customers/{customer_id}`: Retrieve customer details

### Deterministic Ledger (`/api/v1/ledger`)
- `POST /api/v1/ledger/proposals`: Stage an AI proposal for merchant confirmation
- `POST /api/v1/ledger/commit`: Commit a confirmed proposal to the ledger
- `GET /api/v1/ledger/customers/{customer_id}/balance`: Get customer balance
- `GET /api/v1/ledger/customers/{customer_id}/entries`: Get chronological ledger entries
- `GET /api/v1/ledger/summary`: Get store financial totals

### Voice Intent Parsing (`/api/v1/intent`)
- `POST /api/v1/intent/parse`: Parse speech transcript into TransactionProposal (zero DB writes)

### Real-Time Voice Streaming (`/api/v1/voice`)
- `WS /api/v1/voice/stream`: Bidirectional audio streaming WebSocket proxy (Gnani Prisma v3.0 STT + Groq IntentParser + Proposal Staging + Gnani Timbre v3.0 TTS)
- `POST /api/v1/voice/process-transcript`: REST endpoint to process spoken transcript into staged proposal
- `POST /api/v1/voice/synthesize`: REST endpoint to synthesize text into localized Kirana speech audio

---

## 9. Migration & Schema Strategy

- In Phase 3 (MVP/Development), SQLAlchemy `Base.metadata.create_all(bind=engine)` creates tables idempotently without dropping existing data.
- For production multi-tenant deployments, Alembic migrations will be introduced to track incremental schema diffs and zero-downtime rollouts.
