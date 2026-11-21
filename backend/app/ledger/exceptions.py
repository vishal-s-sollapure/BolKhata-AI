"""Domain exceptions for the deterministic ledger engine in BolKhata AI."""

from app.models.khata_entry import ImmutabilityViolationError


class LedgerError(Exception):
    """Base exception for all ledger operations."""
    pass


class StoreNotFoundError(LedgerError):
    """Raised when the specified KiranaStore does not exist."""
    pass


class CustomerNotFoundError(LedgerError):
    """Raised when the specified Customer does not exist in the store."""
    pass


class InactiveCustomerError(LedgerError):
    """Raised when a financial transaction is attempted for an inactive/deactivated customer."""
    pass


class InvalidAmountError(LedgerError):
    """Raised when an invalid, zero, or negative monetary amount is provided."""
    pass


class InvalidCurrencyError(LedgerError):
    """Raised when an unsupported currency is specified (must be INR)."""
    pass


class IdempotencyConflictError(LedgerError):
    """Raised when an idempotency key is reused with a different transaction payload."""
    pass


class DuplicateTransactionError(LedgerError):
    """Raised when a duplicate transaction is detected."""
    pass


class ProposalNotFoundError(LedgerError):
    """Raised when a pending proposal cannot be found for the given store and ID."""
    pass


class ProposalAlreadyCommittedError(LedgerError):
    """Raised when attempting to commit a proposal that has already been committed."""
    pass


class ProposalExpiredError(LedgerError):
    """Raised when attempting to commit a proposal that has expired."""
    pass


class ProposalNotExecutableError(LedgerError):
    """Raised when attempting to commit a non-executable proposal (e.g. UNKNOWN, QUERY_BALANCE)."""
    pass


class StoreMismatchError(LedgerError):
    """Raised when attempting an operation on an entity belonging to a different store."""
    pass


class CustomerAmbiguityError(LedgerError):
    """Raised when multiple customers match a search query and require explicit disambiguation."""
    pass


__all__ = [
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
