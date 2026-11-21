"""FastAPI endpoints for customer management in BolKhata AI."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_store
from app.database.session import get_db
from app.ledger.exceptions import CustomerNotFoundError, StoreNotFoundError
from app.models.kirana_store import KiranaStore
from app.schemas.customer import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
)
from app.services.customer_service import CustomerService
from app.utils.logger import configure_logger

logger = configure_logger("bolkhata.api.customers")
router = APIRouter(prefix="/customers", tags=["Customer Management"])
customer_service = CustomerService()


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer under the current kirana store",
)
def create_customer(
    data: CustomerCreate,
    current_store: KiranaStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> CustomerResponse:
    """Registers a new customer for credit / debit tracking."""
    try:
        customer = customer_service.create_customer(
            store_id=current_store.id,
            data=data,
            db=db,
        )
        return CustomerResponse.model_validate(customer)
    except StoreNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Error creating customer: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register customer.",
        )


@router.get(
    "",
    response_model=CustomerListResponse,
    summary="List or search customers in the current kirana store",
)
def list_customers(
    q: Optional[str] = Query(None, description="Search term for customer name or phone"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_store: KiranaStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> CustomerListResponse:
    """Lists store customers with search and pagination."""
    customers = customer_service.list_customers(
        store_id=current_store.id,
        db=db,
        query=q,
        limit=limit,
        offset=offset,
    )
    return CustomerListResponse(
        customers=[CustomerResponse.model_validate(c) for c in customers],
        total=len(customers),
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Retrieve customer details by ID",
)
def get_customer(
    customer_id: str,
    current_store: KiranaStore = Depends(get_current_store),
    db: Session = Depends(get_db),
) -> CustomerResponse:
    """Retrieves customer record verifying tenant store isolation."""
    try:
        customer = customer_service.get_customer(
            store_id=current_store.id,
            customer_id=customer_id,
            db=db,
        )
        return CustomerResponse.model_validate(customer)
    except CustomerNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
