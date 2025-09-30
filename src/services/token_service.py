"""Token management service for OAuth token lifecycle.

This service handles all token-related operations including:
- Storing new tokens (with encryption)
- Retrieving tokens (with automatic refresh)
- Refreshing expired tokens
- Token rotation handling
- Audit logging of token operations

The service acts as the bridge between providers and the database,
ensuring tokens are always valid and properly encrypted.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.provider import (
    Provider,
    ProviderAuditLog,
    ProviderConnection,
    ProviderStatus,
    ProviderToken,
)
from src.providers import ProviderRegistry
from src.services.encryption import get_encryption_service

logger = logging.getLogger(__name__)


class TokenService:
    """Service for managing OAuth tokens throughout their lifecycle.

    This service provides a high-level interface for token operations,
    handling encryption, refresh logic, and audit logging automatically.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the token service.

        Args:
            session: Database session for operations.
        """
        self.session = session
        self.encryption = get_encryption_service()

    async def store_initial_tokens(
        self,
        provider_id: UUID,
        tokens: Dict[str, Any],
        user_id: UUID,
        request_info: Optional[Dict[str, str]] = None,
    ) -> ProviderToken:
        """Store initial tokens after successful OAuth authentication.

        This method is called after the OAuth callback to store the initial
        tokens received from the provider.

        Args:
            provider_id: The provider instance ID.
            tokens: Token response from provider containing:
                - access_token: The access token
                - refresh_token: Optional refresh token
                - expires_in: Token lifetime in seconds
                - id_token: Optional JWT ID token
                - scope: Optional granted scopes
            user_id: User who authorized the connection.
            request_info: Optional request metadata (IP, user agent).

        Returns:
            The created ProviderToken instance.

        Raises:
            ValueError: If provider or connection not found.
        """
        # Get provider and connection
        from sqlalchemy.orm import selectinload
        from sqlmodel import select

        # Load provider with connection and token relationships
        result = await self.session.execute(
            select(Provider)
            .options(
                selectinload(Provider.connection).selectinload(ProviderConnection.token)
            )
            .where(Provider.id == provider_id)
        )
        provider = result.scalar_one_or_none()
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")

        if not provider.connection:
            # Create connection if it doesn't exist
            connection = ProviderConnection(
                provider_id=provider_id, status=ProviderStatus.PENDING
            )
            self.session.add(connection)
            await self.session.flush()
        else:
            connection = provider.connection

        # Check if token already exists
        existing_token = connection.token if connection else None

        # Encrypt tokens
        encrypted_access = self.encryption.encrypt(tokens["access_token"])
        encrypted_refresh = None
        if tokens.get("refresh_token"):
            encrypted_refresh = self.encryption.encrypt(tokens["refresh_token"])

        # Calculate expiration
        expires_at = None
        if tokens.get("expires_in"):
            expires_at = datetime.utcnow() + timedelta(
                seconds=int(tokens["expires_in"])
            )

        if existing_token:
            # Update existing token
            existing_token.access_token_encrypted = encrypted_access
            if encrypted_refresh:
                existing_token.refresh_token_encrypted = encrypted_refresh
            existing_token.expires_at = expires_at
            existing_token.id_token = tokens.get("id_token")
            existing_token.scope = tokens.get("scope")
            existing_token.updated_at = datetime.utcnow()
            token = existing_token
            action = "token_updated"
        else:
            # Create new token
            token = ProviderToken(
                connection_id=connection.id,
                access_token_encrypted=encrypted_access,
                refresh_token_encrypted=encrypted_refresh,
                expires_at=expires_at,
                id_token=tokens.get("id_token"),
                token_type=tokens.get("token_type", "Bearer"),
                scope=tokens.get("scope"),
            )
            self.session.add(token)
            action = "token_created"

        # Update connection status
        connection.mark_connected()

        # Create audit log
        audit_log = ProviderAuditLog(
            connection_id=connection.id,
            user_id=user_id,
            action=action,
            details={
                "provider_key": provider.provider_key,
                "alias": provider.alias,
                "has_refresh_token": bool(encrypted_refresh),
                "expires_in": tokens.get("expires_in"),
                "scope": tokens.get("scope"),
            },
            ip_address=request_info.get("ip_address") if request_info else None,
            user_agent=request_info.get("user_agent") if request_info else None,
        )
        self.session.add(audit_log)

        await self.session.commit()
        logger.info(f"Stored tokens for provider {provider.alias} (ID: {provider_id})")

        return token

    async def get_valid_access_token(self, provider_id: UUID, user_id: UUID) -> str:
        """Get a valid access token for a provider, refreshing if necessary.

        This is the main method used by providers to get tokens. It handles:
        - Decryption of stored tokens
        - Checking expiration
        - Automatic refresh if expired or expiring soon
        - Audit logging

        Args:
            provider_id: The provider instance ID.
            user_id: The user requesting the token.

        Returns:
            Valid decrypted access token.

        Raises:
            ValueError: If provider, connection, or token not found.
            Exception: If token refresh fails.
        """
        # Get provider with connection and token
        from sqlalchemy.orm import selectinload
        from sqlmodel import select

        result = await self.session.execute(
            select(Provider)
            .options(
                selectinload(Provider.connection).selectinload(ProviderConnection.token)
            )
            .where(Provider.id == provider_id)
        )
        provider = result.scalar_one_or_none()
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")

        if not provider.connection:
            raise ValueError(f"Provider {provider.alias} is not connected")

        connection = provider.connection
        if not connection.token:
            raise ValueError(f"No tokens found for provider {provider.alias}")

        token = connection.token

        # Check if token needs refresh
        if token.needs_refresh:
            logger.info(f"Token for {provider.alias} needs refresh")
            token = await self.refresh_token(provider_id, user_id)

        # Decrypt and return access token
        access_token = self.encryption.decrypt(token.access_token_encrypted)
        return access_token

    async def refresh_token(self, provider_id: UUID, user_id: UUID) -> ProviderToken:
        """Refresh an expired or expiring access token.

        Uses the refresh token to obtain a new access token from the provider.
        Handles token rotation if the provider sends a new refresh token.

        Args:
            provider_id: The provider instance ID.
            user_id: The user requesting the refresh.

        Returns:
            Updated ProviderToken instance.

        Raises:
            ValueError: If no refresh token available.
            Exception: If refresh fails.
        """
        # Get provider and token
        from sqlalchemy.orm import selectinload
        from sqlmodel import select

        result = await self.session.execute(
            select(Provider)
            .options(
                selectinload(Provider.connection).selectinload(ProviderConnection.token)
            )
            .where(Provider.id == provider_id)
        )
        provider = result.scalar_one_or_none()
        if not provider or not provider.connection or not provider.connection.token:
            raise ValueError(f"Invalid provider state for {provider_id}")

        connection = provider.connection
        token = connection.token

        # Check if we have a refresh token
        if not token.refresh_token_encrypted:
            raise ValueError(f"No refresh token available for {provider.alias}")

        # Decrypt refresh token
        refresh_token = self.encryption.decrypt(token.refresh_token_encrypted)

        # Get provider implementation
        provider_impl = ProviderRegistry.create_provider_instance(provider.provider_key)

        try:
            # Call provider's refresh method
            new_tokens = await provider_impl.refresh_authentication(refresh_token)

            # Encrypt new tokens
            encrypted_access = self.encryption.encrypt(new_tokens["access_token"])

            # Handle token rotation - update refresh token if provider sends new one
            encrypted_refresh = (
                token.refresh_token_encrypted
            )  # Keep existing by default
            if (
                new_tokens.get("refresh_token")
                and new_tokens["refresh_token"] != refresh_token
            ):
                # Provider rotated the refresh token
                encrypted_refresh = self.encryption.encrypt(new_tokens["refresh_token"])
                logger.info(f"Refresh token rotated for {provider.alias}")

            # Update token
            token.update_tokens(
                access_token_encrypted=encrypted_access,
                refresh_token_encrypted=encrypted_refresh,
                expires_in=new_tokens.get("expires_in"),
                id_token=new_tokens.get("id_token"),
            )

            # Update connection status
            connection.status = ProviderStatus.ACTIVE
            connection.error_count = 0
            connection.error_message = None

            # Create audit log
            audit_log = ProviderAuditLog(
                connection_id=connection.id,
                user_id=user_id,
                action="token_refreshed",
                details={
                    "provider_key": provider.provider_key,
                    "alias": provider.alias,
                    "refresh_count": token.refresh_count,
                    "token_rotated": new_tokens.get("refresh_token") is not None,
                },
            )
            self.session.add(audit_log)

            await self.session.commit()
            logger.info(
                f"Refreshed token for {provider.alias} (refresh #{token.refresh_count})"
            )

            return token

        except Exception as e:
            # Log refresh failure
            error_message = str(e)
            connection.error_count += 1
            connection.error_message = f"Token refresh failed: {error_message}"

            if connection.error_count >= 3:
                connection.status = ProviderStatus.ERROR

            # Create audit log for failure
            audit_log = ProviderAuditLog(
                connection_id=connection.id,
                user_id=user_id,
                action="token_refresh_failed",
                details={
                    "provider_key": provider.provider_key,
                    "alias": provider.alias,
                    "error": error_message,
                    "error_count": connection.error_count,
                },
            )
            self.session.add(audit_log)

            await self.session.commit()

            logger.error(
                f"Failed to refresh token for {provider.alias}: {error_message}"
            )
            raise Exception(
                f"Token refresh failed for {provider.alias}: {error_message}"
            ) from e

    async def revoke_tokens(
        self,
        provider_id: UUID,
        user_id: UUID,
        request_info: Optional[Dict[str, str]] = None,
    ) -> None:
        """Revoke tokens and disconnect a provider.

        This removes the stored tokens and marks the connection as revoked.
        The provider instance itself is preserved for potential reconnection.

        Args:
            provider_id: The provider instance ID.
            user_id: The user revoking the connection.
            request_info: Optional request metadata.
        """
        # Get provider
        from sqlalchemy.orm import selectinload
        from sqlmodel import select

        result = await self.session.execute(
            select(Provider)
            .options(
                selectinload(Provider.connection).selectinload(ProviderConnection.token)
            )
            .where(Provider.id == provider_id)
        )
        provider = result.scalar_one_or_none()
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")

        if provider.connection:
            connection = provider.connection

            # Delete token if exists
            if connection.token:
                await self.session.delete(connection.token)

            # Update connection status
            connection.status = ProviderStatus.REVOKED
            connection.error_message = "Connection revoked by user"

            # Create audit log
            audit_log = ProviderAuditLog(
                connection_id=connection.id,
                user_id=user_id,
                action="connection_revoked",
                details={
                    "provider_key": provider.provider_key,
                    "alias": provider.alias,
                },
                ip_address=request_info.get("ip_address") if request_info else None,
                user_agent=request_info.get("user_agent") if request_info else None,
            )
            self.session.add(audit_log)

            await self.session.commit()
            logger.info(f"Revoked tokens for provider {provider.alias}")

    async def get_token_info(self, provider_id: UUID) -> Optional[Dict[str, Any]]:
        """Get information about stored tokens without decrypting.

        Useful for checking token status without exposing sensitive data.

        Args:
            provider_id: The provider instance ID.

        Returns:
            Dictionary with token metadata, or None if no tokens.
        """
        from sqlalchemy.orm import selectinload
        from sqlmodel import select

        result = await self.session.execute(
            select(Provider)
            .options(
                selectinload(Provider.connection).selectinload(ProviderConnection.token)
            )
            .where(Provider.id == provider_id)
        )
        provider = result.scalar_one_or_none()
        if not provider or not provider.connection or not provider.connection.token:
            return None

        token = provider.connection.token

        return {
            "has_access_token": bool(token.access_token_encrypted),
            "has_refresh_token": bool(token.refresh_token_encrypted),
            "has_id_token": bool(token.id_token),
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
            "is_expired": token.is_expired,
            "is_expiring_soon": token.is_expiring_soon,
            "needs_refresh": token.needs_refresh,
            "refresh_count": token.refresh_count,
            "last_refreshed_at": token.last_refreshed_at.isoformat()
            if token.last_refreshed_at
            else None,
            "scope": token.scope,
        }


# Convenience function for creating service instances
async def get_token_service(session: AsyncSession) -> TokenService:
    """Create a token service instance with the given session.

    Args:
        session: Database session to use.

    Returns:
        TokenService instance.
    """
    return TokenService(session)
