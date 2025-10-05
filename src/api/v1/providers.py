"""Provider management API endpoints.

This module handles CRUD operations for provider instances (user's connections),
not provider types (catalog). Provider types are handled in provider_types.py.
"""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.api.dependencies import get_current_user
from src.api.v1.provider_authorization import router as authorization_router
from src.core.database import get_session
from src.models.provider import Provider, ProviderConnection
from src.models.user import User
from src.providers import ProviderRegistry
from src.schemas.provider import (
    CreateProviderRequest,
    ProviderResponse,
    UpdateProviderRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Include authorization sub-router for OAuth flow
router.include_router(authorization_router, prefix="", tags=["provider-authorization"])


@router.post("/", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider_instance(
    request: CreateProviderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new provider instance for the current user.

    This creates a provider instance that can then be connected
    through the OAuth flow.
    """
    # Validate provider exists and is configured
    if not ProviderRegistry.is_provider_available(request.provider_key):
        available = list(ProviderRegistry.get_available_providers().keys())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{request.provider_key}' not available. Choose from: {available}",
        )

    if not ProviderRegistry.is_provider_configured(request.provider_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{request.provider_key}' is not properly configured",
        )

    # Check if alias already exists for this user
    result = await session.execute(
        select(Provider).where(
            Provider.user_id == current_user.id, Provider.alias == request.alias
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have a provider named '{request.alias}'",
        )

    # Create provider instance
    provider = Provider(
        user_id=current_user.id, provider_key=request.provider_key, alias=request.alias
    )
    session.add(provider)

    # Create pending connection
    connection = ProviderConnection(provider_id=provider.id)
    session.add(connection)

    try:
        # Commit transaction at API layer
        await session.commit()
        await session.refresh(provider)

        logger.info(
            f"Created provider instance '{request.alias}' for user {current_user.email}"
        )
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create provider instance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create provider instance: {str(e)}",
        )

    return ProviderResponse(
        id=provider.id,
        provider_key=provider.provider_key,
        alias=provider.alias,
        status="pending",
        is_connected=False,
        needs_reconnection=True,
        connected_at=None,
        last_sync_at=None,
        accounts_count=0,
    )


@router.get("/", response_model=List[ProviderResponse])
async def list_user_providers(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get all provider instances for the current user."""
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(Provider)
        .options(selectinload(Provider.connection))
        .where(Provider.user_id == current_user.id)
    )
    providers = result.scalars().all()

    responses = []
    for provider in providers:
        connection = provider.connection

        responses.append(
            ProviderResponse(
                id=provider.id,
                provider_key=provider.provider_key,
                alias=provider.alias,
                status=connection.status.value if connection else "not_connected",
                is_connected=provider.is_connected,
                needs_reconnection=provider.needs_reconnection,
                connected_at=connection.connected_at.isoformat()
                if connection and connection.connected_at
                else None,
                last_sync_at=connection.last_sync_at.isoformat()
                if connection and connection.last_sync_at
                else None,
                accounts_count=connection.accounts_count if connection else 0,
            )
        )

    return responses


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get details of a specific provider instance."""
    from sqlmodel import select
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(Provider)
        .options(selectinload(Provider.connection))
        .where(Provider.id == provider_id)
    )
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found"
        )

    if provider.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this provider",
        )

    connection = provider.connection

    return ProviderResponse(
        id=provider.id,
        provider_key=provider.provider_key,
        alias=provider.alias,
        status=connection.status.value if connection else "not_connected",
        is_connected=provider.is_connected,
        needs_reconnection=provider.needs_reconnection,
        connected_at=connection.connected_at.isoformat()
        if connection and connection.connected_at
        else None,
        last_sync_at=connection.last_sync_at.isoformat()
        if connection and connection.last_sync_at
        else None,
        accounts_count=connection.accounts_count if connection else 0,
    )


@router.patch("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: UUID,
    request: UpdateProviderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProviderResponse:
    """Update a provider instance (partial update).

    Currently supports updating the alias (custom name) only.

    Args:
        provider_id: UUID of the provider instance to update.
        request: Update data (alias).
        current_user: Currently authenticated user.
        session: Database session.

    Returns:
        Updated provider instance.

    Raises:
        HTTPException: 404 if provider not found, 403 if no access,
                      409 if alias conflicts with existing provider.
    """
    from sqlalchemy.orm import selectinload

    # Get provider with connection
    result = await session.execute(
        select(Provider)
        .options(selectinload(Provider.connection))
        .where(Provider.id == provider_id)
    )
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found"
        )

    if provider.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this provider",
        )

    # Check if new alias conflicts with another provider
    if request.alias != provider.alias:
        result = await session.execute(
            select(Provider).where(
                Provider.user_id == current_user.id,
                Provider.alias == request.alias,
                Provider.id != provider_id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"You already have a provider named '{request.alias}'",
            )

        # Update alias
        old_alias = provider.alias
        provider.alias = request.alias

        try:
            await session.commit()
            await session.refresh(provider)

            logger.info(
                f"Updated provider alias from '{old_alias}' to '{request.alias}' "
                f"for user {current_user.email}"
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to update provider: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update provider: {str(e)}",
            )

    # Return updated provider
    connection = provider.connection

    return ProviderResponse(
        id=provider.id,
        provider_key=provider.provider_key,
        alias=provider.alias,
        status=connection.status.value if connection else "not_connected",
        is_connected=provider.is_connected,
        needs_reconnection=provider.needs_reconnection,
        connected_at=connection.connected_at.isoformat()
        if connection and connection.connected_at
        else None,
        last_sync_at=connection.last_sync_at.isoformat()
        if connection and connection.last_sync_at
        else None,
        accounts_count=connection.accounts_count if connection else 0,
    )


@router.delete("/{provider_id}")
async def delete_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a provider instance and all associated data."""
    from sqlmodel import select

    result = await session.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found"
        )

    if provider.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this provider",
        )

    # Delete provider (cascades to connection, token, audit logs)
    try:
        await session.delete(provider)
        # Commit transaction at API layer
        await session.commit()

        logger.info(
            f"Deleted provider '{provider.alias}' for user {current_user.email}"
        )

        return {"message": f"Provider '{provider.alias}' deleted successfully"}
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete provider: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete provider: {str(e)}",
        )
