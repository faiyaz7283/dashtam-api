"""Logout User handler for User Authentication.

Flow:
1. Emit UserLogoutAttempted event
2. Find refresh token by verification
3. Revoke refresh token (or revoke by session if token found)
4. Emit UserLogoutSucceeded event
5. Return Success(message)

Note: JWT access tokens cannot be revoked (they expire naturally in 15 minutes).
This handler only revokes the refresh token to prevent new access tokens.

Architecture:
- Application layer ONLY imports from domain layer (entities, protocols, events)
- NO infrastructure imports (repositories are injected via protocols)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.application.commands.auth_commands import LogoutUser
from src.core.result import Result, Success
from src.domain.events.auth_events import (
    UserLogoutAttempted,
    UserLogoutFailed,
    UserLogoutSucceeded,
)
from src.domain.protocols import (
    RefreshTokenRepository,
    RefreshTokenServiceProtocol,
)
from src.domain.protocols.event_bus_protocol import EventBusProtocol


class LogoutError:
    """Logout error reasons."""

    TOKEN_NOT_FOUND = "token_not_found"
    TOKEN_ALREADY_REVOKED = "token_already_revoked"


@dataclass
class LogoutResponse:
    """Response data for successful logout."""

    message: str = "Successfully logged out."


class LogoutUserHandler:
    """Handler for logout user command.

    Revokes the refresh token to prevent new access tokens from being issued.
    The current access token remains valid until it expires (15 minutes).

    Follows hexagonal architecture:
    - Application layer (this handler)
    - Domain layer (protocols)
    - Infrastructure layer (repositories, services via dependency injection)
    """

    def __init__(
        self,
        refresh_token_repo: RefreshTokenRepository,
        refresh_token_service: RefreshTokenServiceProtocol,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize logout handler with dependencies.

        Args:
            refresh_token_repo: Refresh token repository for revocation.
            refresh_token_service: Service for token verification.
            event_bus: Event bus for publishing domain events.
        """
        self._refresh_token_repo = refresh_token_repo
        self._refresh_token_service = refresh_token_service
        self._event_bus = event_bus

    async def handle(self, cmd: LogoutUser) -> Result[LogoutResponse, str]:
        """Handle logout user command.

        Args:
            cmd: LogoutUser command with user_id and refresh_token.

        Returns:
            Success(LogoutResponse) on successful logout.
            Failure(error_message) on failure.

        Side Effects:
            - Publishes UserLogoutAttempted event (always).
            - Publishes UserLogoutSucceeded/Failed event.
            - Revokes refresh token in database.
        """
        # Step 1: Emit ATTEMPTED event
        await self._event_bus.publish(
            UserLogoutAttempted(
                event_id=uuid4(),
                occurred_at=datetime.now(UTC),
                user_id=cmd.user_id,
            )
        )

        # Step 2: Find refresh token by verification
        token_data = await self._refresh_token_repo.find_by_token_verification(
            cmd.refresh_token,
            self._refresh_token_service.verify_token,
        )

        session_id: UUID | None = None

        if token_data is None:
            # Token not found - could be already revoked or invalid
            # For security, we still return success but log internally
            await self._event_bus.publish(
                UserLogoutFailed(
                    event_id=uuid4(),
                    occurred_at=datetime.now(UTC),
                    user_id=cmd.user_id,
                    reason=LogoutError.TOKEN_NOT_FOUND,
                )
            )
            # Return success anyway to prevent information leakage
            # User experience: they wanted to logout, we say they're logged out
            return Success(value=LogoutResponse())

        # Check if token belongs to this user (security check)
        if token_data.user_id != cmd.user_id:
            # Token doesn't belong to user - security issue
            await self._event_bus.publish(
                UserLogoutFailed(
                    event_id=uuid4(),
                    occurred_at=datetime.now(UTC),
                    user_id=cmd.user_id,
                    reason="token_user_mismatch",
                )
            )
            # Return success to prevent information leakage
            return Success(value=LogoutResponse())

        # Check if already revoked
        if token_data.revoked_at is not None:
            await self._event_bus.publish(
                UserLogoutFailed(
                    event_id=uuid4(),
                    occurred_at=datetime.now(UTC),
                    user_id=cmd.user_id,
                    reason=LogoutError.TOKEN_ALREADY_REVOKED,
                )
            )
            # Return success - user wanted to logout, token is already revoked
            return Success(value=LogoutResponse())

        session_id = token_data.session_id

        # Step 3: Revoke the session (revokes all tokens for this session)
        await self._refresh_token_repo.revoke_by_session(session_id)

        # Step 4: Emit SUCCEEDED event
        await self._event_bus.publish(
            UserLogoutSucceeded(
                event_id=uuid4(),
                occurred_at=datetime.now(UTC),
                user_id=cmd.user_id,
                session_id=session_id,
            )
        )

        # Step 5: Return Success
        return Success(value=LogoutResponse())
