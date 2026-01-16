"""Email verification handler for User Authentication.

Flow:
1. Emit EmailVerificationAttempted event
2. Find token by token string
3. Check token exists
4. Check token not expired
5. Check token not already used
6. Update user.is_verified = True
7. Mark token as used
8. Emit EmailVerificationSucceeded event
9. Return Success(user_id)

On failure:
- Emit EmailVerificationFailed event
- Return Failure(error)

Architecture:
- Application layer ONLY imports from domain layer (entities, protocols, events)
- NO infrastructure imports (repositories are injected via protocols)
- Handler orchestrates business logic without knowing persistence details
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID
from uuid_extensions import uuid7

from src.application.commands.auth_commands import VerifyEmail

if TYPE_CHECKING:
    from fastapi import Request
from src.core.result import Failure, Result, Success
from src.domain.events.auth_events import (
    EmailVerificationAttempted,
    EmailVerificationFailed,
    EmailVerificationSucceeded,
)
from src.domain.protocols import (
    EmailVerificationTokenRepository,
    UserRepository,
)
from src.domain.protocols.event_bus_protocol import EventBusProtocol


class VerifyEmailError:
    """Email verification error reasons."""

    TOKEN_NOT_FOUND = "token_not_found"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_ALREADY_USED = "token_already_used"
    USER_NOT_FOUND = "user_not_found"


class VerifyEmailHandler:
    """Handler for email verification command.

    Follows hexagonal architecture:
    - Application layer (this handler)
    - Domain layer (User entity, protocols)
    - Infrastructure layer (repositories via dependency injection)
    """

    def __init__(
        self,
        user_repo: UserRepository,
        verification_token_repo: EmailVerificationTokenRepository,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize email verification handler with dependencies.

        Args:
            user_repo: User repository for persistence.
            verification_token_repo: Email verification token repository.
            event_bus: Event bus for publishing domain events.
        """
        self._user_repo = user_repo
        self._verification_token_repo = verification_token_repo
        self._event_bus = event_bus

    async def handle(
        self, cmd: VerifyEmail, request: "Request | None" = None
    ) -> Result[UUID, str]:
        """Handle email verification command.

        Args:
            cmd: VerifyEmail command (token validated by Annotated types).
            request: Optional FastAPI Request for IP/user agent tracking (PCI-DSS 10.2.7).

        Returns:
            Success(user_id) on successful verification.
            Failure(error_message) on failure.

        Side Effects:
            - Publishes EmailVerificationAttempted event (always).
            - Publishes EmailVerificationSucceeded event (on success).
            - Publishes EmailVerificationFailed event (on failure).
            - Updates User.is_verified to True.
            - Marks token as used.
        """
        # Extract request metadata for audit trail (PCI-DSS 10.2.7)
        metadata: dict[str, str] = {}
        if request and request.client:
            metadata["ip_address"] = request.client.host
            metadata["user_agent"] = request.headers.get("user-agent", "Unknown")
        # Truncate token for logging (security)
        token_preview = cmd.token[:8] if len(cmd.token) >= 8 else cmd.token

        # Step 1: Emit ATTEMPTED event
        await self._event_bus.publish(
            EmailVerificationAttempted(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                token=token_preview,
            ),
            metadata=metadata,
        )

        # Step 2: Find token by token string
        token_data = await self._verification_token_repo.find_by_token(cmd.token)

        # Step 3: Check token exists
        if token_data is None:
            await self._publish_failed_event(
                token=token_preview,
                reason=VerifyEmailError.TOKEN_NOT_FOUND,
                metadata=metadata,
            )
            return Failure(error=VerifyEmailError.TOKEN_NOT_FOUND)

        # Step 4: Check token not expired
        if token_data.expires_at < datetime.now(UTC):
            await self._publish_failed_event(
                token=token_preview,
                reason=VerifyEmailError.TOKEN_EXPIRED,
                metadata=metadata,
            )
            return Failure(error=VerifyEmailError.TOKEN_EXPIRED)

        # Step 5: Check token not already used (should not happen due to find_by_token filter)
        if token_data.used_at is not None:
            await self._publish_failed_event(
                token=token_preview,
                reason=VerifyEmailError.TOKEN_ALREADY_USED,
                metadata=metadata,
            )
            return Failure(error=VerifyEmailError.TOKEN_ALREADY_USED)

        # Find user to update
        user = await self._user_repo.find_by_id(token_data.user_id)
        if user is None:
            await self._publish_failed_event(
                token=token_preview,
                reason=VerifyEmailError.USER_NOT_FOUND,
                metadata=metadata,
            )
            return Failure(error=VerifyEmailError.USER_NOT_FOUND)

        # Step 6: Update user.is_verified = True
        user.is_verified = True
        user.updated_at = datetime.now(UTC)
        await self._user_repo.update(user)

        # Step 7: Mark token as used
        await self._verification_token_repo.mark_as_used(token_data.id)

        # Step 8: Emit SUCCEEDED event
        await self._event_bus.publish(
            EmailVerificationSucceeded(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                user_id=user.id,
                email=user.email,
            ),
            metadata=metadata,
        )

        # Step 9: Return Success
        return Success(value=user.id)

    async def _publish_failed_event(
        self,
        token: str,
        reason: str,
        metadata: dict[str, str],
    ) -> None:
        """Publish EmailVerificationFailed event.

        Args:
            token: Truncated token for logging.
            reason: Failure reason.
            metadata: Request metadata for audit trail.
        """
        await self._event_bus.publish(
            EmailVerificationFailed(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                token=token,
                reason=reason,
            ),
            metadata=metadata,
        )
