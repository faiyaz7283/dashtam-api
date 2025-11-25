"""Request Password Reset handler for User Authentication.

Flow:
1. Emit PasswordResetRequestAttempted event
2. Look up user by email
3. If user not found: emit FAILED event, but return Success (no user enumeration)
4. Check rate limiting (max 3 requests per hour)
5. Generate password reset token
6. Save token to database
7. Send password reset email
8. Emit PasswordResetRequestSucceeded event
9. Return Success(message)

Security:
- ALWAYS returns success to prevent user enumeration attacks
- Rate limiting to prevent abuse
- Token expires after 15 minutes

Architecture:
- Application layer ONLY imports from domain layer (entities, protocols, events)
- NO infrastructure imports (repositories are injected via protocols)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.application.commands.auth_commands import RequestPasswordReset
from src.core.result import Result, Success
from src.domain.events.auth_events import (
    PasswordResetRequestAttempted,
    PasswordResetRequestFailed,
    PasswordResetRequestSucceeded,
)
from src.domain.protocols import (
    EmailServiceProtocol,
    PasswordResetTokenRepository,
    PasswordResetTokenServiceProtocol,
    UserRepository,
)
from src.domain.protocols.event_bus_protocol import EventBusProtocol


class PasswordResetError:
    """Password reset error reasons (internal only, not exposed to API)."""

    USER_NOT_FOUND = "user_not_found"
    RATE_LIMITED = "rate_limited"
    USER_NOT_VERIFIED = "user_not_verified"


@dataclass
class PasswordResetRequestResponse:
    """Response data for password reset request.

    Note: Always returns success message to prevent user enumeration.
    """

    message: str = (
        "If an account with that email exists, a password reset link has been sent."
    )


class RequestPasswordResetHandler:
    """Handler for request password reset command.

    Security considerations:
    - Always returns success (no user enumeration)
    - Rate limits requests (max 3 per hour per user)
    - Tokens expire after 15 minutes

    Follows hexagonal architecture:
    - Application layer (this handler)
    - Domain layer (User entity, protocols)
    - Infrastructure layer (repositories, services via dependency injection)
    """

    # Rate limiting: max 3 requests per hour
    MAX_REQUESTS_PER_HOUR = 3

    def __init__(
        self,
        user_repo: UserRepository,
        password_reset_repo: PasswordResetTokenRepository,
        token_service: PasswordResetTokenServiceProtocol,
        email_service: EmailServiceProtocol,
        event_bus: EventBusProtocol,
        verification_url_base: str,
    ) -> None:
        """Initialize password reset request handler with dependencies.

        Args:
            user_repo: User repository for user lookup.
            password_reset_repo: Password reset token repository.
            token_service: Token generation service.
            email_service: Email sending service.
            event_bus: Event bus for publishing domain events.
            verification_url_base: Base URL for password reset links.
        """
        self._user_repo = user_repo
        self._password_reset_repo = password_reset_repo
        self._token_service = token_service
        self._email_service = email_service
        self._event_bus = event_bus
        self._verification_url_base = verification_url_base

    async def handle(
        self, cmd: RequestPasswordReset
    ) -> Result[PasswordResetRequestResponse, str]:
        """Handle password reset request command.

        Args:
            cmd: RequestPasswordReset command with user's email.

        Returns:
            Always returns Success(PasswordResetRequestResponse).
            This prevents user enumeration attacks.

        Side Effects:
            - Publishes PasswordResetRequestAttempted event (always).
            - Publishes PasswordResetRequestSucceeded/Failed event.
            - Creates PasswordResetToken in database (if user exists).
            - Sends password reset email (if user exists).
        """
        # Step 1: Emit ATTEMPTED event
        await self._event_bus.publish(
            PasswordResetRequestAttempted(
                event_id=uuid4(),
                occurred_at=datetime.now(UTC),
                email=cmd.email,
            )
        )

        # Step 2: Look up user by email
        user = await self._user_repo.find_by_email(cmd.email)

        # Step 3: If user not found, emit FAILED event but return success
        if user is None:
            await self._event_bus.publish(
                PasswordResetRequestFailed(
                    event_id=uuid4(),
                    occurred_at=datetime.now(UTC),
                    email=cmd.email,
                    reason=PasswordResetError.USER_NOT_FOUND,
                )
            )
            # Return success to prevent user enumeration
            return Success(value=PasswordResetRequestResponse())

        # Check if user's email is verified
        if not user.is_verified:
            await self._event_bus.publish(
                PasswordResetRequestFailed(
                    event_id=uuid4(),
                    occurred_at=datetime.now(UTC),
                    email=cmd.email,
                    reason=PasswordResetError.USER_NOT_VERIFIED,
                )
            )
            # Return success to prevent user enumeration
            return Success(value=PasswordResetRequestResponse())

        # Step 4: Check rate limiting
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        request_count = await self._password_reset_repo.count_recent_requests(
            user_id=user.id,
            since=one_hour_ago,
        )

        if request_count >= self.MAX_REQUESTS_PER_HOUR:
            await self._event_bus.publish(
                PasswordResetRequestFailed(
                    event_id=uuid4(),
                    occurred_at=datetime.now(UTC),
                    email=cmd.email,
                    reason=PasswordResetError.RATE_LIMITED,
                )
            )
            # Return success to prevent user enumeration
            return Success(value=PasswordResetRequestResponse())

        # Step 5: Generate password reset token
        token = self._token_service.generate_token()
        expires_at = self._token_service.calculate_expiration()

        # Step 6: Save token to database
        await self._password_reset_repo.save(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
            ip_address=cmd.ip_address,
            user_agent=cmd.user_agent,
        )

        # Step 7: Send password reset email
        reset_url = f"{self._verification_url_base}/api/v1/auth/password-reset/confirm?token={token}"
        await self._email_service.send_password_reset_email(
            to_email=user.email,
            reset_url=reset_url,
        )

        # Step 8: Emit SUCCEEDED event
        await self._event_bus.publish(
            PasswordResetRequestSucceeded(
                event_id=uuid4(),
                occurred_at=datetime.now(UTC),
                user_id=user.id,
                email=user.email,
                reset_token=token[:8] + "...",  # Truncated for security in logs
            )
        )

        # Step 9: Return Success
        return Success(value=PasswordResetRequestResponse())
