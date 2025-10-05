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
