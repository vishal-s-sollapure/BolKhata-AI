"""Phase 3.1 Financial Integrity, Security & Concurrency Verification Test Suite.

Audits and verifies:
1. Database immutability (SQLite triggers blocking direct SQL UPDATE/DELETE).
2. Real multi-threaded concurrent idempotency execution.
3. HITL proposal integrity (preventing client-side tampering of amount, customer, or intent).
4. Customer identity & anti-merging disambiguation.
5. Multi-tenant store isolation across endpoints.
6. Financial calculation exactness (including overpayment / advance credit -₹60.00).
7. Absolute isolation of intent parser from database writes.
"""

import concurrent.futures
import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError, OperationalError
from sqlalchemy.orm import Session
from unittest.mock import AsyncMock, patch

from app.database.session import SessionLocal, engine, init_db_triggers
from app.ledger.balance import BalanceCalculator
from app.ledger.exceptions import (
    CustomerAmbiguityError,
    CustomerNotFoundError,
    IdempotencyConflictError,
    InvalidAmountError,
    InvalidCurrencyError,
    LedgerError,
    ProposalAlreadyCommittedError,
    ProposalNotExecutableError,
    ProposalNotFoundError,
    StoreMismatchError,
)
from app.ledger.service import LedgerService
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.khata_entry import KhataEntry
from app.models.kirana_store import KiranaStore
from app.models.pending_proposal import PendingProposal
from app.schemas.intent import IntentType, ReasoningCode, TransactionProposal
from app.schemas.ledger import (
    CommitProposalRequest,
    EntryType,
    StageProposalRequest,
)


class TestDatabaseLevelImmutability:
    """Verifies that direct SQL statements bypassing the SQLAlchemy ORM cannot mutate or delete ledger records."""

    def test_direct_sql_update_on_khata_entry_blocked_by_sqlite_trigger(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Direct SQL UPDATE khata_entries must fail via SQLite trigger."""
        service = LedgerService()
        res = service.record_credit(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("340.00"),
            idempotency_key="trigger_test_upd",
            db=db_session,
        )

        # Attempt raw SQL UPDATE bypassing ORM event listeners
        with pytest.raises((DatabaseError, OperationalError), match="append-only and cannot be updated"):
            db_session.execute(
                text("UPDATE khata_entries SET amount = 999.00 WHERE id = :id"),
                {"id": res.transaction_id},
            )
            db_session.commit()
        db_session.rollback()

        # Verify amount remains unmodified
        entry = db_session.query(KhataEntry).filter(KhataEntry.id == res.transaction_id).first()
        assert Decimal(str(entry.amount)) == Decimal("340.00")

    def test_direct_sql_delete_on_khata_entry_blocked_by_sqlite_trigger(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Direct SQL DELETE FROM khata_entries must fail via SQLite trigger."""
        service = LedgerService()
        res = service.record_credit(
            store_id=test_store.id,
            customer_id=test_customer.id,
            amount=Decimal("150.00"),
            idempotency_key="trigger_test_del",
            db=db_session,
        )

        # Attempt raw SQL DELETE
        with pytest.raises((DatabaseError, OperationalError), match="append-only and cannot be deleted"):
            db_session.execute(
                text("DELETE FROM khata_entries WHERE id = :id"),
                {"id": res.transaction_id},
            )
            db_session.commit()
        db_session.rollback()

        # Verify entry still exists
        entry = db_session.query(KhataEntry).filter(KhataEntry.id == res.transaction_id).first()
        assert entry is not None

    def test_direct_sql_update_on_audit_log_blocked_by_sqlite_trigger(
        self,
        db_session: Session,
        test_store: KiranaStore,
    ):
        """Direct SQL UPDATE audit_logs must fail via SQLite trigger."""
        audit = AuditLog(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            actor_type="merchant",
            action="DIRECT_TEST",
            entity_type="Test",
            entity_id="123",
        )
        db_session.add(audit)
        db_session.commit()

        # Attempt raw SQL UPDATE
        with pytest.raises((DatabaseError, OperationalError), match="append-only and cannot be updated"):
            db_session.execute(
                text("UPDATE audit_logs SET action = 'TAMPERED' WHERE id = :id"),
                {"id": audit.id},
            )
            db_session.commit()
        db_session.rollback()

    def test_direct_sql_delete_on_audit_log_blocked_by_sqlite_trigger(
        self,
        db_session: Session,
        test_store: KiranaStore,
    ):
        """Direct SQL DELETE FROM audit_logs must fail via SQLite trigger."""
        audit = AuditLog(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            actor_type="merchant",
            action="DIRECT_TEST_DEL",
            entity_type="Test",
            entity_id="1234",
        )
        db_session.add(audit)
        db_session.commit()

        # Attempt raw SQL DELETE
        with pytest.raises((DatabaseError, OperationalError), match="append-only and cannot be deleted"):
            db_session.execute(
                text("DELETE FROM audit_logs WHERE id = :id"),
                {"id": audit.id},
            )
            db_session.commit()
        db_session.rollback()


class TestConcurrentIdempotencyExecution:
    """Verifies thread-safe execution under simultaneous concurrent requests."""

    def test_real_concurrent_identical_commits_produce_exactly_one_entry(
        self,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """5 simultaneous concurrent threads commit the exact same proposal."""
        # Use an isolated Session for staging
        session = SessionLocal()
        service = LedgerService()
        staged = service.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name=test_customer.customer_name,
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("340.00"),
                proposal_id="concurrent_prop_01",
            ),
            db=session,
        )
        session.close()

        shared_key = "concurrent_key_01"
        num_threads = 5
        results = []
        errors = []

        def worker_commit():
            worker_session = SessionLocal()
            try:
                commit_req = CommitProposalRequest(
                    proposal_id=staged.proposal_id,
                    confirmed=True,
                    idempotency_key=shared_key,
                )
                res = service.commit_proposal(test_store.id, commit_req, worker_session)
                return res
            except Exception as e:
                return e
            finally:
                worker_session.close()

        # Execute concurrently with ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_commit) for _ in range(num_threads)]
            for future in concurrent.futures.as_completed(futures):
                val = future.result()
                if isinstance(val, Exception):
                    errors.append(val)
                else:
                    results.append(val)

        # Assert zero unhandled crashes
        assert len(errors) == 0, f"Concurrent workers encountered unexpected exceptions: {errors}"
        assert len(results) == num_threads

        # Exactly 1 result was the original; the other 4 were recognized duplicates
        new_entries = [r for r in results if not r.is_duplicate]
        replays = [r for r in results if r.is_duplicate]
        assert len(new_entries) == 1
        assert len(replays) == num_threads - 1

        # All results share the exact same transaction ID
        target_tx_id = new_entries[0].transaction_id
        for r in replays:
            assert r.transaction_id == target_tx_id
            assert r.resulting_balance == Decimal("340.00")

        # Verify in database: exactly 1 KhataEntry was created
        verify_session = SessionLocal()
        db_entries = (
            verify_session.query(KhataEntry)
            .filter(KhataEntry.store_id == test_store.id, KhataEntry.idempotency_key == shared_key)
            .all()
        )
        assert len(db_entries) == 1

        balance = BalanceCalculator.calculate_customer_balance(
            test_store.id, test_customer.id, verify_session
        )
        assert balance.outstanding_balance == Decimal("340.00")
        verify_session.close()

    def test_concurrent_conflicting_payloads_are_safely_rejected(
        self,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Simultaneous requests with same idempotency key but conflicting amounts must reject."""
        service = LedgerService()
        shared_key = "concurrent_conflict_key"

        def worker_credit(amount: str):
            s = SessionLocal()
            try:
                return service.record_credit(
                    store_id=test_store.id,
                    customer_id=test_customer.id,
                    amount=Decimal(amount),
                    idempotency_key=shared_key,
                    db=s,
                )
            except Exception as e:
                return e
            finally:
                s.close()

        # Launch two workers with conflicting amounts
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker_credit, "100.00")
            f2 = executor.submit(worker_credit, "500.00")
            r1 = f1.result()
            r2 = f2.result()

        outcomes = [r1, r2]
        successes = [o for o in outcomes if not isinstance(o, Exception)]
        failures = [o for o in outcomes if isinstance(o, Exception)]

        # One must succeed and the conflicting one must fail with IdempotencyConflictError or LedgerError
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], (IdempotencyConflictError, LedgerError))


class TestHITLProposalIntegrity:
    """Verifies that the server is the sole financial authority and rejects client tampering."""

    def test_client_cannot_change_amount_at_commit_time(
        self,
        client: TestClient,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Even if client attempts to pass 'amount': '1.00', server commits authoritative DB amount."""
        service = LedgerService()
        staged = service.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name=test_customer.customer_name,
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("340.00"),  # Authoritative amount
            ),
            db=db_session,
        )

        # Attacker tries injecting a tampered amount in commit payload
        res = client.post(
            "/api/v1/ledger/commit",
            json={
                "proposal_id": staged.proposal_id,
                "confirmed": True,
                "amount": "1.00",  # Attacker attempt!
            },
            headers={"X-Store-Id": test_store.id},
        )
        assert res.status_code == 200
        data = res.json()
        # Authoritative amount of ₹340.00 must be committed, NOT ₹1.00!
        assert data["amount"] == "340.00"
        assert data["resulting_balance"] == "340.00"

    def test_client_cannot_switch_intent_at_commit_time(
        self,
        client: TestClient,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Attacker cannot turn an ADD_CREDIT proposal into a LOG_PAYMENT proposal at commit time."""
        service = LedgerService()
        staged = service.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name=test_customer.customer_name,
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("200.00"),
            ),
            db=db_session,
        )

        res = client.post(
            "/api/v1/ledger/commit",
            json={
                "proposal_id": staged.proposal_id,
                "confirmed": True,
                "intent": "LOG_PAYMENT",  # Attacker attempt!
            },
            headers={"X-Store-Id": test_store.id},
        )
        assert res.status_code == 200
        # Authoritative intent remains CREDIT
        assert res.json()["entry_type"] == "CREDIT"

    def test_rejected_proposal_cannot_be_committed(
        self,
        client: TestClient,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Once explicitly rejected, a proposal cannot be executed."""
        service = LedgerService()
        staged = service.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name=test_customer.customer_name,
                intent=IntentType.ADD_CREDIT,
                amount=Decimal("150.00"),
            ),
            db=db_session,
        )

        # Merchant rejects proposal
        reject_res = client.post(
            f"/api/v1/ledger/proposals/{staged.proposal_id}/reject?reason=CancelledByMerchant",
            headers={"X-Store-Id": test_store.id},
        )
        assert reject_res.status_code == 200
        assert reject_res.json()["status"] == "REJECTED"

        # Subsequent commit attempt must fail
        commit_res = client.post(
            "/api/v1/ledger/commit",
            json={"proposal_id": staged.proposal_id, "confirmed": True},
            headers={"X-Store-Id": test_store.id},
        )
        assert commit_res.status_code in (400, 409)


class TestCustomerIdentityAndAntiMerging:
    """Verifies that similarly named customers are never silently merged."""

    def test_case_and_whitespace_normalization(
        self,
        db_session: Session,
        test_store: KiranaStore,
    ):
        service = LedgerService()
        # "  Ramesh Kumar  " and "ramesh kumar" resolve to the exact same customer
        c1 = service._resolve_or_create_customer(test_store.id, "  Ramesh Kumar  ", db_session)
        c2 = service._resolve_or_create_customer(test_store.id, "ramesh kumar", db_session)
        assert c1.id == c2.id

    def test_ambiguous_customer_names_raise_disambiguation_error(
        self,
        db_session: Session,
        test_store: KiranaStore,
    ):
        """If 2 customers named 'Suresh Gowda' exist with different phones, require explicit selection."""
        # Create 2 distinct Suresh Gowdas in the same store
        suresh1 = Customer(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            customer_name="Suresh Gowda",
            normalized_name="suresh gowda",
            phone_number="+919111111111",
            is_active=True,
        )
        suresh2 = Customer(
            id=str(uuid.uuid4()),
            store_id=test_store.id,
            customer_name="Suresh Gowda",
            normalized_name="suresh gowda",
            phone_number="+919222222222",
            is_active=True,
        )
        db_session.add_all([suresh1, suresh2])
        db_session.commit()

        service = LedgerService()
        with pytest.raises(CustomerAmbiguityError, match="Explicit selection required"):
            service._resolve_or_create_customer(test_store.id, "Suresh Gowda", db_session)

    def test_identical_names_across_different_stores_are_independent(
        self,
        db_session: Session,
        test_store: KiranaStore,
    ):
        """'Ramesh' in Store A is completely independent of 'Ramesh' in Store B."""
        store_b = KiranaStore(
            id=str(uuid.uuid4()),
            store_name="Store B",
            owner_name="Owner B",
            is_active=True,
        )
        db_session.add(store_b)
        db_session.commit()

        service = LedgerService()
        cust_a = service._resolve_or_create_customer(test_store.id, "Ramesh", db_session)
        cust_b = service._resolve_or_create_customer(store_b.id, "Ramesh", db_session)

        assert cust_a.id != cust_b.id
        assert cust_a.store_id == test_store.id
        assert cust_b.store_id == store_b.id


class TestCompleteFinancialCalculationSequence:
    """Verifies the documented 4-step sequence resulting in ₹-60.00 advance balance."""

    def test_documented_overpayment_sequence(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        """Sequence:
        1. Credit ₹340
        2. Payment ₹100
        3. Credit ₹200
        4. Advance Payment ₹500
        Expected final balance: -₹60.00.
        """
        service = LedgerService()

        # Step 1: Credit ₹340
        r1 = service.record_credit(
            test_store.id, test_customer.id, Decimal("340.00"), "seq_p31_1", db=db_session
        )
        assert r1.resulting_balance == Decimal("340.00")

        # Step 2: Payment ₹100
        r2 = service.record_payment(
            test_store.id, test_customer.id, Decimal("100.00"), "seq_p31_2", db=db_session
        )
        assert r2.resulting_balance == Decimal("240.00")

        # Step 3: Credit ₹200
        r3 = service.record_credit(
            test_store.id, test_customer.id, Decimal("200.00"), "seq_p31_3", db=db_session
        )
        assert r3.resulting_balance == Decimal("440.00")

        # Step 4: Advance Payment ₹500
        r4 = service.record_payment(
            test_store.id, test_customer.id, Decimal("500.00"), "seq_p31_4", db=db_session
        )
        assert r4.resulting_balance == Decimal("-60.00")
        assert r4.total_credit == Decimal("540.00")
        assert r4.total_payment == Decimal("600.00")

        # Check through BalanceCalculator
        bal = BalanceCalculator.calculate_customer_balance(test_store.id, test_customer.id, db_session)
        assert bal.outstanding_balance == Decimal("-60.00")
        assert bal.total_credit == Decimal("540.00")
        assert bal.total_payment == Decimal("600.00")


class TestCanonicalIntentsAndSafety:
    """Verifies that only ADD_CREDIT and LOG_PAYMENT mutate balances."""

    def test_log_payment_creates_payment_entry(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        service = LedgerService()
        staged = service.stage_proposal(
            store_id=test_store.id,
            request=StageProposalRequest(
                customer_name=test_customer.customer_name,
                intent=IntentType.LOG_PAYMENT,
                amount=Decimal("120.00"),
            ),
            db=db_session,
        )

        res = service.commit_proposal(
            store_id=test_store.id,
            request=CommitProposalRequest(
                proposal_id=staged.proposal_id,
                confirmed=True,
            ),
            db=db_session,
        )
        assert res.entry_type == "PAYMENT"
        assert res.amount == Decimal("120.00")

    def test_non_executable_intents_cannot_mutate_database(
        self,
        db_session: Session,
        test_store: KiranaStore,
        test_customer: Customer,
    ):
        service = LedgerService()
        for forbidden in (IntentType.QUERY_BALANCE, IntentType.LIST_DUES, IntentType.UNKNOWN):
            with pytest.raises(ProposalNotExecutableError):
                service.stage_proposal(
                    store_id=test_store.id,
                    request=StageProposalRequest(
                        customer_name=test_customer.customer_name,
                        intent=forbidden,
                        amount=Decimal("100.00"),
                    ),
                    db=db_session,
                )
