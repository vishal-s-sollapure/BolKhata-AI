"""Ledger engine package for BolKhata AI.

Design Requirements:
- Deterministic credit (udhaar) and payment (jama) calculation engine using Decimal arithmetic.
- Only this service may update financial balances in the database.
- Every transaction has a unique ID, idempotency protection, and auditable history.
- Never directly modified by LLM output.
"""

from app.ledger.balance import BalanceCalculator
from app.ledger.idempotency import IdempotencyEngine
from app.ledger.service import LedgerService
from app.ledger.exceptions import (
    CustomerAmbiguityError,
    CustomerNotFoundError,
    DuplicateTransactionError,
    IdempotencyConflictError,
    ImmutabilityViolationError,
    InactiveCustomerError,
    InvalidAmountError,
    InvalidCurrencyError,
    LedgerError,
    ProposalAlreadyCommittedError,
    ProposalExpiredError,
    ProposalNotExecutableError,
    ProposalNotFoundError,
    StoreMismatchError,
    StoreNotFoundError,
)

__all__ = [
    "BalanceCalculator",
    "IdempotencyEngine",
    "LedgerService",
    "LedgerError",
    "StoreNotFoundError",
    "CustomerNotFoundError",
    "InactiveCustomerError",
    "InvalidAmountError",
    "InvalidCurrencyError",
    "IdempotencyConflictError",
    "DuplicateTransactionError",
    "ProposalNotFoundError",
    "ProposalAlreadyCommittedError",
    "ProposalExpiredError",
    "ProposalNotExecutableError",
    "StoreMismatchError",
    "CustomerAmbiguityError",
    "ImmutabilityViolationError",
]

