"""Provider OAuth authorization endpoints.

This module handles the OAuth authorization flow for provider connections,
modeling authorization/connection as a sub-resource of providers.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.api.dependencies import get_current_user, get_token_service
from src.core.database import get_session
from src.models.provider import Provider
from src.models.user import User
from src.providers import ProviderRegistry
from src.schemas.common import MessageResponse
from src.schemas.provider import (
    AuthorizationCallbackResponse,
    AuthorizationInitiateResponse,
    AuthorizationStatusResponse,
)
from src.services.token_service import TokenService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/{provider_id}/authorization", response_model=AuthorizationInitiateResponse
)
async def initiate_authorization(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AuthorizationInitiateResponse:
    """Initiate OAuth authorization flow for a provider.

    Returns the authorization URL where the user should be redirected
    to authorize the provider connection.

    Args:
        provider_id: UUID of the provider instance to authorize.
        current_user: Currently authenticated user.
        session: Database session.

    Returns:
        Dictionary with auth_url, state, and message.

    Raises:
        HTTPException: 404 if provider not found, 403 if no access.
    """
    # Get provider
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

    # Get provider implementation
    try:
        provider_impl = ProviderRegistry.create_provider_instance(provider.provider_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Generate authorization URL
    # We use the provider_id as the state parameter for security
    auth_url = provider_impl.get_auth_url(state=str(provider_id))

    logger.info(f"Generated auth URL for provider {provider.alias}")

    return AuthorizationInitiateResponse(
        auth_url=auth_url,
        state=str(provider_id),
        message=f"Visit the auth_url to authorize {provider.alias}",
    )


@router.get("/{provider_id}/authorization", response_model=AuthorizationStatusResponse)
async def get_authorization_status(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    token_service: TokenService = Depends(get_token_service),
    session: AsyncSession = Depends(get_session),
) -> AuthorizationStatusResponse:
    """Get current authorization/connection status for a provider.

    Returns information about the stored tokens without exposing
    the actual token values.

    Args:
        provider_id: UUID of the provider instance.
        current_user: Currently authenticated user.
        token_service: Token service dependency.
        session: Database session.

    Returns:
        Dictionary with provider connection status and token info.

    Raises:
        HTTPException: 404 if provider not found, 403 if no access.
    """
    # Get provider
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
    token_info = await token_service.get_token_info(provider_id=provider.id)

    if not token_info:
        return AuthorizationStatusResponse(
            provider_id=provider.id,
            alias=provider.alias,
            status="not_connected",
            message="No tokens found. Please authorize the provider first.",
        )

    return AuthorizationStatusResponse(
        provider_id=provider.id,
        alias=provider.alias,
        status="connected",
        expires_at=token_info.get("expires_at"),
        has_refresh_token=token_info.get("has_refresh_token"),
        scope=token_info.get("scope"),
    )


@router.get(
    "/{provider_id}/authorization/callback",
    response_model=AuthorizationCallbackResponse,
)
async def handle_authorization_callback(
    provider_id: UUID,
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    token_service: TokenService = Depends(get_token_service),
    session: AsyncSession = Depends(get_session),
) -> AuthorizationCallbackResponse:
    """Handle OAuth callback from provider.

    This endpoint receives the authorization code from the provider
    and exchanges it for access tokens.

    Args:
        provider_id: UUID of the provider instance.
        code: Authorization code from provider.
        error: Error message if authorization failed.
        state: State parameter for CSRF protection.
        request: FastAPI request object for audit logging.
        current_user: Currently authenticated user.
        token_service: Token service dependency.
        session: Database session.

    Returns:
        Dictionary with success message and provider info.

    Raises:
        HTTPException: Various errors for invalid requests.
    """
    # Handle OAuth errors
    if error:
        logger.error(f"OAuth error for provider {provider_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authorization failed: {error}",
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No authorization code received",
        )

    # Validate state parameter matches provider_id
    if state and state != str(provider_id):
        logger.warning(f"State mismatch: expected {provider_id}, got {state}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State parameter mismatch - possible CSRF attempt",
        )

    # Get provider
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

    # Get provider implementation
    try:
        provider_impl = ProviderRegistry.create_provider_instance(provider.provider_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Exchange code for tokens
    try:
        tokens = await provider_impl.authenticate({"code": code})
    except Exception as e:
        logger.error(f"Failed to exchange code for tokens: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange authorization code: {str(e)}",
        )

    # Store tokens (service already injected via dependency)

    # Extract request info for audit log
    request_info = None
    if request:
        request_info = {
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }

    try:
        await token_service.store_initial_tokens(
            provider_id=provider.id,
            tokens=tokens,
            user_id=current_user.id,
            request_info=request_info,
        )
        # Commit transaction at API layer
        await session.commit()
    except Exception as e:
        logger.error(f"Failed to store tokens: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store tokens: {str(e)}",
        )

    logger.info(
        f"Successfully connected provider {provider.alias} for user {current_user.email}"
    )

    return AuthorizationCallbackResponse(
        message=f"Successfully connected {provider.alias}",
        provider_id=provider.id,
        alias=provider.alias,
        expires_in=tokens.get("expires_in"),
        scope=tokens.get("scope"),
    )


@router.patch("/{provider_id}/authorization", response_model=MessageResponse)
async def refresh_authorization(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    token_service: TokenService = Depends(get_token_service),
    session: AsyncSession = Depends(get_session),
):
    """Manually refresh tokens for a provider.

    Forces a token refresh even if the current token hasn't expired.

    Args:
        provider_id: UUID of the provider instance.
        current_user: Currently authenticated user.
        token_service: Token service dependency.
        session: Database session.

    Returns:
        Success message.

    Raises:
        HTTPException: 404 if provider not found, 403 if no access.
    """
    # Get provider
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

    try:
        await token_service.refresh_token(
            provider_id=provider.id, user_id=current_user.id
        )
        # Commit transaction at API layer
        await session.commit()
    except Exception as e:
        logger.error(f"Failed to refresh tokens: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh tokens: {str(e)}",
        )

    logger.info(f"Refreshed tokens for provider {provider.alias}")

    return MessageResponse(
        message=f"Tokens refreshed successfully for {provider.alias}"
    )


@router.delete("/{provider_id}/authorization", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_authorization(
    provider_id: UUID,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    token_service: TokenService = Depends(get_token_service),
    session: AsyncSession = Depends(get_session),
):
    """Revoke authorization and disconnect provider.

    Removes stored tokens but keeps the provider instance for
    potential reconnection.

    Args:
        provider_id: UUID of the provider instance.
        request: FastAPI request object for audit logging.
        current_user: Currently authenticated user.
        token_service: Token service dependency.
        session: Database session.

    Returns:
        None (204 No Content status).

    Raises:
        HTTPException: 404 if provider not found, 403 if no access.
    """
    # Get provider
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

    # Extract request info for audit log
    request_info = None
    if request:
        request_info = {
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }

    try:
        await token_service.revoke_tokens(
            provider_id=provider.id, user_id=current_user.id, request_info=request_info
        )
        # Commit transaction at API layer
        await session.commit()
    except Exception as e:
        logger.error(f"Failed to revoke tokens: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect provider: {str(e)}",
        )

    logger.info(f"Disconnected provider {provider.alias} for user {current_user.email}")

    # No return body with 204
