"""Schemas for token rotation API endpoints.

Request and response models for token rotation operations.
Follows REST API design principles with clean separation.
"""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# Request Schemas


class RotateUserTokensRequest(BaseModel):
    """Request to rotate tokens for specific user."""

    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Why tokens are being rotated (audit trail)",
        examples=["Password changed by user", "Suspicious activity detected"],
    )


class RotateGlobalTokensRequest(BaseModel):
    """Request to rotate all tokens system-wide (emergency)."""

    reason: str = Field(
        ...,
        min_length=20,
        max_length=1000,
        description="Detailed reason for global rotation (audit trail)",
        examples=["Encryption key compromised", "Database breach detected"],
    )
    grace_period_minutes: int = Field(
        default=15,
        ge=0,
        le=60,
        description="Minutes before full revocation (0-60)",
    )


# Response Schemas


class TokenRotationResponse(BaseModel):
    """Response from token rotation operation."""

    rotation_type: Literal["USER", "GLOBAL"] = Field(
        description="Type of rotation performed"
    )
    user_id: Optional[UUID] = Field(
        default=None, description="User ID (for USER rotation)"
    )
    old_version: int = Field(description="Previous version number")
    new_version: int = Field(description="New version number")
    tokens_revoked: int = Field(description="Number of tokens revoked")
    users_affected: Optional[int] = Field(
        default=None, description="Number of users affected (GLOBAL only)"
    )
    reason: str = Field(description="Why rotation was performed")
    initiated_by: Optional[str] = Field(
        default=None, description="Who initiated rotation (GLOBAL only)"
    )
    grace_period_minutes: Optional[int] = Field(
        default=None, description="Grace period before full revocation (GLOBAL only)"
    )
    rotated_at: datetime = Field(description="When rotation was performed (UTC)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "rotation_type": "USER",
                    "user_id": "123e4567-e89b-12d3-a456-426614174000",
                    "old_version": 1,
                    "new_version": 2,
                    "tokens_revoked": 3,
                    "reason": "Password changed by user",
                    "rotated_at": "2025-10-29T22:00:00Z",
                }
            ]
        }
    }


class SecurityConfigResponse(BaseModel):
    """Current global security configuration."""

    global_min_token_version: int = Field(
        description="Current global minimum token version"
    )
    last_updated_at: datetime = Field(
        description="When global version was last updated (UTC)"
    )
    last_updated_by: Optional[str] = Field(
        default=None, description="Who last updated global version"
    )
    last_rotation_reason: Optional[str] = Field(
        default=None, description="Reason for last global rotation"
    )
