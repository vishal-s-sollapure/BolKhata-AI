"""Deterministic financial ledger service for BolKhata AI."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ledger.balance import BalanceCalculator
from app.ledger.idempotency import IdempotencyEngine
from app.ledger.exceptions import (
    CustomerAmbiguityError,
    CustomerNotFoundError,
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
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.khata_entry import KhataEntry
from app.models.kirana_store import KiranaStore
from app.models.pending_proposal import PendingProposal
from app.schemas.intent import IntentType
from app.schemas.ledger import (
    CommitProposalRequest,
    CustomerBalanceResponse,
    CustomerEntriesResponse,
    EntryType,
    KhataEntryResponse,
    LedgerCommitResponse,
    PendingProposalResponse,
    StageProposalRequest,
    StoreSummaryResponse,
)
from app.utils.logger import configure_logger

logger = configure_logger("bolkhata.ledger.service")


class LedgerService:
    """Sole financial transaction authority in BolKhata AI.
    
    ARCHITECTURAL PRINCIPLES:
    1. Zero LLM writes: The LLM produces proposals only; only LedgerService mutates balances.
    2. Append-only ledger: Balances are calculated dynamically using Decimal arithmetic.
    3. Idempotency protection: Replay requests return the existing transaction without re-mutating.
    4. HITL safety: Proposals require explicit confirmation and cannot be modified at commit time.
    5. Tenant isolation: Every entity and query is strictly scoped to store_id.
    """

    def __init__(self, proposal_ttl_minutes: int = 15) -> None:
        self.proposal_ttl_minutes = proposal_ttl_minutes

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _verify_store(self, store_id: str, db: Session) -> KiranaStore:
        """Verifies that the KiranaStore exists and is active."""
        store = (
            db.query(KiranaStore)
            .filter(KiranaStore.id == store_id, KiranaStore.is_active == True)
            .first()
        )
        if not store:
            raise StoreNotFoundError(f"Active KiranaStore '{store_id}' not found.")
        return store

    def _resolve_or_create_customer(
        self,
        store_id: str,
        customer_name: str,
        db: Session,
        phone_number: Optional[str] = None,
    ) -> Customer:
        """Finds an existing customer or creates a new one in the store."""
        clean_name = customer_name.strip()
        normalized = clean_name.lower()

        # Query existing customers
        query = db.query(Customer).filter(
            Customer.store_id == store_id,
            Customer.normalized_name == normalized,
        )
        if phone_number:
            query = query.filter(Customer.phone_number == phone_number)

        matches = query.all()
        if len(matches) == 1:
            customer = matches[0]
            if not customer.is_active:
                raise InactiveCustomerError(
                    f"Customer '{customer.customer_name}' is inactive/deactivated."
                )
            return customer
        elif len(matches) > 1:
            # Check if one of them is an exact case match
            exact_matches = [c for c in matches if c.customer_name == clean_name and c.is_active]
            if len(exact_matches) == 1:
                return exact_matches[0]
            raise CustomerAmbiguityError(
                f"Multiple customers match '{clean_name}'. Explicit selection required."
            )

        # Create new customer for this store
        customer = Customer(
            id=str(uuid.uuid4()),
            store_id=store_id,
            customer_name=clean_name,
            normalized_name=normalized,
            phone_number=phone_number,
            is_active=True,
        )
        db.add(customer)
        db.flush()

        # Audit customer creation
        audit = AuditLog(
            id=str(uuid.uuid4()),
            store_id=store_id,
            actor_type="system",
            action="CUSTOMER_CREATED_AUTO",
            entity_type="Customer",
            entity_id=customer.id,
            metadata_json=json.dumps({"customer_name": clean_name}),
        )
        db.add(audit)
        return customer

    # -------------------------------------------------------------------------
    # Proposal Staging (HITL Step 1)
    # -------------------------------------------------------------------------

    def stage_proposal(
        self,
        store_id: str,
        request: StageProposalRequest,
        db: Session,
    ) -> PendingProposalResponse:
        """Persists a validated TransactionProposal on the server awaiting merchant confirmation."""
        self._verify_store(store_id, db)

        # Enforce executable intents only
        valid_intents = (
            IntentType.ADD_CREDIT,
            IntentType.RECORD_PAYMENT,
            IntentType.LOG_PAYMENT,
        )
        if request.intent not in valid_intents:
            raise ProposalNotExecutableError(
                f"Intent '{request.intent}' cannot be staged for ledger mutation. "
                "Only ADD_CREDIT and LOG_PAYMENT / RECORD_PAYMENT create ledger entries."
            )

        amount = request.amount.quantize(Decimal("0.01"))
        if amount <= Decimal("0"):
            raise InvalidAmountError("Transaction amount must be strictly greater than zero.")

        proposal_id = request.proposal_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self.proposal_ttl_minutes)

        # Try to pre-resolve customer if one exists or if explicitly provided
        clean_name = request.customer_name.strip()
        customer_id = None
        if request.customer_id:
            cust = (
                db.query(Customer)
                .filter(Customer.id == request.customer_id, Customer.store_id == store_id)
                .first()
            )
            if not cust:
                raise CustomerNotFoundError(
                    f"Customer '{request.customer_id}' not found in store '{store_id}'."
                )
            if not cust.is_active:
                raise InactiveCustomerError(f"Customer '{cust.customer_name}' is inactive.")
            customer_id = cust.id
            clean_name = cust.customer_name
        else:
            cust_query = db.query(Customer).filter(
                Customer.store_id == store_id,
                Customer.normalized_name == clean_name.lower(),
                Customer.is_active == True,
            )
            if request.phone_number:
                cust_query = cust_query.filter(Customer.phone_number == request.phone_number)
            matches = cust_query.all()
            if len(matches) == 1:
                customer_id = matches[0].id

        summary = request.summary or (
            f"Add ₹{amount:.2f} credit for {clean_name}"
            if request.intent == IntentType.ADD_CREDIT
            else f"Record ₹{amount:.2f} payment from {clean_name}"
        )

        pending = PendingProposal(
            id=str(uuid.uuid4()),
            store_id=store_id,
            proposal_id=proposal_id,
            customer_name=clean_name,
            customer_id=customer_id,
            intent=request.intent.value,
            amount=amount,
            currency="INR",
            summary=summary,
            status="PENDING",
            requires_confirmation=True,
            created_at=now,
            expires_at=expires_at,
            raw_transcript=request.raw_transcript,
        )

        db.add(pending)

        # Log audit record
        audit = AuditLog(
            id=str(uuid.uuid4()),
            store_id=store_id,
            actor_type="system",
            action="PROPOSAL_STAGED",
            entity_type="PendingProposal",
            entity_id=pending.id,
            metadata_json=json.dumps({
                "proposal_id": proposal_id,
                "intent": request.intent.value,
                "amount": str(amount),
                "customer_name": clean_name,
            }),
        )
        db.add(audit)
        db.commit()
        db.refresh(pending)

        return PendingProposalResponse(
            proposal_id=pending.proposal_id,
            store_id=pending.store_id,
            customer_name=pending.customer_name,
            intent=pending.intent,
            amount=pending.amount,
            currency=pending.currency,
            summary=pending.summary,
            status=pending.status,
            requires_confirmation=pending.requires_confirmation,
            created_at=pending.created_at,
            expires_at=pending.expires_at,
        )

    # -------------------------------------------------------------------------
    # Proposal Rejection (HITL Step 1b)
    # -------------------------------------------------------------------------

    def reject_proposal(
        self,
        store_id: str,
        proposal_id: str,
        db: Session,
        reason: Optional[str] = None,
    ) -> PendingProposalResponse:
        """Explicitly cancels / rejects a pending proposal before it can be committed."""
        self._verify_store(store_id, db)

        proposal = (
            db.query(PendingProposal)
            .filter(
                PendingProposal.proposal_id == proposal_id,
                PendingProposal.store_id == store_id,
            )
            .first()
        )
        if not proposal:
            raise ProposalNotFoundError(f"Proposal '{proposal_id}' not found in store '{store_id}'.")

        if proposal.status == "COMMITTED":
            raise ProposalAlreadyCommittedError(
                f"Proposal '{proposal_id}' is already committed and cannot be rejected."
            )

        proposal.status = "REJECTED"
        audit = AuditLog(
            id=str(uuid.uuid4()),
            store_id=store_id,
            actor_type="merchant",
            action="PROPOSAL_REJECTED",
            entity_type="PendingProposal",
            entity_id=proposal.id,
            metadata_json=json.dumps({"proposal_id": proposal_id, "reason": reason}),
        )
        db.add(audit)
        db.commit()
        db.refresh(proposal)

        return PendingProposalResponse(
            proposal_id=proposal.proposal_id,
            store_id=proposal.store_id,
            customer_name=proposal.customer_name,
            intent=proposal.intent,
            amount=proposal.amount,
            currency=proposal.currency,
            summary=proposal.summary,
            status=proposal.status,
            requires_confirmation=proposal.requires_confirmation,
            created_at=proposal.created_at,
            expires_at=proposal.expires_at,
        )

    # -------------------------------------------------------------------------
    # Proposal Commit (HITL Step 2)
    # -------------------------------------------------------------------------

    def commit_proposal(
        self,
        store_id: str,
        request: CommitProposalRequest,
        db: Session,
    ) -> LedgerCommitResponse:
        """Authoritatively commits a previously staged proposal after explicit merchant confirmation."""
        self._verify_store(store_id, db)

        if not request.confirmed:
            raise LedgerError("Proposal must be explicitly confirmed by the merchant (confirmed=True).")

        # 1. Fetch authoritative proposal from DB
        proposal: Optional[PendingProposal] = (
            db.query(PendingProposal)
            .filter(PendingProposal.proposal_id == request.proposal_id)
            .first()
        )

        if not proposal:
            raise ProposalNotFoundError(
                f"Proposal '{request.proposal_id}' was not found."
            )

        # Verify store ownership
        if proposal.store_id != store_id:
            raise StoreMismatchError(
                f"Proposal '{request.proposal_id}' does not belong to store '{store_id}'."
            )

        # 2. Check if proposal has already been committed (Idempotent safety)
        if proposal.status == "COMMITTED":
            logger.info("Proposal '%s' is already committed. Returning existing transaction.", request.proposal_id)
            if proposal.khata_entry_id:
                existing_entry = db.query(KhataEntry).filter(KhataEntry.id == proposal.khata_entry_id).first()
                if existing_entry:
                    customer = db.query(Customer).filter(Customer.id == existing_entry.customer_id).first()
                    balance = BalanceCalculator.calculate_customer_balance(store_id, customer.id, db)

                    # Log duplicate audit
                    audit = AuditLog(
                        id=str(uuid.uuid4()),
                        store_id=store_id,
                        actor_type=request.actor_type,
                        actor_id=request.actor_id,
                        action="DUPLICATE_COMMIT_ATTEMPT",
                        entity_type="KhataEntry",
                        entity_id=existing_entry.id,
                        metadata_json=json.dumps({"proposal_id": request.proposal_id}),
                    )
                    db.add(audit)
                    db.commit()

                    return LedgerCommitResponse(
                        transaction_id=existing_entry.id,
                        store_id=store_id,
                        customer_id=customer.id,
                        customer_name=customer.customer_name,
                        entry_type=existing_entry.entry_type,
                        amount=Decimal(str(existing_entry.amount)),
                        currency=existing_entry.currency,
                        resulting_balance=balance.outstanding_balance,
                        total_credit=balance.total_credit,
                        total_payment=balance.total_payment,
                        created_at=existing_entry.created_at,
                        is_duplicate=True,
                        proposal_id=proposal.proposal_id,
                        idempotency_key=existing_entry.idempotency_key,
                    )
            raise ProposalAlreadyCommittedError(
                f"Proposal '{request.proposal_id}' has already been committed."
            )

        if proposal.status == "REJECTED":
            raise ProposalAlreadyCommittedError(
                f"Proposal '{request.proposal_id}' was previously rejected."
            )

        # 3. Check expiration
        now = datetime.now(timezone.utc)
        if proposal.expires_at.replace(tzinfo=timezone.utc) < now:
            proposal.status = "EXPIRED"
            db.commit()
            raise ProposalExpiredError(
                f"Proposal '{request.proposal_id}' expired at {proposal.expires_at}."
            )

        # 4. Map intent to entry type
        intent_str = proposal.intent.upper()
        if intent_str == "ADD_CREDIT":
            entry_type = "CREDIT"
        elif intent_str in ("RECORD_PAYMENT", "LOG_PAYMENT"):
            entry_type = "PAYMENT"
        else:
            raise ProposalNotExecutableError(
                f"Cannot commit non-executable intent '{proposal.intent}'."
            )

        # 5. Resolve customer
        if proposal.customer_id:
            customer = (
                db.query(Customer)
                .filter(Customer.id == proposal.customer_id, Customer.store_id == store_id)
                .first()
            )
            if not customer:
                raise CustomerNotFoundError("Associated customer record was removed.")
            if not customer.is_active:
                raise InactiveCustomerError(f"Customer '{customer.customer_name}' is inactive.")
        else:
            customer = self._resolve_or_create_customer(store_id, proposal.customer_name, db)
            proposal.customer_id = customer.id

        # 6. Idempotency Check
        idempotency_key = request.idempotency_key or f"prop_{proposal.proposal_id}"
        amount = Decimal(str(proposal.amount)).quantize(Decimal("0.01"))

        existing_entry, is_replay = IdempotencyEngine.check_idempotency(
            store_id=store_id,
            idempotency_key=idempotency_key,
            expected_customer_id=customer.id,
            expected_entry_type=entry_type,
            expected_amount=amount,
            expected_currency=proposal.currency,
            db=db,
        )

        if is_replay and existing_entry:
            balance = BalanceCalculator.calculate_customer_balance(store_id, customer.id, db)
            return LedgerCommitResponse(
                transaction_id=existing_entry.id,
                store_id=store_id,
                customer_id=customer.id,
                customer_name=customer.customer_name,
                entry_type=existing_entry.entry_type,
                amount=amount,
                currency=existing_entry.currency,
                resulting_balance=balance.outstanding_balance,
                total_credit=balance.total_credit,
                total_payment=balance.total_payment,
                created_at=existing_entry.created_at,
                is_duplicate=True,
                proposal_id=proposal.proposal_id,
                idempotency_key=existing_entry.idempotency_key,
            )

        # 7. Atomic Transaction Commit
        try:
            khata_entry = KhataEntry(
                id=str(uuid.uuid4()),
                store_id=store_id,
                customer_id=customer.id,
                entry_type=entry_type,
                amount=amount,
                currency=proposal.currency,
                description=request.notes or proposal.summary,
                idempotency_key=idempotency_key,
                created_by=request.actor_type,
                proposal_id=proposal.proposal_id,
                metadata_json=json.dumps({"transcript": proposal.raw_transcript}),
            )
            db.add(khata_entry)
            db.flush()

            # Mark proposal committed
            proposal.status = "COMMITTED"
            proposal.khata_entry_id = khata_entry.id
            proposal.committed_at = now

            # Audit record
            audit = AuditLog(
                id=str(uuid.uuid4()),
                store_id=store_id,
                actor_type=request.actor_type,
                actor_id=request.actor_id,
                action="TRANSACTION_COMMITTED",
                entity_type="KhataEntry",
                entity_id=khata_entry.id,
                metadata_json=json.dumps({
                    "proposal_id": proposal.proposal_id,
                    "customer_id": customer.id,
                    "customer_name": customer.customer_name,
                    "entry_type": entry_type,
                    "amount": str(amount),
                    "idempotency_key": idempotency_key,
                }),
            )
            db.add(audit)
            db.commit()
            db.refresh(khata_entry)

        except IntegrityError as e:
            db.rollback()
            logger.info("IntegrityError during proposal commit (concurrent race handled): %s", str(e))
            existing_entry, is_replay = IdempotencyEngine.check_idempotency(
                store_id=store_id,
                idempotency_key=idempotency_key,
                expected_customer_id=customer.id,
                expected_entry_type=entry_type,
                expected_amount=amount,
                expected_currency=proposal.currency,
                db=db,
            )
            if is_replay and existing_entry:
                balance = BalanceCalculator.calculate_customer_balance(store_id, customer.id, db)
                return LedgerCommitResponse(
                    transaction_id=existing_entry.id,
                    store_id=store_id,
                    customer_id=customer.id,
                    customer_name=customer.customer_name,
                    entry_type=existing_entry.entry_type,
                    amount=amount,
                    currency=existing_entry.currency,
                    resulting_balance=balance.outstanding_balance,
                    total_credit=balance.total_credit,
                    total_payment=balance.total_payment,
                    created_at=existing_entry.created_at,
                    is_duplicate=True,
                    proposal_id=proposal.proposal_id,
                    idempotency_key=existing_entry.idempotency_key,
                )
            raise LedgerError(f"Database integrity violation during commit: {str(e)}") from e
        except Exception as e:
            db.rollback()
            logger.exception("Database transaction failed during proposal commit: %s", str(e))
            raise LedgerError(f"Transaction failed and was safely rolled back: {str(e)}") from e

        # 8. Compute resulting balance
        balance = BalanceCalculator.calculate_customer_balance(store_id, customer.id, db)

        return LedgerCommitResponse(
            transaction_id=khata_entry.id,
            store_id=store_id,
            customer_id=customer.id,
            customer_name=customer.customer_name,
            entry_type=khata_entry.entry_type,
            amount=amount,
            currency=khata_entry.currency,
            resulting_balance=balance.outstanding_balance,
            total_credit=balance.total_credit,
            total_payment=balance.total_payment,
            created_at=khata_entry.created_at,
            is_duplicate=False,
            proposal_id=proposal.proposal_id,
            idempotency_key=idempotency_key,
        )

    # -------------------------------------------------------------------------
    # Direct Programmatic Transactions (for Unit Tests & Admin Services)
    # -------------------------------------------------------------------------

    def record_transaction(
        self,
        store_id: str,
        customer_id: str,
        entry_type: EntryType,
        amount: Decimal,
        idempotency_key: str,
        currency: str = "INR",
        description: Optional[str] = None,
        created_by: str = "merchant",
        proposal_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> LedgerCommitResponse:
        """Records a direct CREDIT or PAYMENT entry with atomic transaction guarantees."""
        if db is None:
            raise LedgerError("Database session is required.")

        self._verify_store(store_id, db)

        # Validate amount
        if amount <= Decimal("0"):
            raise InvalidAmountError("Transaction amount must be strictly greater than zero.")
        amount_quantized = amount.quantize(Decimal("0.01"))

        if currency.upper() != "INR":
            raise InvalidCurrencyError("Only 'INR' currency is supported.")

        # Verify customer
        customer = (
            db.query(Customer)
            .filter(Customer.id == customer_id, Customer.store_id == store_id)
            .first()
        )
        if not customer:
            raise CustomerNotFoundError(
                f"Customer '{customer_id}' not found in store '{store_id}'."
            )
        if not customer.is_active:
            raise InactiveCustomerError(
                f"Customer '{customer.customer_name}' is inactive/deactivated."
            )

        entry_type_str = entry_type.value if isinstance(entry_type, EntryType) else str(entry_type)

        # Idempotency check
        existing_entry, is_replay = IdempotencyEngine.check_idempotency(
            store_id=store_id,
            idempotency_key=idempotency_key,
            expected_customer_id=customer.id,
            expected_entry_type=entry_type_str,
            expected_amount=amount_quantized,
            expected_currency="INR",
            db=db,
        )

        if is_replay and existing_entry:
            balance = BalanceCalculator.calculate_customer_balance(store_id, customer.id, db)
            return LedgerCommitResponse(
                transaction_id=existing_entry.id,
                store_id=store_id,
                customer_id=customer.id,
                customer_name=customer.customer_name,
                entry_type=existing_entry.entry_type,
                amount=amount_quantized,
                currency="INR",
                resulting_balance=balance.outstanding_balance,
                total_credit=balance.total_credit,
                total_payment=balance.total_payment,
                created_at=existing_entry.created_at,
                is_duplicate=True,
                proposal_id=proposal_id,
                idempotency_key=idempotency_key,
            )

        # Atomic commit
        try:
            entry = KhataEntry(
                id=str(uuid.uuid4()),
                store_id=store_id,
                customer_id=customer.id,
                entry_type=entry_type_str,
                amount=amount_quantized,
                currency="INR",
                description=description,
                idempotency_key=idempotency_key,
                created_by=created_by,
                proposal_id=proposal_id,
            )
            db.add(entry)
            db.flush()

            audit = AuditLog(
                id=str(uuid.uuid4()),
                store_id=store_id,
                actor_type=created_by,
                action="TRANSACTION_COMMITTED_DIRECT",
                entity_type="KhataEntry",
                entity_id=entry.id,
                metadata_json=json.dumps({
                    "customer_id": customer.id,
                    "entry_type": entry_type_str,
                    "amount": str(amount_quantized),
                    "idempotency_key": idempotency_key,
                }),
            )
            db.add(audit)
            db.commit()
            db.refresh(entry)

        except IntegrityError as e:
            db.rollback()
            logger.info("IntegrityError during direct transaction (concurrent race handled): %s", str(e))
            existing_entry, is_replay = IdempotencyEngine.check_idempotency(
                store_id=store_id,
                idempotency_key=idempotency_key,
                expected_customer_id=customer.id,
                expected_entry_type=entry_type_str,
                expected_amount=amount_quantized,
                expected_currency="INR",
                db=db,
            )
            if is_replay and existing_entry:
                balance = BalanceCalculator.calculate_customer_balance(store_id, customer.id, db)
                return LedgerCommitResponse(
                    transaction_id=existing_entry.id,
                    store_id=store_id,
                    customer_id=customer.id,
                    customer_name=customer.customer_name,
                    entry_type=existing_entry.entry_type,
                    amount=amount_quantized,
                    currency="INR",
                    resulting_balance=balance.outstanding_balance,
                    total_credit=balance.total_credit,
                    total_payment=balance.total_payment,
                    created_at=existing_entry.created_at,
                    is_duplicate=True,
                    proposal_id=proposal_id,
                    idempotency_key=idempotency_key,
                )
            raise LedgerError(f"Database integrity violation during direct transaction: {str(e)}") from e
        except Exception as e:
            db.rollback()
            logger.exception("Failed direct transaction commit: %s", str(e))
            raise LedgerError(f"Direct transaction commit failed: {str(e)}") from e

        balance = BalanceCalculator.calculate_customer_balance(store_id, customer.id, db)

        return LedgerCommitResponse(
            transaction_id=entry.id,
            store_id=store_id,
            customer_id=customer.id,
            customer_name=customer.customer_name,
            entry_type=entry.entry_type,
            amount=amount_quantized,
            currency="INR",
            resulting_balance=balance.outstanding_balance,
            total_credit=balance.total_credit,
            total_payment=balance.total_payment,
            created_at=entry.created_at,
            is_duplicate=False,
            proposal_id=proposal_id,
            idempotency_key=idempotency_key,
        )

    def record_credit(
        self,
        store_id: str,
        customer_id: str,
        amount: Decimal,
        idempotency_key: str,
        description: Optional[str] = None,
        created_by: str = "merchant",
        proposal_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> LedgerCommitResponse:
        """Convenience method to record credit (udhaar)."""
        return self.record_transaction(
            store_id=store_id,
            customer_id=customer_id,
            entry_type=EntryType.CREDIT,
            amount=amount,
            idempotency_key=idempotency_key,
            currency="INR",
            description=description,
            created_by=created_by,
            proposal_id=proposal_id,
            db=db,
        )

    def record_payment(
        self,
        store_id: str,
        customer_id: str,
        amount: Decimal,
        idempotency_key: str,
        description: Optional[str] = None,
        created_by: str = "merchant",
        proposal_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> LedgerCommitResponse:
        """Convenience method to record payment (jama)."""
        return self.record_transaction(
            store_id=store_id,
            customer_id=customer_id,
            entry_type=EntryType.PAYMENT,
            amount=amount,
            idempotency_key=idempotency_key,
            currency="INR",
            description=description,
            created_by=created_by,
            proposal_id=proposal_id,
            db=db,
        )

    # -------------------------------------------------------------------------
    # Queries & History
    # -------------------------------------------------------------------------

    def get_customer_balance(
        self,
        store_id: str,
        customer_id: str,
        db: Session,
    ) -> CustomerBalanceResponse:
        """Retrieves the customer balance."""
        self._verify_store(store_id, db)
        return BalanceCalculator.calculate_customer_balance(store_id, customer_id, db)

    def get_customer_entries(
        self,
        store_id: str,
        customer_id: str,
        db: Session,
        limit: int = 50,
        offset: int = 0,
    ) -> CustomerEntriesResponse:
        """Retrieves chronological ledger entries for a customer."""
        self._verify_store(store_id, db)
        customer = (
            db.query(Customer)
            .filter(Customer.id == customer_id, Customer.store_id == store_id)
            .first()
        )
        if not customer:
            raise CustomerNotFoundError(
                f"Customer '{customer_id}' not found in store '{store_id}'."
            )

        total = (
            db.query(func.count(KhataEntry.id))
            .filter(KhataEntry.store_id == store_id, KhataEntry.customer_id == customer_id)
            .scalar()
            or 0
        )

        entries = (
            db.query(KhataEntry)
            .filter(KhataEntry.store_id == store_id, KhataEntry.customer_id == customer_id)
            .order_by(KhataEntry.created_at.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return CustomerEntriesResponse(
            customer_id=customer.id,
            customer_name=customer.customer_name,
            currency="INR",
            entries=[
                KhataEntryResponse(
                    id=e.id,
                    store_id=e.store_id,
                    customer_id=e.customer_id,
                    entry_type=e.entry_type,
                    amount=Decimal(str(e.amount)),
                    currency=e.currency,
                    description=e.description,
                    idempotency_key=e.idempotency_key,
                    proposal_id=e.proposal_id,
                    created_at=e.created_at,
                    created_by=e.created_by,
                )
                for e in entries
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_store_summary(
        self,
        store_id: str,
        db: Session,
    ) -> StoreSummaryResponse:
        """Calculates store financial summary."""
        return BalanceCalculator.calculate_store_summary(store_id, db)
