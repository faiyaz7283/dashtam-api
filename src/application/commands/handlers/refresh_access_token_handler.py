"""Refresh Access Token handler for User Authentication.

Flow:
1. Emit AuthTokenRefreshAttempted event
2. Verify refresh token format
3. Look up all refresh tokens for user and verify against provided token
4. Verify token not expired
5. Verify token not revoked
6. Get user from database
7. Verify user exists and is active
8. Generate new JWT access token
9. Implement token rotation (delete old, save new)
10. Emit AuthTokenRefreshSucceeded event
11. Return Success(tokens)

On failure:
- Emit AuthTokenRefreshFailed event
- Return Failure(error)

Architecture:
- Application layer ONLY imports from domain layer (entities, protocols, events)
- NO infrastructure imports (repositories are injected via protocols)
- Handler orchestrates business logic without knowing persistence details
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID
from uuid_extensions import uuid7

from src.application.commands.auth_commands import RefreshAccessToken
from src.core.result import Failure, Result, Success
from src.domain.events.auth_events import (
    AuthTokenRefreshAttempted,
    AuthTokenRefreshFailed,
    AuthTokenRefreshSucceeded,
    TokenRejectedDueToRotation,
)
from src.domain.protocols import (
    RefreshTokenData,
    RefreshTokenRepository,
    RefreshTokenServiceProtocol,
    SecurityConfigRepository,
    TokenGenerationProtocol,
    UserRepository,
)
from src.domain.protocols.event_bus_protocol import EventBusProtocol


class RefreshError:
    """Refresh-specific error reasons."""

    TOKEN_INVALID = "token_invalid"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_REVOKED = "token_revoked"
    TOKEN_VERSION_REJECTED = "token_version_rejected"
    USER_NOT_FOUND = "user_not_found"
    USER_INACTIVE = "user_inactive"


@dataclass
class RefreshResponse:
    """Response data for successful token refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes in seconds


class RefreshAccessTokenHandler:
    """Handler for refresh access token command.

    Implements token rotation security pattern:
    - On each refresh, the old refresh token is deleted
    - A new refresh token is generated and saved
    - This prevents token reuse attacks

    Follows hexagonal architecture:
    - Application layer (this handler)
    - Domain layer (User entity, protocols)
    - Infrastructure layer (repositories, services via dependency injection)
    """

    def __init__(
        self,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        security_config_repo: SecurityConfigRepository,
        token_service: TokenGenerationProtocol,
        refresh_token_service: RefreshTokenServiceProtocol,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize refresh handler with dependencies.

        Args:
            user_repo: User repository for persistence.
            refresh_token_repo: Refresh token repository for persistence.
            security_config_repo: Security config repository for version check.
            token_service: JWT token generation service.
            refresh_token_service: Refresh token generation/verification service.
            event_bus: Event bus for publishing domain events.
        """
        self._user_repo = user_repo
        self._refresh_token_repo = refresh_token_repo
        self._security_config_repo = security_config_repo
        self._token_service = token_service
        self._refresh_token_service = refresh_token_service
        self._event_bus = event_bus

    async def handle(self, cmd: RefreshAccessToken) -> Result[RefreshResponse, str]:
        """Handle refresh access token command.

        Args:
            cmd: RefreshAccessToken command (token validated by Annotated type).

        Returns:
            Success(RefreshResponse) on successful refresh.
            Failure(error_message) on failure.

        Side Effects:
            - Publishes AuthTokenRefreshAttempted event (always).
            - Publishes AuthTokenRefreshSucceeded event (on success).
            - Publishes AuthTokenRefreshFailed event (on failure).
            - Deletes old RefreshToken from database (rotation).
            - Creates new RefreshToken in database.
        """
        # Step 1: Emit ATTEMPTED event
        await self._event_bus.publish(
            AuthTokenRefreshAttempted(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                user_id=None,  # Unknown until we verify token
            )
        )

        # Step 2-3: Look up token by iterating through database tokens
        # Note: We hash the provided token and compare against stored hashes
        # Since bcrypt hashes are non-deterministic, we need to verify each stored hash

        # First, we need to find the token record
        # The refresh_token_service can verify token against hash
        token_data = await self._find_valid_refresh_token(cmd.refresh_token)

        if token_data is None:
            await self._publish_failed_event(
                user_id=None,
                reason=RefreshError.TOKEN_INVALID,
            )
            return Failure(error=RefreshError.TOKEN_INVALID)

        # Step 4: Verify token not expired
        if token_data.expires_at < datetime.now(UTC):
            await self._publish_failed_event(
                user_id=token_data.user_id,
                reason=RefreshError.TOKEN_EXPIRED,
            )
            return Failure(error=RefreshError.TOKEN_EXPIRED)

        # Step 5: Verify token not revoked
        if token_data.revoked_at is not None:
            await self._publish_failed_event(
                user_id=token_data.user_id,
                reason=RefreshError.TOKEN_REVOKED,
            )
            return Failure(error=RefreshError.TOKEN_REVOKED)

        # Step 6: Get user from database
        user = await self._user_repo.find_by_id(token_data.user_id)

        # Step 7: Verify user exists
        if user is None:
            await self._publish_failed_event(
                user_id=token_data.user_id,
                reason=RefreshError.USER_NOT_FOUND,
            )
            return Failure(error=RefreshError.USER_NOT_FOUND)

        # Step 7b: Verify token version meets requirements (breach rotation check)
        security_config = await self._security_config_repo.get_or_create_default()
        required_version = max(
            security_config.global_min_token_version,
            user.min_token_version,
        )

        if token_data.token_version < required_version:
            # Check grace period
            now = datetime.now(UTC)
            within_grace = security_config.is_within_grace_period(now)

            # During grace period, allow tokens that were valid at issuance
            if (
                not within_grace
                or token_data.global_version_at_issuance < required_version - 1
            ):
                # Emit security monitoring event
                await self._event_bus.publish(
                    TokenRejectedDueToRotation(
                        event_id=uuid7(),
                        occurred_at=now,
                        user_id=user.id,
                        token_version=token_data.token_version,
                        required_version=required_version,
                        rejection_reason=(
                            "global_rotation"
                            if security_config.global_min_token_version
                            > token_data.token_version
                            else "user_rotation"
                        ),
                    )
                )
                await self._publish_failed_event(
                    user_id=user.id,
                    reason=RefreshError.TOKEN_VERSION_REJECTED,
                )
                return Failure(error=RefreshError.TOKEN_VERSION_REJECTED)

        # Step 7c: Verify user is active
        if not user.is_active:
            await self._publish_failed_event(
                user_id=user.id,
                reason=RefreshError.USER_INACTIVE,
            )
            return Failure(error=RefreshError.USER_INACTIVE)

        # Step 8: Generate new JWT access token
        access_token = self._token_service.generate_access_token(
            user_id=user.id,
            email=user.email,
            roles=["user"],  # Default role, extend in F1.1b
            session_id=token_data.session_id,
        )

        # Step 9: Token rotation - delete old, create new
        # Delete old refresh token
        await self._refresh_token_repo.delete(token_data.id)

        # Generate new refresh token
        new_refresh_token, new_token_hash = self._refresh_token_service.generate_token()

        # Save new refresh token with same session_id and current version
        new_expires_at = self._refresh_token_service.calculate_expiration()
        await self._refresh_token_repo.save(
            user_id=user.id,
            token_hash=new_token_hash,
            session_id=token_data.session_id,
            expires_at=new_expires_at,
            token_version=security_config.global_min_token_version,
            global_version_at_issuance=security_config.global_min_token_version,
        )

        # Step 10: Emit SUCCEEDED event
        await self._event_bus.publish(
            AuthTokenRefreshSucceeded(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                user_id=user.id,
                session_id=token_data.session_id,
            )
        )

        # Step 11: Return Success
        return Success(
            value=RefreshResponse(
                access_token=access_token,
                refresh_token=new_refresh_token,
            )
        )

    async def _find_valid_refresh_token(
        self, provided_token: str
    ) -> RefreshTokenData | None:
        """Find refresh token by verifying against stored hashes.

        Since bcrypt hashes are non-deterministic, we cannot simply hash
        the provided token and look it up. Instead, we need to fetch
        candidates and verify each one.

        Note: This is a simplistic implementation. For production with
        many tokens, consider:
        - Adding a token prefix/identifier to narrow search
        - Using a deterministic hash as a lookup key alongside bcrypt

        Args:
            provided_token: Plain refresh token from user request.

        Returns:
            RefreshTokenData if found and valid, None otherwise.
        """
        # For now, we need a way to look up tokens
        # The repository should have a method to iterate tokens
        # OR we add a token prefix for lookup

        # Since our current protocol doesn't support iteration,
        # we need to verify by hash directly
        # Let's add find_by_verification to the protocol

        # Actually, the login handler saves token_hash, so we need
        # to verify the provided token against each stored hash
        # This requires iterating - not ideal but secure

        # For MVP: Let's look up by user from JWT claims
        # But we don't have user_id in the refresh request...

        # Alternative approach: Store a non-secret token identifier
        # alongside the bcrypt hash for lookup, then verify

        # For now, let's assume the repository has a method to
        # iterate active tokens and verify (we'll add this)

        # Using the verify_and_find pattern:
        return await self._refresh_token_repo.find_by_token_verification(
            provided_token,
            self._refresh_token_service.verify_token,
        )

    async def _publish_failed_event(
        self,
        user_id: UUID | None,
        reason: str,
    ) -> None:
        """Publish AuthTokenRefreshFailed event.

        Args:
            user_id: User ID if known.
            reason: Failure reason.
        """
        await self._event_bus.publish(
            AuthTokenRefreshFailed(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                user_id=user_id,
                reason=reason,
            )
        )
