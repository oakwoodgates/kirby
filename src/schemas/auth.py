"""Pydantic schemas for authentication and API key management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)


class UserCreate(UserBase):
    """Schema for creating a new user."""

    is_admin: bool = False


class UserResponse(UserBase):
    """Schema for user responses."""

    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class APIKeyCreate(BaseModel):
    """Schema for creating a new API key."""

    name: Optional[str] = Field(None, max_length=100)
    rate_limit: Optional[int] = Field(None, ge=1, le=10000, description="Requests per minute")
    expires_in_days: Optional[int] = Field(None, ge=1, le=3650, description="Expiration in days from now")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate and clean the API key name."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class APIKeyResponse(BaseModel):
    """Schema for API key responses (without the full key)."""

    id: int
    user_id: int
    key_prefix: str
    name: Optional[str]
    is_active: bool
    rate_limit: Optional[int]
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class APIKeyCreated(APIKeyResponse):
    """Schema for API key creation response (includes the full key ONCE)."""

    key: str = Field(..., description="Full API key - save this! It will not be shown again")


class APIKeyUpdate(BaseModel):
    """Schema for updating an API key."""

    name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    rate_limit: Optional[int] = Field(None, ge=1, le=10000)
    expires_at: Optional[datetime] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate and clean the API key name."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class APIKeyUsageResponse(BaseModel):
    """Schema for API key usage log responses."""

    id: int
    api_key_id: int
    endpoint: str
    method: str
    status_code: int
    response_time_ms: Optional[int]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyUsageStats(BaseModel):
    """Schema for aggregated API key usage statistics."""

    api_key_id: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time_ms: Optional[float]
    period_start: datetime
    period_end: datetime
