"""FastAPI endpoints for deterministic ledger operations and HITL proposal commits in BolKhata AI."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_store
from app.database.session import get_db
from app.ledger.exceptions import (
    CustomerAmbiguityError,
    CustomerNotFoundError,
    IdempotencyConflictError,
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
from app.ledger.service import LedgerService
from app.models.kirana_store import KiranaStore
from app.schemas.ledger import (
    CommitProposalRequest,
    CustomerBalanceResponse,
    CustomerEntriesResponse,
    LedgerCommitResponse,
    PendingProposalResponse,
    StageProposalRequest,
    StoreSummaryResponse,
)
from app.utils.logger import configure_logger

logger = configure_logger("bolkhata.api.ledger")
router = APIRouter(prefix="/ledger", tags=["Deterministic Ledger Engine"])
ledger_service = LedgerService()


@router.post(
    "/proposals",
    response_model=PendingProposalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Stage a validated proposal awaiting merchant confirmation",
    description="Stores an AI-generated TransactionProposal server-side. Sets a 15-minute "
                "time-to-live. Does NOT alter any financial balances.",
)
def stage_proposal(
    request: StageProposalRequest,
    current_store: KiranaStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> PendingProposalResponse:
    """Stages a proposal on the server for explicit shopkeeper confirmation."""
    try:
        return ledger_service.stage_proposal(
            store_id=current_store.id,
            request=request,
            db=db,
        )
    except ProposalNotExecutableError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (InvalidAmountError, InvalidCurrencyError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except StoreNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to stage proposal: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while staging the transaction proposal.",
        )


@router.post(
    "/commit",
    response_model=LedgerCommitResponse,
    status_code=status.HTTP_200_OK,
    summary="Commit confirmed proposal to the immutable ledger",
    description="Requires explicit merchant confirmation (confirmed=True). The server fetches "
                "the authoritative proposal by proposal_id and does NOT trust client-supplied amounts. "
                "Performs an atomic database commit and records an audit log.",
)
def commit_proposal(
    request: CommitProposalRequest,
    current_store: KiranaStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> LedgerCommitResponse:
    """Authoritatively commits a pending proposal to the immutable digital ledger."""
    try:
        return ledger_service.commit_proposal(
            store_id=current_store.id,
            request=request,
            db=db,
        )
    except ProposalNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except StoreMismatchError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ProposalExpiredError as e:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(e))
    except ProposalAlreadyCommittedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ProposalNotExecutableError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except InactiveCustomerError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CustomerAmbiguityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except IdempotencyConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except LedgerError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error committing ledger proposal: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to commit transaction to the ledger.",
        )


@router.get(
    "/customers/{customer_id}/balance",
    response_model=CustomerBalanceResponse,
    summary="Get customer credit, payment, and outstanding balance",
)
def get_customer_balance(
    customer_id: str,
    current_store: KiranaStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> CustomerBalanceResponse:
    """Calculates customer balance deterministically: Outstanding = Total CREDIT - Total PAYMENT."""
    try:
        return ledger_service.get_customer_balance(
            store_id=current_store.id,
            customer_id=customer_id,
            db=db,
        )
    except CustomerNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/customers/{customer_id}/entries",
    response_model=CustomerEntriesResponse,
    summary="Get chronological ledger entries for a customer",
)
def get_customer_entries(
    customer_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_store: KiranaStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> CustomerEntriesResponse:
    """Returns paginated, chronological immutable entries."""
    try:
        return ledger_service.get_customer_entries(
            store_id=current_store.id,
            customer_id=customer_id,
            limit=limit,
            offset=offset,
            db=db,
        )
    except CustomerNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/summary",
    response_model=StoreSummaryResponse,
    summary="Get store-level ledger metrics summary",
)
def get_store_summary(
    current_store: KiranaStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> StoreSummaryResponse:
    """Aggregates store metrics across all customers."""
    return ledger_service.get_store_summary(
        store_id=current_store.id,
        db=db,
    )
