"""Common Pydantic schemas used across multiple modules.

This module contains schemas that are shared across different API endpoints,
such as generic message responses, pagination, error handling, etc.
"""

import math
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Generic message response for simple API operations.

    Used for operations that don't return complex data, just a status message.
    Examples: logout, password reset request, email verification sent, etc.

    Attributes:
        message: Human-readable success or status message.
        detail: Optional additional details about the operation.
    """

    message: str = Field(
        ..., description="Human-readable success or status message", min_length=1
    )
    detail: Optional[str] = Field(
        default=None, description="Optional additional details about the operation"
    )

    model_config = {
        "json_schema_extra": {"example": {"message": "Operation successful"}}
    }


class HealthResponse(BaseModel):
    """Health check response.

    Attributes:
        status: Health status (e.g., 'healthy', 'degraded', 'unhealthy').
        version: API version.
    """

    status: str = Field(..., description="Health status of the API")
    version: str = Field(..., description="API version")

    model_config = {
        "json_schema_extra": {"example": {"status": "healthy", "version": "v1"}}
    }


class AuthorizationUrlResponse(BaseModel):
    """OAuth authorization URL response.

    Attributes:
        auth_url: The OAuth authorization URL to redirect to.
        message: Human-readable description.
    """

    auth_url: str = Field(..., description="OAuth authorization URL")
    message: str = Field(..., description="Human-readable message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "auth_url": "https://provider.com/oauth/authorize?...",
                "message": "Visit this URL to authorize MyProvider",
            }
        }
    }


class OAuthCallbackResponse(BaseModel):
    """OAuth callback completion response.

    Attributes:
        message: Human-readable success message.
        provider_id: UUID of the connected provider.
        alias: Provider alias/name.
        expires_in: Token expiration time in seconds (optional).
        scope: OAuth scopes granted (optional).
    """

    message: str = Field(..., description="Human-readable success message")
    provider_id: str = Field(..., description="UUID of the connected provider")
    alias: str = Field(..., description="Provider alias/name")
    expires_in: Optional[int] = Field(
        default=None, description="Token expiration in seconds"
    )
    scope: Optional[str] = Field(default=None, description="OAuth scopes granted")

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Successfully connected MySchwab!",
                "provider_id": "123e4567-e89b-12d3-a456-426614174000",
                "alias": "MySchwab",
                "expires_in": 3600,
                "scope": "read write",
            }
        }
    }


class TokenStatusResponse(BaseModel):
    """Token status information response.

    Attributes:
        provider_id: UUID of the provider.
        alias: Provider alias/name.
        status: Connection status ('connected', 'not_connected', etc.).
        message: Optional status message.
        has_access_token: Whether access token exists (optional).
        has_refresh_token: Whether refresh token exists (optional).
        expires_at: Access token expiration timestamp ISO 8601 (optional).
        created_at: Token creation timestamp ISO 8601 (optional).
        updated_at: Token last update timestamp ISO 8601 (optional).
    """

    provider_id: str = Field(..., description="UUID of the provider")
    alias: str = Field(..., description="Provider alias/name")
    status: str = Field(..., description="Connection status")
    message: Optional[str] = Field(default=None, description="Optional status message")
    has_access_token: Optional[bool] = Field(
        default=None, description="Whether access token exists"
    )
    has_refresh_token: Optional[bool] = Field(
        default=None, description="Whether refresh token exists"
    )
    expires_at: Optional[str] = Field(
        default=None, description="Token expiration timestamp (ISO 8601)"
    )
    created_at: Optional[str] = Field(
        default=None, description="Token creation timestamp (ISO 8601)"
    )
    updated_at: Optional[str] = Field(
        default=None, description="Token update timestamp (ISO 8601)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "provider_id": "123e4567-e89b-12d3-a456-426614174000",
                "alias": "MySchwab",
                "status": "connected",
                "has_access_token": True,
                "has_refresh_token": True,
                "expires_at": "2025-10-05T12:00:00Z",
            }
        }
    }


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response for list endpoints.

    Provides pagination metadata along with the items to enable
    efficient navigation through large result sets.

    Type Parameters:
        T: The type of items in the list.

    Attributes:
        items: List of items for the current page.
        total: Total number of items across all pages.
        page: Current page number (1-indexed).
        per_page: Number of items per page.
        pages: Total number of pages.
        has_next: Whether there is a next page available.
        has_prev: Whether there is a previous page available.
    """

    items: List[T] = Field(..., description="List of items for current page")
    total: int = Field(..., description="Total number of items", ge=0)
    page: int = Field(..., description="Current page number (1-indexed)", ge=1)
    per_page: int = Field(..., description="Items per page", ge=1)
    pages: int = Field(..., description="Total number of pages", ge=0)
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")

    @classmethod
    def create(
        cls, items: List[T], total: int, page: int, per_page: int
    ) -> "PaginatedResponse[T]":
        """Create paginated response with calculated metadata.

        Args:
            items: List of items for the current page.
            total: Total number of items across all pages.
            page: Current page number (1-indexed).
            per_page: Number of items per page.

        Returns:
            PaginatedResponse with all metadata calculated.
        """
        pages = math.ceil(total / per_page) if per_page > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
        )

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "per_page": 50,
                "pages": 2,
                "has_next": True,
                "has_prev": False,
            }
        }
    }
