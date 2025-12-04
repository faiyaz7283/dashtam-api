"""Provider request and response schemas.

Pydantic schemas for provider API endpoints. Includes:
- Request schemas (client → API)
- Response schemas (API → client)
- DTO-to-schema conversion methods

Reference:
    - docs/architecture/api-design-patterns.md
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.application.queries.handlers.get_provider_handler import (
    ProviderConnectionResult,
)
from src.application.queries.handlers.list_providers_handler import (
    ProviderConnectionListResult,
)


# =============================================================================
# Response Schemas
# =============================================================================


class ProviderConnectionResponse(BaseModel):
    """Single provider connection response.

    Attributes:
        id: Connection unique identifier.
        provider_slug: Provider identifier (e.g., "schwab").
        alias: User-defined nickname (if set).
        status: Current connection status.
        is_connected: Whether connection is usable for API calls.
        needs_reauthentication: Whether user needs to re-authenticate.
        connected_at: When connection was established.
        last_sync_at: Last successful data sync.
        created_at: Record creation timestamp.
        updated_at: Last modification timestamp.
    """

    id: UUID = Field(..., description="Connection unique identifier")
    provider_slug: str = Field(
        ..., description="Provider identifier", examples=["schwab"]
    )
    alias: str | None = Field(None, description="User-defined nickname")
    status: str = Field(..., description="Connection status")
    is_connected: bool = Field(..., description="Whether connection is usable")
    needs_reauthentication: bool = Field(
        ..., description="Whether re-authentication is needed"
    )
    connected_at: datetime | None = Field(None, description="When connected")
    last_sync_at: datetime | None = Field(None, description="Last sync timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    @classmethod
    def from_dto(cls, dto: ProviderConnectionResult) -> "ProviderConnectionResponse":
        """Convert application DTO to response schema.

        Args:
            dto: ProviderConnectionResult from handler.

        Returns:
            ProviderConnectionResponse for API response.
        """
        return cls(
            id=dto.id,
            provider_slug=dto.provider_slug,
            alias=dto.alias,
            status=dto.status.value,
            is_connected=dto.is_connected,
            needs_reauthentication=dto.needs_reauthentication,
            connected_at=dto.connected_at,
            last_sync_at=dto.last_sync_at,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class ProviderConnectionListResponse(BaseModel):
    """Provider connection list response.

    Attributes:
        connections: List of provider connections.
        total_count: Total number of connections.
        active_count: Number of active (usable) connections.
    """

    connections: list[ProviderConnectionResponse] = Field(
        ..., description="List of connections"
    )
    total_count: int = Field(..., description="Total connection count")
    active_count: int = Field(..., description="Active connection count")

    @classmethod
    def from_dto(
        cls, dto: ProviderConnectionListResult
    ) -> "ProviderConnectionListResponse":
        """Convert application DTO to response schema.

        Args:
            dto: ProviderConnectionListResult from handler.

        Returns:
            ProviderConnectionListResponse for API response.
        """
        return cls(
            connections=[
                ProviderConnectionResponse.from_dto(conn) for conn in dto.connections
            ],
            total_count=dto.total_count,
            active_count=dto.active_count,
        )


class AuthorizationUrlResponse(BaseModel):
    """Response with OAuth authorization URL.

    Attributes:
        authorization_url: URL to redirect user for OAuth consent.
        state: State parameter for CSRF protection (stored in cache).
        expires_in: Seconds until state expires.
    """

    authorization_url: str = Field(..., description="OAuth consent URL")
    state: str = Field(..., description="CSRF state token")
    expires_in: int = Field(600, description="State expiration in seconds")


class TokenRefreshResponse(BaseModel):
    """Response for token refresh operation.

    Attributes:
        success: Whether refresh succeeded.
        message: Human-readable result message.
        expires_at: New token expiration time (if success).
    """

    success: bool = Field(..., description="Whether refresh succeeded")
    message: str = Field(..., description="Result message")
    expires_at: datetime | None = Field(None, description="New token expiration")


# =============================================================================
# Request Schemas
# =============================================================================


class ConnectProviderRequest(BaseModel):
    """Request to initiate provider connection.

    Attributes:
        provider_slug: Provider to connect (e.g., "schwab").
        alias: Optional user-defined nickname for the connection.
        redirect_uri: Optional custom redirect URI (uses default if not provided).
    """

    provider_slug: str = Field(
        ...,
        description="Provider identifier",
        examples=["schwab"],
        min_length=1,
        max_length=50,
    )
    alias: str | None = Field(
        None,
        description="User-defined nickname",
        max_length=100,
    )
    redirect_uri: str | None = Field(
        None,
        description="Custom OAuth redirect URI",
    )


class RefreshProviderTokensRequest(BaseModel):
    """Request to refresh provider tokens.

    Attributes:
        force: Force refresh even if token hasn't expired.
    """

    force: bool = Field(False, description="Force refresh even if not expired")


class UpdateProviderConnectionRequest(BaseModel):
    """Request to update provider connection.

    Attributes:
        alias: New nickname for the connection.
    """

    alias: str | None = Field(
        None,
        description="New nickname (null to remove)",
        max_length=100,
    )
