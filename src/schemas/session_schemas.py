"""Session management request/response schemas.

Pydantic models for session API request validation and response serialization.
Kept separate from domain entities - these are HTTP-layer concerns.

RESTful Endpoints:
    GET    /api/v1/sessions           - List user sessions
    GET    /api/v1/sessions/{id}      - Get session details
    DELETE /api/v1/sessions/{id}      - Revoke specific session
    DELETE /api/v1/sessions           - Revoke all sessions (except current)
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Session Response (shared)
# =============================================================================


class SessionResponse(BaseModel):
    """Response schema for a single session.

    Used in both GET /sessions/{id} and as list item.
    """

    id: UUID = Field(..., description="Session identifier")
    device_info: str | None = Field(
        None,
        description="Parsed device info (e.g., 'Chrome on macOS')",
    )
    ip_address: str | None = Field(
        None,
        description="IP address at session creation",
    )
    location: str | None = Field(
        None,
        description="Geographic location (e.g., 'New York, US')",
    )
    created_at: datetime | None = Field(
        None,
        description="When session was created",
    )
    last_activity_at: datetime | None = Field(
        None,
        description="Last activity timestamp",
    )
    expires_at: datetime | None = Field(
        None,
        description="When session expires",
    )
    is_current: bool = Field(
        default=False,
        description="Whether this is the current session",
    )
    is_revoked: bool = Field(
        default=False,
        description="Whether session has been revoked",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "device_info": "Chrome on macOS",
                "ip_address": "192.168.1.1",
                "location": "New York, US",
                "created_at": "2024-01-15T10:30:00Z",
                "last_activity_at": "2024-01-15T14:45:00Z",
                "expires_at": "2024-02-14T10:30:00Z",
                "is_current": True,
                "is_revoked": False,
            }
        }
    )


# =============================================================================
# List Sessions
# =============================================================================


class SessionListResponse(BaseModel):
    """Response schema for session list.

    GET /api/v1/sessions
    Returns: 200 OK
    """

    sessions: list[SessionResponse] = Field(
        ...,
        description="List of user sessions",
    )
    total_count: int = Field(
        ...,
        description="Total number of sessions returned",
    )
    active_count: int = Field(
        ...,
        description="Number of active (non-revoked) sessions",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sessions": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "device_info": "Chrome on macOS",
                        "ip_address": "192.168.1.1",
                        "location": "New York, US",
                        "created_at": "2024-01-15T10:30:00Z",
                        "last_activity_at": "2024-01-15T14:45:00Z",
                        "expires_at": "2024-02-14T10:30:00Z",
                        "is_current": True,
                        "is_revoked": False,
                    }
                ],
                "total_count": 1,
                "active_count": 1,
            }
        }
    )


# =============================================================================
# Revoke Session
# =============================================================================


class SessionRevokeRequest(BaseModel):
    """Request schema for revoking a specific session.

    DELETE /api/v1/sessions/{id}
    Returns: 204 No Content

    Note: Session ID is in URL path, not body.
    This schema is for optional request body (reason).
    """

    reason: str = Field(
        default="manual",
        max_length=255,
        description="Reason for revocation (for audit)",
        examples=["manual", "suspicious", "device_lost"],
    )


# =============================================================================
# Revoke All Sessions
# =============================================================================


class SessionRevokeAllRequest(BaseModel):
    """Request schema for revoking all sessions.

    DELETE /api/v1/sessions
    Returns: 200 OK with count

    Revokes all sessions except the current one.
    """

    reason: str = Field(
        default="logout_all",
        max_length=255,
        description="Reason for bulk revocation",
        examples=["logout_all", "security_concern", "password_change"],
    )


class SessionRevokeAllResponse(BaseModel):
    """Response schema for bulk session revocation.

    DELETE /api/v1/sessions
    Returns: 200 OK
    """

    revoked_count: int = Field(
        ...,
        description="Number of sessions revoked",
    )
    message: str = Field(
        default="Sessions revoked successfully",
        description="Success message",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "revoked_count": 3,
                "message": "Sessions revoked successfully",
            }
        }
    )
