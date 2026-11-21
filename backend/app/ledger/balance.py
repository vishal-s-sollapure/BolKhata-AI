"""Deterministic balance computation engine for BolKhata AI.

All monetary operations strictly utilize Python Decimal arithmetic to guarantee
absolute precision and avoid floating-point inaccuracies.
"""

from decimal import Decimal
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.khata_entry import KhataEntry
from app.models.kirana_store import KiranaStore
from app.schemas.ledger import CustomerBalanceResponse, StoreSummaryResponse
from app.ledger.exceptions import CustomerNotFoundError, StoreNotFoundError


class BalanceCalculator:
    """Sole deterministic authority for computing financial balances in BolKhata AI.
    
    CRITICAL INVARIANTS:
    1. Financial balances are NEVER calculated or updated by an LLM.
    2. Outstanding balance = Total CREDIT (udhaar) - Total PAYMENT (jama).
    3. Calculations are derived directly from the append-only KhataEntry records.
    4. Overpayments are handled deterministically: an overpayment results in a negative
       outstanding balance (indicating advance credit / deposit held with the merchant).
    5. All amounts are rounded and quantized to Decimal('0.01').
    """

    @staticmethod
    def calculate_customer_balance(
        store_id: str,
        customer_id: str,
        db: Session,
    ) -> CustomerBalanceResponse:
        """Calculates the authoritative credit, payment, and outstanding balance for a customer.
        
        Args:
            store_id: Tenant KiranaStore UUID.
            customer_id: Customer UUID.
            db: Active SQLAlchemy database session.
            
        Returns:
            CustomerBalanceResponse with total_credit, total_payment, and outstanding_balance.
            
        Raises:
            CustomerNotFoundError: If the customer does not exist in the specified store.
        """
        # Verify customer exists in this store
        customer = (
            db.query(Customer)
            .filter(Customer.id == customer_id, Customer.store_id == store_id)
            .first()
        )
        if not customer:
            raise CustomerNotFoundError(
                f"Customer '{customer_id}' not found in store '{store_id}'."
            )

        # Retrieve all entries for this customer in this store
        entries: List[KhataEntry] = (
            db.query(KhataEntry)
            .filter(
                KhataEntry.store_id == store_id,
                KhataEntry.customer_id == customer_id,
            )
            .all()
        )

        total_credit = Decimal("0.00")
        total_payment = Decimal("0.00")

        for entry in entries:
            amount = Decimal(str(entry.amount)).quantize(Decimal("0.01"))
            if entry.entry_type == "CREDIT":
                total_credit += amount
            elif entry.entry_type == "PAYMENT":
                total_payment += amount

        total_credit = total_credit.quantize(Decimal("0.01"))
        total_payment = total_payment.quantize(Decimal("0.01"))
        outstanding_balance = (total_credit - total_payment).quantize(Decimal("0.01"))

        return CustomerBalanceResponse(
            customer_id=customer.id,
            customer_name=customer.customer_name,
            currency="INR",
            total_credit=total_credit,
            total_payment=total_payment,
            outstanding_balance=outstanding_balance,
        )

    @staticmethod
    def calculate_store_summary(
        store_id: str,
        db: Session,
    ) -> StoreSummaryResponse:
        """Calculates store-wide financial summary metrics across all customers.
        
        Args:
            store_id: Tenant KiranaStore UUID.
            db: Active SQLAlchemy database session.
            
        Returns:
            StoreSummaryResponse with aggregated metrics.
            
        Raises:
            StoreNotFoundError: If the store does not exist.
        """
        store = db.query(KiranaStore).filter(KiranaStore.id == store_id).first()
        if not store:
            raise StoreNotFoundError(f"Store '{store_id}' not found.")

        # Aggregate credits and payments
        all_entries: List[KhataEntry] = (
            db.query(KhataEntry)
            .filter(KhataEntry.store_id == store_id)
            .all()
        )

        total_credit = Decimal("0.00")
        total_payment = Decimal("0.00")

        for entry in all_entries:
            amount = Decimal(str(entry.amount)).quantize(Decimal("0.01"))
            if entry.entry_type == "CREDIT":
                total_credit += amount
            elif entry.entry_type == "PAYMENT":
                total_payment += amount

        total_credit = total_credit.quantize(Decimal("0.01"))
        total_payment = total_payment.quantize(Decimal("0.01"))
        total_outstanding = (total_credit - total_payment).quantize(Decimal("0.01"))

        active_customers = (
            db.query(func.count(Customer.id))
            .filter(Customer.store_id == store_id, Customer.is_active == True)
            .scalar()
            or 0
        )

        return StoreSummaryResponse(
            store_id=store.id,
            store_name=store.store_name,
            currency="INR",
            total_credit=total_credit,
            total_payment=total_payment,
            total_outstanding_balance=total_outstanding,
            active_customers_count=active_customers,
            total_transactions_count=len(all_entries),
        )
