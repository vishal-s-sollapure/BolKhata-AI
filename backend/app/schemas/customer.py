"""Pydantic schemas for KiranaStore Customer management in BolKhata AI."""

import re
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class CustomerBase(BaseModel):
    """Base customer schema with validation."""
    customer_name: str = Field(..., min_length=1, max_length=255, description="Full customer name")
    phone_number: Optional[str] = Field(None, max_length=20, description="Optional phone number")

    @field_validator("customer_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Customer name cannot be empty or whitespace.")
        return clean

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            clean = re.sub(r"[\s\-\(\)]", "", value.strip())
            if not clean:
                return None
            if not re.match(r"^\+?[0-9]{7,15}$", clean):
                raise ValueError("Invalid phone number format. Must contain 7 to 15 digits.")
            return clean
        return None


class CustomerCreate(CustomerBase):
    """Schema for registering a new customer under a kirana store."""
    pass


class CustomerUpdate(BaseModel):
    """Schema for updating an existing customer."""
    customer_name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone_number: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = Field(None, description="Soft-delete or reactivate flag")

    @field_validator("customer_name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            clean = value.strip()
            if not clean:
                raise ValueError("Customer name cannot be empty.")
            return clean
        return None


class CustomerResponse(BaseModel):
    """Authoritative customer response schema."""
    id: str = Field(..., description="Customer UUID")
    store_id: str = Field(..., description="Owning KiranaStore UUID")
    customer_name: str
    normalized_name: str
    phone_number: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerListResponse(BaseModel):
    """List of store customers with total count."""
    customers: List[CustomerResponse]
    total: int


class CustomerDisambiguationItem(BaseModel):
    """Candidate match when disambiguating between similarly named customers."""
    id: str
    customer_name: str
    phone_number: Optional[str]
    created_at: datetime


class CustomerDisambiguationResponse(BaseModel):
    """Response when a customer name matches multiple records in the same store."""
    message: str = "Multiple customers found with similar names. Please disambiguate."
    candidates: List[CustomerDisambiguationItem]
