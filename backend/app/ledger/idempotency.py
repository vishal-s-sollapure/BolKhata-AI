"""Idempotency and duplicate detection engine for BolKhata AI."""

from decimal import Decimal
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models.khata_entry import KhataEntry
from app.ledger.exceptions import IdempotencyConflictError


class IdempotencyEngine:
    """Manages transactional idempotency and duplicate replay detection.
    
    GUARANTEES:
    1. Every transaction has an idempotency key scoped to the kirana store.
    2. Identical requests re-submitted with the same idempotency key return the original
       transaction without creating duplicate ledger records or altering balances.
    3. Reusing an idempotency key with conflicting parameters (e.g. different amount or
       different customer) is strictly rejected with IdempotencyConflictError.
    """

    @staticmethod
    def check_idempotency(
        store_id: str,
        idempotency_key: str,
        expected_customer_id: str,
        expected_entry_type: str,
        expected_amount: Decimal,
        expected_currency: str,
        db: Session,
    ) -> Tuple[Optional[KhataEntry], bool]:
        """Checks if a ledger entry already exists for the given idempotency key.
        
        Args:
            store_id: Tenant KiranaStore UUID.
            idempotency_key: Client or server assigned idempotency key.
            expected_customer_id: Target customer UUID.
            expected_entry_type: 'CREDIT' or 'PAYMENT'.
            expected_amount: Expected monetary Decimal amount.
            expected_currency: Expected currency (e.g. 'INR').
            db: Database session.
            
        Returns:
            Tuple of (existing_entry, is_replay). If not found, returns (None, False).
            
        Raises:
            IdempotencyConflictError: If the key was already used for a different payload.
        """
        existing: Optional[KhataEntry] = (
            db.query(KhataEntry)
            .filter(
                KhataEntry.store_id == store_id,
                KhataEntry.idempotency_key == idempotency_key,
            )
            .first()
        )

        if not existing:
            return None, False

        # Validate that the existing transaction matches expected payload
        existing_amount = Decimal(str(existing.amount)).quantize(Decimal("0.01"))
        expected_amount_quantized = expected_amount.quantize(Decimal("0.01"))

        if (
            existing.customer_id != expected_customer_id
            or existing.entry_type != expected_entry_type
            or existing_amount != expected_amount_quantized
            or existing.currency != expected_currency
        ):
            raise IdempotencyConflictError(
                f"Idempotency key '{idempotency_key}' was already used with conflicting "
                f"parameters (existing: {existing.entry_type} ₹{existing_amount} for customer {existing.customer_id}, "
                f"requested: {expected_entry_type} ₹{expected_amount_quantized} for customer {expected_customer_id})."
            )

        return existing, True
