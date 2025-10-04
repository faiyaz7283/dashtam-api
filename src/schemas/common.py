"""Common Pydantic schemas used across multiple modules.

This module contains schemas that are shared across different API endpoints,
such as generic message responses, pagination, error handling, etc.
"""

from typing import Optional

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
