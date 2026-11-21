"""Pydantic schemas for the deterministic ledger and proposal commit flow in BolKhata AI."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_serializer, field_validator
from app.schemas.intent import IntentType


class EntryType(str, Enum):
    """Immutable ledger entry types."""
    CREDIT = "CREDIT"
    PAYMENT = "PAYMENT"


class PendingProposalStatus(str, Enum):
    """Lifecycle statuses for server-side pending proposals."""
    PENDING = "PENDING"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class StageProposalRequest(BaseModel):
    """Request to register a validated TransactionProposal as a pending proposal awaiting HITL confirmation."""
    customer_name: str = Field(..., min_length=1, max_length=255, description="Target customer name")
    intent: IntentType = Field(..., description="Parsed intent (must be ADD_CREDIT or LOG_PAYMENT / RECORD_PAYMENT)")
    amount: Decimal = Field(..., gt=Decimal("0"), description="Positive transaction amount in INR")
    currency: str = Field("INR", description="Currency (must be INR)")
    customer_id: Optional[str] = Field(None, description="Optional customer UUID for explicit disambiguation")
    phone_number: Optional[str] = Field(None, description="Optional customer phone for disambiguation")
    summary: Optional[str] = Field(None, max_length=500, description="Human readable summary")
    raw_transcript: Optional[str] = Field(None, max_length=1000, description="Original voice utterance")
    proposal_id: Optional[str] = Field(None, description="Client or parser assigned proposal UUID")

    @field_validator("currency")
    @classmethod
    def validate_inr(cls, v: str) -> str:
        if v.upper() != "INR":
            raise ValueError("Only 'INR' currency is supported.")
        return "INR"

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("Amount must be strictly greater than zero.")
        return v.quantize(Decimal("0.01"))


class RejectProposalRequest(BaseModel):
    """Request to explicitly reject/cancel a pending proposal."""
    reason: Optional[str] = Field(None, max_length=500, description="Optional merchant rejection reason")



class PendingProposalResponse(BaseModel):
    """Server-side pending proposal response schema."""
    proposal_id: str
    store_id: str
    customer_name: str
    intent: str
    amount: Decimal
    currency: str = "INR"
    summary: str
    status: str
    requires_confirmation: bool = True
    created_at: datetime
    expires_at: datetime

    @field_serializer("amount")
    def serialize_amount(self, v: Decimal) -> str:
        return f"{v:.2f}"

    class Config:
        from_attributes = True


class CommitProposalRequest(BaseModel):
    """Request payload to commit a pending proposal to the immutable ledger.
    
    CRITICAL HITL SAFETY:
    The merchant explicitly sets confirmed=True. The server retrieves the authoritative
    proposal from the database by proposal_id and does NOT trust client-supplied amounts.
    """
    proposal_id: str = Field(..., description="UUID of the pending proposal to commit")
    confirmed: bool = Field(True, description="Explicit merchant confirmation flag (must be True)")
    idempotency_key: Optional[str] = Field(None, max_length=100, description="Optional client idempotency key")
    actor_type: str = Field("merchant", description="Actor performing the confirmation (merchant, api)")
    actor_id: Optional[str] = Field(None, description="Identifier of the confirming merchant or terminal")
    notes: Optional[str] = Field(None, max_length=500, description="Optional merchant notes")


class DirectTransactionRequest(BaseModel):
    """Direct programmatic credit or payment request for API/service usage."""
    customer_id: str = Field(..., description="Target customer UUID")
    entry_type: EntryType = Field(..., description="CREDIT or PAYMENT")
    amount: Decimal = Field(..., gt=Decimal("0"), description="Transaction amount in INR")
    currency: str = Field("INR", description="Must be INR")
    description: Optional[str] = Field(None, max_length=500)
    idempotency_key: str = Field(..., min_length=1, max_length=100, description="Unique idempotency key")
    created_by: str = Field("merchant", max_length=100)

    @field_validator("currency")
    @classmethod
    def validate_inr(cls, v: str) -> str:
        if v.upper() != "INR":
            raise ValueError("Only 'INR' currency is supported.")
        return "INR"

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("Amount must be strictly greater than zero.")
        return v.quantize(Decimal("0.01"))


class LedgerCommitResponse(BaseModel):
    """Authoritative response after a successful or deduplicated ledger commit."""
    transaction_id: str = Field(..., description="Committed KhataEntry UUID")
    store_id: str
    customer_id: str
    customer_name: str
    entry_type: str
    amount: Decimal
    currency: str = "INR"
    resulting_balance: Decimal
    total_credit: Decimal
    total_payment: Decimal
    created_at: datetime
    is_duplicate: bool = False
    proposal_id: Optional[str] = None
    idempotency_key: str

    @field_serializer("amount", "resulting_balance", "total_credit", "total_payment")
    def serialize_decimal(self, v: Decimal) -> str:
        return f"{v:.2f}"


class CustomerBalanceResponse(BaseModel):
    """Authoritative customer balance response."""
    customer_id: str
    customer_name: str
    currency: str = "INR"
    total_credit: Decimal
    total_payment: Decimal
    outstanding_balance: Decimal

    @field_serializer("total_credit", "total_payment", "outstanding_balance")
    def serialize_decimal(self, v: Decimal) -> str:
        return f"{v:.2f}"


class KhataEntryResponse(BaseModel):
    """Authoritative ledger entry response."""
    id: str
    store_id: str
    customer_id: str
    entry_type: str
    amount: Decimal
    currency: str = "INR"
    description: Optional[str] = None
    idempotency_key: str
    proposal_id: Optional[str] = None
    created_at: datetime
    created_by: str

    @field_serializer("amount")
    def serialize_decimal(self, v: Decimal) -> str:
        return f"{v:.2f}"

    class Config:
        from_attributes = True


class CustomerEntriesResponse(BaseModel):
    """Paginated ledger entries for a customer."""
    customer_id: str
    customer_name: str
    currency: str = "INR"
    entries: List[KhataEntryResponse]
    total: int
    limit: int
    offset: int


class StoreSummaryResponse(BaseModel):
    """Authoritative summary of store-level ledger metrics."""
    store_id: str
    store_name: str
    currency: str = "INR"
    total_credit: Decimal
    total_payment: Decimal
    total_outstanding_balance: Decimal
    active_customers_count: int
    total_transactions_count: int

    @field_serializer("total_credit", "total_payment", "total_outstanding_balance")
    def serialize_decimal(self, v: Decimal) -> str:
        return f"{v:.2f}"
