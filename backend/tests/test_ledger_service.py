"""Unit tests for the Deterministic Ledger Engine service in BolKhata AI."""

import uuid
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.ledger.balance import BalanceCalculator
from app.ledger.exceptions import (
    CustomerNotFoundError,
    InactiveCustomerError,
    InvalidAmountError,
    InvalidCurrencyError,
    StoreNotFoundError,
)
from app.ledger.service import LedgerService
from app.models.customer import Customer
from app.models.kirana_store import KiranaStore
from app.schemas.ledger import EntryType


class TestLedgerService:
    """Verifies credit, payment, balance calculation, precision, and edge cases."""

    def test_add_credit(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Customer: Ramesh, Transaction: CREDIT, Amount: ₹340. Result: Balance increases by ₹340."""
        service = LedgerService()
        result = service.record_credit(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("340.00"),
            idempotency_key="test_credit_01",
            db=db_session,
        )

        assert result.transaction_id is not None
        assert result.entry_type == "CREDIT"
        assert result.amount == Decimal("340.00")
        assert result.resulting_balance == Decimal("340.00")
        assert result.total_credit == Decimal("340.00")
        assert result.total_payment == Decimal("0.00")
        assert result.is_duplicate is False

    def test_record_payment(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Opening ₹340 credit, record ₹200 payment. Result: Balance is ₹140."""
        service = LedgerService()
        service.record_credit(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("340.00"),
            idempotency_key="test_credit_seq",
            db=db_session,
        )

        payment_res = service.record_payment(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("200.00"),
            idempotency_key="test_payment_seq",
            db=db_session,
        )

        assert payment_res.entry_type == "PAYMENT"
        assert payment_res.amount == Decimal("200.00")
        assert payment_res.resulting_balance == Decimal("140.00")
        assert payment_res.total_credit == Decimal("340.00")
        assert payment_res.total_payment == Decimal("200.00")

    def test_canonical_balance_calculation_sequence(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Section 5 Example:
        Opening: ₹0
        Credit: ₹340
        Payment: ₹100
        Credit: ₹200
        Expected outstanding balance: ₹440.00.
        """
        service = LedgerService()

        # Step 1: Credit ₹340
        r1 = service.record_credit(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("340.00"),
            idempotency_key="seq_step_1",
            db=db_session,
        )
        assert r1.resulting_balance == Decimal("340.00")

        # Step 2: Payment ₹100
        r2 = service.record_payment(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("100.00"),
            idempotency_key="seq_step_2",
            db=db_session,
        )
        assert r2.resulting_balance == Decimal("240.00")

        # Step 3: Credit ₹200
        r3 = service.record_credit(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("200.00"),
            idempotency_key="seq_step_3",
            db=db_session,
        )
        assert r3.resulting_balance == Decimal("440.00")

        # Verify through BalanceCalculator directly
        balance = BalanceCalculator.calculate_customer_balance(
            store_id=test_store.id,
            customer_id=test_customer.id,
            db=db_session,
        )
        assert balance.total_credit == Decimal("540.00")
        assert balance.total_payment == Decimal("100.00")
        assert balance.outstanding_balance == Decimal("440.00")

    def test_zero_amount_rejected(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        service = LedgerService()
        with pytest.raises(InvalidAmountError, match="strictly greater than zero"):
            service.record_credit(
                store_id=test_store.id,
                customer_id=test_customer.id,
                amount=Decimal("0.00"),
                idempotency_key="idem_zero_test",
                db=db_session,
            )

    def test_negative_amount_rejected(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        service = LedgerService()
        with pytest.raises(InvalidAmountError, match="strictly greater than zero"):
            service.record_payment(
                store_id=test_store.id,
                customer_id=test_customer.id,
                amount=Decimal("-50.00"),
                idempotency_key="idem_neg_test",
                db=db_session,
            )

    def test_decimal_precision_handling(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Verifies exact cent/paise arithmetic (₹340.55 + ₹159.45 = ₹500.00)."""
        service = LedgerService()
        service.record_credit(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("340.55"),
            idempotency_key="prec_1",
            db=db_session,
        )
        res = service.record_credit(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("159.45"),
            idempotency_key="prec_2",
            db=db_session,
        )
        assert res.resulting_balance == Decimal("500.00")

    def test_overpayment_deterministic_behavior(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """When payment exceeds total credit, outstanding balance is negative Decimal (advance deposit)."""
        service = LedgerService()
        service.record_credit(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("100.00"),
            idempotency_key="op_credit",
            db=db_session,
        )
        res = service.record_payment(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("150.00"),
            idempotency_key="op_payment",
            db=db_session,
        )
        # Advance payment of ₹50.00 results in -₹50.00 balance
        assert res.resulting_balance == Decimal("-50.00")
        assert res.total_credit == Decimal("100.00")
        assert res.total_payment == Decimal("150.00")

    def test_customer_not_found(
        self,
        db_session: Session,
        test_store: KiranaStore,
    ):
        service = LedgerService()
        with pytest.raises(CustomerNotFoundError):
            service.record_credit(
                store_id=test_store.id,
                customer_id=str(uuid.uuid4()),
                amount=Decimal("100.00"),
                idempotency_key="idem_cnf",
                db=db_session,
            )

    def test_tenant_isolation_customer_belongs_to_different_store(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Attempting to access Customer of Store A using Store B fails."""
        # Create Store B
        store_b = KiranaStore(
            id=str(uuid.uuid4()),
            store_name="Store B",
            owner_name="Owner B",
            is_active=True,
        )
        db_session.add(store_b)
        db_session.commit()

        service = LedgerService()
        with pytest.raises(CustomerNotFoundError, match="not found in store"):
            service.record_credit(
                store_id=store_b.id,
                customer_id=test_customer.id,  # Belongs to test_store, not store_b
                amount=Decimal("100.00"),
                idempotency_key="idem_cross_store",
                db=db_session,
            )

    def test_inactive_customer_rejected(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Transactions on inactive customers must be rejected."""
        test_customer.is_active = False
        db_session.commit()

        service = LedgerService()
        with pytest.raises(InactiveCustomerError, match="inactive"):
            service.record_credit(
                store_id=test_store.id,
                customer_id=test_customer.id,
                amount=Decimal("100.00"),
                idempotency_key="idem_inactive",
                db=db_session,
            )
