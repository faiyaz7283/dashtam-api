"""Token rotation request/response schemas.

Pydantic models for admin API token rotation endpoints.
Admin-only operations for breach response and security management.

RESTful Endpoints (admin-only):
    POST   /api/v1/admin/security/rotations        - Global token rotation
    POST   /api/v1/admin/users/{user_id}/rotations - Per-user token rotation
    GET    /api/v1/admin/security/config           - Get security config
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Global Token Rotation
# =============================================================================


class GlobalRotationRequest(BaseModel):
    """Request schema for global token rotation.

    POST /api/v1/admin/security/rotations
    Returns: 201 Created

    Admin-only. Invalidates ALL tokens with version below new minimum.
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Reason for rotation (for audit trail)",
        examples=["Database breach detected", "Security vulnerability patched"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reason": "Database breach detected - rotating all tokens",
            }
        }
    )


class GlobalRotationResponse(BaseModel):
    """Response schema for global token rotation (201 Created)."""

    previous_version: int = Field(
        ...,
        description="Previous global minimum token version",
    )
    new_version: int = Field(
        ...,
        description="New global minimum token version",
    )
    grace_period_seconds: int = Field(
        ...,
        description="Seconds before old tokens fully rejected",
    )
    message: str = Field(
        default="Global token rotation triggered successfully",
        description="Success message",
    )


# =============================================================================
# Per-User Token Rotation
# =============================================================================


class UserRotationRequest(BaseModel):
    """Request schema for per-user token rotation.

    POST /api/v1/admin/users/{user_id}/rotations
    Returns: 201 Created

    Admin operation. Invalidates only the specified user's tokens.
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Reason for rotation (for audit trail)",
        examples=["Suspicious activity detected", "User requested log out everywhere"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reason": "Suspicious activity detected on account",
            }
        }
    )


class UserRotationResponse(BaseModel):
    """Response schema for per-user token rotation (201 Created)."""

    user_id: UUID = Field(
        ...,
        description="User whose tokens were rotated",
    )
    previous_version: int = Field(
        ...,
        description="Previous user minimum token version",
    )
    new_version: int = Field(
        ...,
        description="New user minimum token version",
    )
    message: str = Field(
        default="User token rotation triggered successfully",
        description="Success message",
    )


# =============================================================================
# Security Configuration
# =============================================================================


class SecurityConfigResponse(BaseModel):
    """Response schema for security configuration.

    GET /api/v1/admin/security/config
    Returns: 200 OK
    """

    global_min_token_version: int = Field(
        ...,
        description="Current global minimum token version",
    )
    grace_period_seconds: int = Field(
        ...,
        description="Grace period for token rotation (seconds)",
    )
    last_rotation_at: str | None = Field(
        None,
        description="ISO timestamp of last global rotation (null if never)",
    )
    last_rotation_reason: str | None = Field(
        None,
        description="Reason for last global rotation (null if never)",
    )
