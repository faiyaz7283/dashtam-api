"""Confirm Password Reset handler for User Authentication.

Flow:
1. Emit PasswordResetConfirmAttempted event
2. Look up token by token string
3. Verify token exists and not used
4. Verify token not expired
5. Get user from database
6. Hash new password
7. Update user's password
8. Mark token as used
9. Revoke all refresh tokens (force re-login)
10. Send password changed notification email
11. Emit PasswordResetConfirmSucceeded event
12. Return Success(message)

On failure:
- Emit PasswordResetConfirmFailed event
- Return Failure(error)

Architecture:
- Application layer ONLY imports from domain layer (entities, protocols, events)
- NO infrastructure imports (repositories are injected via protocols)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid_extensions import uuid7

from src.application.commands.auth_commands import ConfirmPasswordReset

if TYPE_CHECKING:
    from fastapi import Request
from src.core.result import Failure, Result, Success
from src.domain.events.auth_events import (
    PasswordResetConfirmAttempted,
    PasswordResetConfirmFailed,
    PasswordResetConfirmSucceeded,
)
from src.domain.protocols import (
    EmailServiceProtocol,
    PasswordHashingProtocol,
    PasswordResetTokenRepository,
    RefreshTokenRepository,
    UserRepository,
)
from src.domain.protocols.event_bus_protocol import EventBusProtocol


class PasswordResetConfirmError:
    """Password reset confirmation error reasons."""

    TOKEN_NOT_FOUND = "token_not_found"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_ALREADY_USED = "token_already_used"
    USER_NOT_FOUND = "user_not_found"


@dataclass
class PasswordResetConfirmResponse:
    """Response data for successful password reset confirmation."""

    message: str = (
        "Password has been reset successfully. Please login with your new password."
    )


class ConfirmPasswordResetHandler:
    """Handler for confirm password reset command.

    Validates token, updates password, and forces re-login by revoking
    all refresh tokens.

    Follows hexagonal architecture:
    - Application layer (this handler)
    - Domain layer (User entity, protocols)
    - Infrastructure layer (repositories, services via dependency injection)
    """

    def __init__(
        self,
        user_repo: UserRepository,
        password_reset_repo: PasswordResetTokenRepository,
        refresh_token_repo: RefreshTokenRepository,
        password_service: PasswordHashingProtocol,
        email_service: EmailServiceProtocol,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize password reset confirmation handler with dependencies.

        Args:
            user_repo: User repository for user lookup and update.
            password_reset_repo: Password reset token repository.
            refresh_token_repo: Refresh token repository for session revocation.
            password_service: Password hashing service.
            email_service: Email sending service.
            event_bus: Event bus for publishing domain events.
        """
        self._user_repo = user_repo
        self._password_reset_repo = password_reset_repo
        self._refresh_token_repo = refresh_token_repo
        self._password_service = password_service
        self._email_service = email_service
        self._event_bus = event_bus

    async def handle(
        self, cmd: ConfirmPasswordReset, request: "Request | None" = None
    ) -> Result[PasswordResetConfirmResponse, str]:
        """Handle confirm password reset command.

        Args:
            cmd: ConfirmPasswordReset command with token and new password.
            request: Optional FastAPI Request for IP/user agent tracking (PCI-DSS 10.2.7).

        Returns:
            Success(PasswordResetConfirmResponse) on successful password reset.
            Failure(error_message) on failure.

        Side Effects:
            - Publishes PasswordResetConfirmAttempted event (always).
            - Publishes PasswordResetConfirmSucceeded/Failed event.
            - Updates user's password in database.
            - Marks token as used in database.
            - Revokes all refresh tokens for user.
            - Sends password changed notification email.
        """
        # Extract request metadata for audit trail (PCI-DSS 10.2.7)
        metadata: dict[str, str] = {}
        if request and request.client:
            metadata["ip_address"] = request.client.host
            metadata["user_agent"] = request.headers.get("user-agent", "Unknown")
        # Step 1: Emit ATTEMPTED event
        await self._event_bus.publish(
            PasswordResetConfirmAttempted(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                token=cmd.token[:8] + "..." if len(cmd.token) > 8 else cmd.token,
            ),
            metadata=metadata,
        )

        # Step 2: Look up token
        token_data = await self._password_reset_repo.find_by_token(cmd.token)

        # Step 3: Verify token exists (find_by_token already filters used tokens)
        if token_data is None:
            await self._publish_failed_event(
                token=cmd.token,
                reason=PasswordResetConfirmError.TOKEN_NOT_FOUND,
                metadata=metadata,
            )
            return Failure(error=PasswordResetConfirmError.TOKEN_NOT_FOUND)

        # Step 4: Verify token not expired
        if token_data.expires_at < datetime.now(UTC):
            await self._publish_failed_event(
                token=cmd.token,
                reason=PasswordResetConfirmError.TOKEN_EXPIRED,
                metadata=metadata,
            )
            return Failure(error=PasswordResetConfirmError.TOKEN_EXPIRED)

        # Step 5: Get user from database
        user = await self._user_repo.find_by_id(token_data.user_id)

        if user is None:
            await self._publish_failed_event(
                token=cmd.token,
                reason=PasswordResetConfirmError.USER_NOT_FOUND,
                metadata=metadata,
            )
            return Failure(error=PasswordResetConfirmError.USER_NOT_FOUND)

        # Step 6: Hash new password
        password_hash = self._password_service.hash_password(cmd.new_password)

        # Step 7: Update user's password
        await self._user_repo.update_password(
            user_id=user.id,
            password_hash=password_hash,
        )

        # Step 8: Mark token as used
        await self._password_reset_repo.mark_as_used(token_data.id)

        # Step 9: Revoke all refresh tokens (force re-login on all devices)
        await self._refresh_token_repo.revoke_all_for_user(
            user_id=user.id,
            reason="password_reset",
        )

        # Step 10: Send password changed notification email
        await self._email_service.send_password_changed_notification(
            to_email=user.email,
        )

        # Step 11: Emit SUCCEEDED event
        await self._event_bus.publish(
            PasswordResetConfirmSucceeded(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                user_id=user.id,
                email=user.email,
            ),
            metadata=metadata,
        )

        # Step 12: Return Success
        return Success(value=PasswordResetConfirmResponse())

    async def _publish_failed_event(
        self,
        token: str,
        reason: str,
        metadata: dict[str, str],
    ) -> None:
        """Publish PasswordResetConfirmFailed event.

        Args:
            token: Password reset token (will be truncated).
            reason: Failure reason.
            metadata: Request metadata for audit trail.
        """
        await self._event_bus.publish(
            PasswordResetConfirmFailed(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                token=token[:8] + "..." if len(token) > 8 else token,
                reason=reason,
            ),
            metadata=metadata,
        )
