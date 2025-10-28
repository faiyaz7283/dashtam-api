"""Pydantic schemas for session management API endpoints.

All schemas follow project REST API standards:
- Separate request/response schemas
- No inline models in routers
- Descriptive field names and validation
- Comprehensive docstrings
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SessionInfoResponse(BaseModel):
    """Single session information for API response.

    Represents one active session (device) for the user.
    """

    id: UUID = Field(description="Unique session identifier (refresh token ID)")

    device_info: str = Field(
        description="Human-readable device information (e.g., 'Chrome on macOS')"
    )

    location: str = Field(
        description="City-level location from IP address (e.g., 'San Francisco, USA')"
    )

    ip_address: str | None = Field(
        default=None, description="IP address (optional, privacy setting)"
    )

    last_activity: datetime = Field(description="Last time session was used (UTC)")

    created_at: datetime = Field(description="Session creation time (UTC)")

    is_current: bool = Field(
        description="Whether this is the current session (from JWT jti claim)"
    )

    is_trusted: bool = Field(description="Whether user marked this device as trusted")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "device_info": "Chrome on macOS",
                "location": "San Francisco, USA",
                "ip_address": "192.168.1.1",
                "last_activity": "2025-10-27T15:30:00Z",
                "created_at": "2025-10-20T10:00:00Z",
                "is_current": True,
                "is_trusted": False,
            }
        }


class SessionListResponse(BaseModel):
    """Response for GET /api/v1/auth/sessions (list all sessions)."""

    sessions: list[SessionInfoResponse] = Field(
        description="List of active sessions (sorted by last_activity DESC)"
    )

    total_count: int = Field(description="Total number of active sessions")

    class Config:
        json_schema_extra = {
            "example": {
                "sessions": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "device_info": "Chrome on macOS",
                        "location": "San Francisco, USA",
                        "ip_address": "192.168.1.1",
                        "last_activity": "2025-10-27T15:30:00Z",
                        "created_at": "2025-10-20T10:00:00Z",
                        "is_current": True,
                        "is_trusted": False,
                    },
                    {
                        "id": "223e4567-e89b-12d3-a456-426614174001",
                        "device_info": "Safari on iOS",
                        "location": "New York, USA",
                        "ip_address": None,
                        "last_activity": "2025-10-26T08:15:00Z",
                        "created_at": "2025-10-15T09:00:00Z",
                        "is_current": False,
                        "is_trusted": True,
                    },
                ],
                "total_count": 2,
            }
        }


class RevokeSessionResponse(BaseModel):
    """Response for DELETE /api/v1/auth/sessions/{session_id}."""

    message: str = Field(description="Success message")

    revoked_session_id: UUID = Field(description="ID of revoked session")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Session revoked successfully",
                "revoked_session_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        }


class BulkRevokeResponse(BaseModel):
    """Response for bulk session revocation operations."""

    message: str = Field(description="Success message")

    revoked_count: int = Field(description="Number of sessions revoked")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "All other sessions revoked successfully",
                "revoked_count": 3,
            }
        }
