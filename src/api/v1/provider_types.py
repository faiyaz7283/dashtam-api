"""Provider type catalog API endpoints.

This module handles provider type information (catalog of available providers),
separate from provider instances (user's connections).
"""

from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Optional

from src.schemas.provider import ProviderTypeInfo


router = APIRouter()


@router.get("/", response_model=List[ProviderTypeInfo])
async def list_provider_types(
    configured: Optional[bool] = Query(
        None, description="Filter by configuration status"
    ),
):
    """Get list of available provider types.

    This endpoint returns the catalog of provider types that can be connected.
    Provider types are templates/definitions, not user instances.

    Args:
        configured: If true, only return configured providers.
                   If false, only return unconfigured providers.
                   If None, return all providers.

    Returns:
        List of provider type information.
    """
    from src.providers import ProviderRegistry

    if configured is True:
        providers = ProviderRegistry.get_configured_providers()
    elif configured is False:
        # Get all providers and filter for unconfigured
        all_providers = ProviderRegistry.get_available_providers()
        providers = {
            key: info
            for key, info in all_providers.items()
            if not info["is_configured"]
        }
    else:
        providers = ProviderRegistry.get_available_providers()

    return [
        ProviderTypeInfo(
            key=key,
            name=info["name"],
            provider_type=info["provider_type"],
            description=info.get("description", ""),
            icon_url=info.get("icon_url"),
            is_configured=info.get("is_configured", False),
            supported_features=info.get("supported_features", []),
        )
        for key, info in providers.items()
    ]


@router.get("/{provider_key}", response_model=ProviderTypeInfo)
async def get_provider_type(provider_key: str):
    """Get details of a specific provider type.

    Args:
        provider_key: The unique key for the provider type (e.g., 'schwab').

    Returns:
        Provider type information.

    Raises:
        HTTPException: 404 if provider type not found.
    """
    from src.providers import ProviderRegistry

    providers = ProviderRegistry.get_available_providers()

    if provider_key not in providers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider type '{provider_key}' not found",
        )

    info = providers[provider_key]
    return ProviderTypeInfo(
        key=provider_key,
        name=info["name"],
        provider_type=info["provider_type"],
        description=info.get("description", ""),
        icon_url=info.get("icon_url"),
        is_configured=info.get("is_configured", False),
        supported_features=info.get("supported_features", []),
    )
