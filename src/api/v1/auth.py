"""OAuth authentication flow API endpoints.

This module handles the OAuth flow for connecting providers,
including authorization URL generation, callback handling,
and token management.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.database import get_session
from src.models.user import User
from src.models.provider import Provider
from src.providers import ProviderRegistry
from src.services.token_service import TokenService

logger = logging.getLogger(__name__)

router = APIRouter()


# For now, we'll use a simple mock authentication
# In production, this should be replaced with proper JWT-based auth
async def get_current_user(session: AsyncSession = Depends(get_session)) -> User:
    """Get the current authenticated user.

    For development, this creates/returns a test user.
    In production, this should validate JWT tokens.
    """
    # For development: Get or create test user
    result = await session.execute(select(User).where(User.email == "test@example.com"))
    user = result.scalar_one_or_none()

    if not user:
        user = User(email="test@example.com", name="Test User", is_verified=True)
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return user


@router.get("/{provider_id}/authorize")
async def get_authorization_url(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get the OAuth authorization URL for a provider.

    Returns the URL where the user should be redirected to
    authorize the provider connection.
    """
    # Get provider
    from sqlmodel import select
    result = await session.execute(
        select(Provider).where(Provider.id == provider_id)
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

    # Get provider implementation
    try:
        provider_impl = ProviderRegistry.create_provider_instance(provider.provider_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Generate authorization URL
    # We use the provider_id as the state parameter for security
    auth_url = provider_impl.get_auth_url(state=str(provider_id))

    logger.info(f"Generated auth URL for provider {provider.alias}")

    return {
        "auth_url": auth_url,
        "message": f"Visit this URL to authorize {provider.alias}",
    }


@router.get("/{provider_id}/authorize/redirect")
async def redirect_to_authorization(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Redirect to the OAuth authorization page.

    This endpoint directly redirects the user to the provider's
    authorization page instead of returning the URL.
    """
    # Get authorization URL
    result = await get_authorization_url(provider_id, current_user, session)

    # Redirect to authorization page
    return RedirectResponse(url=result["auth_url"])


@router.get("/{provider_id}/callback")
async def handle_oauth_callback(
    provider_id: UUID,
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Handle OAuth callback from provider.

    This endpoint receives the authorization code from the provider
    and exchanges it for access tokens.
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

    # Get provider
    from sqlmodel import select
    result = await session.execute(
        select(Provider).where(Provider.id == provider_id)
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

    # Store tokens
    token_service = TokenService(session)

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
    except Exception as e:
        logger.error(f"Failed to store tokens: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store tokens: {str(e)}",
        )

    logger.info(
        f"Successfully connected provider {provider.alias} for user {current_user.email}"
    )

    return {
        "message": f"Successfully connected {provider.alias}!",
        "provider_id": provider.id,
        "alias": provider.alias,
        "expires_in": tokens.get("expires_in"),
        "scope": tokens.get("scope"),
    }


@router.post("/{provider_id}/refresh")
async def refresh_provider_tokens(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Manually refresh tokens for a provider.

    This endpoint forces a token refresh even if the current
    token hasn't expired yet.
    """
    # Get provider
    from sqlmodel import select
    result = await session.execute(
        select(Provider).where(Provider.id == provider_id)
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

    # Refresh tokens
    token_service = TokenService(session)

    try:
        await token_service.refresh_token(
            provider_id=provider.id, user_id=current_user.id
        )
    except Exception as e:
        logger.error(f"Failed to refresh tokens: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh tokens: {str(e)}",
        )

    logger.info(f"Refreshed tokens for provider {provider.alias}")

    return {"message": f"Tokens refreshed successfully for {provider.alias}"}


@router.get("/{provider_id}/status")
async def get_token_status(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get the current token status for a provider.

    Returns information about the stored tokens without
    exposing the actual token values.
    """
    # Get provider
    from sqlmodel import select
    result = await session.execute(
        select(Provider).where(Provider.id == provider_id)
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

    # Get token info
    token_service = TokenService(session)
    token_info = await token_service.get_token_info(provider_id=provider.id)

    if not token_info:
        return {
            "provider_id": provider.id,
            "alias": provider.alias,
            "status": "not_connected",
            "message": "No tokens found. Please authorize the provider first.",
        }

    return {
        "provider_id": provider.id,
        "alias": provider.alias,
        "status": "connected",
        **token_info,
    }


@router.delete("/{provider_id}/disconnect")
async def disconnect_provider(
    provider_id: UUID,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Disconnect a provider by revoking its tokens.

    This removes the stored tokens but keeps the provider
    instance for potential reconnection.
    """
    # Get provider
    from sqlmodel import select
    result = await session.execute(
        select(Provider).where(Provider.id == provider_id)
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

    # Revoke tokens
    token_service = TokenService(session)

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
    except Exception as e:
        logger.error(f"Failed to revoke tokens: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect provider: {str(e)}",
        )

    logger.info(f"Disconnected provider {provider.alias} for user {current_user.email}")

    return {"message": f"Successfully disconnected {provider.alias}"}
