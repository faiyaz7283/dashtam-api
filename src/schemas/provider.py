"""Provider management Pydantic schemas.

This module contains request/response schemas for provider-related endpoints,
including provider types, instances, connections, and status.
"""

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
