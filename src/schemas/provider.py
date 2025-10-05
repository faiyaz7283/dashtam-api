"""Provider management Pydantic schemas.

This module contains request/response schemas for provider-related endpoints,
including provider types, instances, connections, and status.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProviderTypeInfo(BaseModel):
    """Information about an available provider type.

    Represents metadata about a financial institution provider that can
    be connected (e.g., Charles Schwab, Fidelity, etc.).

    Attributes:
        key: Unique identifier for this provider type (e.g., 'schwab').
        name: Display name of the provider.
        provider_type: Category of provider (brokerage, bank, etc.).
        description: Human-readable description of the provider.
        icon_url: Optional URL to provider's icon/logo.
        is_configured: Whether provider has required credentials configured.
        supported_features: List of features this provider supports.
    """

    key: str = Field(..., description="Unique provider identifier")
    name: str = Field(..., description="Display name of the provider")
    provider_type: str = Field(..., description="Category of provider")
    description: str = Field(default="", description="Provider description")
    icon_url: Optional[str] = Field(default=None, description="URL to provider icon")
    is_configured: bool = Field(
        ..., description="Whether provider credentials are configured"
    )
    supported_features: List[str] = Field(
        default_factory=list, description="Features this provider supports"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "key": "schwab",
                "name": "Charles Schwab",
                "provider_type": "brokerage",
                "description": "Charles Schwab brokerage accounts",
                "icon_url": "https://example.com/schwab-icon.png",
                "is_configured": True,
                "supported_features": ["accounts", "transactions", "positions"],
            }
        }
    }


class CreateProviderRequest(BaseModel):
    """Request to create a new provider instance.

    Used when a user wants to connect a new financial institution.

    Attributes:
        provider_key: Type of provider to connect (e.g., 'schwab').
        alias: User's custom name for this connection (e.g., 'My Schwab Account').
    """

    provider_key: str = Field(
        ...,
        description="Provider type key (e.g., 'schwab')",
        min_length=1,
        max_length=50,
    )
    alias: str = Field(
        ...,
        description="User's custom name for this connection",
        min_length=1,
        max_length=100,
    )

    model_config = {
        "json_schema_extra": {
            "example": {"provider_key": "schwab", "alias": "My Schwab Brokerage"}
        }
    }


class ProviderResponse(BaseModel):
    """Response for a provider instance.

    Represents a user's connected financial institution with current status.

    Attributes:
        id: Unique identifier for this provider instance.
        provider_key: Type of provider (e.g., 'schwab').
        alias: User's custom name for this connection.
        status: Current connection status (pending, connected, error, etc.).
        is_connected: Whether provider is currently connected.
        needs_reconnection: Whether provider needs re-authorization.
        connected_at: ISO timestamp when first connected.
        last_sync_at: ISO timestamp of last data sync.
        accounts_count: Number of accounts linked to this provider.
    """

    id: UUID = Field(..., description="Unique provider instance ID")
    provider_key: str = Field(..., description="Provider type key")
    alias: str = Field(..., description="User's custom name")
    status: str = Field(..., description="Current connection status")
    is_connected: bool = Field(..., description="Whether currently connected")
    needs_reconnection: bool = Field(..., description="Whether needs re-auth")
    connected_at: Optional[str] = Field(
        default=None, description="ISO timestamp of first connection"
    )
    last_sync_at: Optional[str] = Field(
        default=None, description="ISO timestamp of last sync"
    )
    accounts_count: int = Field(default=0, description="Number of linked accounts")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "provider_key": "schwab",
                "alias": "My Schwab Brokerage",
                "status": "connected",
                "is_connected": True,
                "needs_reconnection": False,
                "connected_at": "2025-10-04T20:00:00Z",
                "last_sync_at": "2025-10-04T20:30:00Z",
                "accounts_count": 3,
            }
        }
    }


class AuthorizationInitiateResponse(BaseModel):
    """Response when initiating OAuth authorization flow.

    Contains the authorization URL where the user should be redirected
    to authorize the provider connection.

    Attributes:
        auth_url: URL to redirect user for OAuth authorization.
        state: State parameter for CSRF protection (matches provider_id).
        message: Instructions for the user.
    """

    auth_url: str = Field(..., description="OAuth authorization URL")
    state: str = Field(..., description="State parameter for CSRF protection")
    message: str = Field(..., description="Instructions for authorization")

    model_config = {
        "json_schema_extra": {
            "example": {
                "auth_url": "https://api.schwabapi.com/v1/oauth/authorize?client_id=...",
                "state": "123e4567-e89b-12d3-a456-426614174000",
                "message": "Visit the auth_url to authorize My Schwab Account",
            }
        }
    }


class AuthorizationStatusResponse(BaseModel):
    """Response containing authorization/connection status.

    Returns information about stored tokens without exposing actual token values.

    Attributes:
        provider_id: UUID of the provider instance.
        alias: User's custom name for this provider.
        status: Connection status (connected, not_connected).
        message: Additional status information.
        expires_at: ISO timestamp when access token expires (if connected).
        has_refresh_token: Whether a refresh token is available (if connected).
        scope: OAuth scopes granted (if connected).
    """

    provider_id: UUID = Field(..., description="Provider instance ID")
    alias: str = Field(..., description="Provider alias")
    status: str = Field(..., description="Connection status")
    message: Optional[str] = Field(default=None, description="Status message")
    expires_at: Optional[datetime] = Field(
        default=None, description="Token expiration timestamp"
    )
    has_refresh_token: Optional[bool] = Field(
        default=None, description="Whether refresh token available"
    )
    scope: Optional[str] = Field(default=None, description="OAuth scopes granted")

    model_config = {
        "json_schema_extra": {
            "example": {
                "provider_id": "123e4567-e89b-12d3-a456-426614174000",
                "alias": "My Schwab Account",
                "status": "connected",
                "expires_at": "2025-10-04T21:00:00Z",
                "has_refresh_token": True,
                "scope": "read write",
            }
        }
    }


class AuthorizationCallbackResponse(BaseModel):
    """Response after successful OAuth callback.

    Returned after the authorization code has been exchanged for tokens.

    Attributes:
        message: Success message.
        provider_id: UUID of the provider instance.
        alias: User's custom name for this provider.
        expires_in: Seconds until access token expires.
        scope: OAuth scopes granted.
    """

    message: str = Field(..., description="Success message")
    provider_id: UUID = Field(..., description="Provider instance ID")
    alias: str = Field(..., description="Provider alias")
    expires_in: Optional[int] = Field(
        default=None, description="Token expiration in seconds"
    )
    scope: Optional[str] = Field(default=None, description="OAuth scopes granted")

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Successfully connected My Schwab Account",
                "provider_id": "123e4567-e89b-12d3-a456-426614174000",
                "alias": "My Schwab Account",
                "expires_in": 1800,
                "scope": "read write",
            }
        }
    }
