"""Authenticate user handler.

Single responsibility: Verify user credentials.
Does NOT create sessions or generate tokens (CQRS separation).

Flow:
1. Emit UserLoginAttempted event
2. Find user by email
3. Check account exists
4. Check email verified
5. Check account not locked
6. Check account active
7. Verify password
8. Reset failed login counter on success
9. Emit UserLoginSucceeded event
10. Return Success(AuthenticatedUser)

On failure:
- Increment failed login counter (if password wrong)
- Emit UserLoginFailed event
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

from src.application.commands.auth_commands import AuthenticateUser, AuthenticatedUser

if TYPE_CHECKING:
    from fastapi import Request
from src.core.result import Failure, Result, Success
from src.domain.events.auth_events import (
    UserLoginAttempted,
    UserLoginFailed,
    UserLoginSucceeded,
)
from src.domain.protocols import PasswordHashingProtocol, UserRepository
from src.domain.protocols.event_bus_protocol import EventBusProtocol


class AuthenticationError:
    """Authentication-specific error reasons."""

    INVALID_CREDENTIALS = "invalid_credentials"
    EMAIL_NOT_VERIFIED = "email_not_verified"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_INACTIVE = "account_inactive"


class AuthenticateUserHandler:
    """Handler for user authentication command.

    Single responsibility: Verify user credentials and return user data.
    Does NOT create sessions or generate tokens.

    Follows hexagonal architecture:
    - Application layer (this handler)
    - Domain layer (User entity, protocols)
    - Infrastructure layer (repositories via dependency injection)
    """

    def __init__(
        self,
        user_repo: UserRepository,
        password_service: PasswordHashingProtocol,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize authentication handler with dependencies.

        Args:
            user_repo: User repository for persistence.
            password_service: Password hashing/verification service.
            event_bus: Event bus for publishing domain events.
        """
        self._user_repo = user_repo
        self._password_service = password_service
        self._event_bus = event_bus

    async def handle(
        self, cmd: AuthenticateUser, request: "Request | None" = None
    ) -> Result[AuthenticatedUser, str]:
        """Handle user authentication command.

        Args:
            cmd: AuthenticateUser command (email and password).
            request: Optional FastAPI Request for IP/user agent tracking (PCI-DSS 10.2.7).

        Returns:
            Success(AuthenticatedUser) on successful authentication.
            Failure(error_message) on failure.

        Side Effects:
            - Publishes UserLoginAttempted event (always).
            - Publishes UserLoginSucceeded event (on success).
            - Publishes UserLoginFailed event (on failure).
            - Updates User failed_login_attempts on wrong password.
        """
        # Extract request metadata for audit trail (PCI-DSS 10.2.7)
        metadata: dict[str, str] = {}
        if request and request.client:
            metadata["ip_address"] = request.client.host
            metadata["user_agent"] = request.headers.get("user-agent", "Unknown")
        # Step 1: Emit ATTEMPTED event
        await self._event_bus.publish(
            UserLoginAttempted(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                email=cmd.email,
            ),
            metadata=metadata,
        )

        # Step 2: Find user by email
        user = await self._user_repo.find_by_email(cmd.email)

        # Step 3: Check account exists
        if user is None:
            await self._publish_failed_event(
                email=cmd.email,
                reason=AuthenticationError.INVALID_CREDENTIALS,
                user_id=None,
                metadata=metadata,
            )
            # Use generic message to prevent user enumeration
            return Failure(error=AuthenticationError.INVALID_CREDENTIALS)

        # Step 4: Check email verified
        if not user.is_verified:
            await self._publish_failed_event(
                email=cmd.email,
                reason=AuthenticationError.EMAIL_NOT_VERIFIED,
                user_id=user.id,
                metadata=metadata,
            )
            return Failure(error=AuthenticationError.EMAIL_NOT_VERIFIED)

        # Step 5: Check account not locked
        if user.is_locked():
            await self._publish_failed_event(
                email=cmd.email,
                reason=AuthenticationError.ACCOUNT_LOCKED,
                user_id=user.id,
                metadata=metadata,
            )
            return Failure(error=AuthenticationError.ACCOUNT_LOCKED)

        # Step 6: Check account active
        if not user.is_active:
            await self._publish_failed_event(
                email=cmd.email,
                reason=AuthenticationError.ACCOUNT_INACTIVE,
                user_id=user.id,
                metadata=metadata,
            )
            return Failure(error=AuthenticationError.ACCOUNT_INACTIVE)

        # Step 7: Verify password
        if not self._password_service.verify_password(cmd.password, user.password_hash):
            # Increment failed login counter
            user.increment_failed_login()
            await self._user_repo.update(user)

            await self._publish_failed_event(
                email=cmd.email,
                reason=AuthenticationError.INVALID_CREDENTIALS,
                user_id=user.id,
                metadata=metadata,
            )
            return Failure(error=AuthenticationError.INVALID_CREDENTIALS)

        # Step 8: Reset failed login counter on success
        if user.failed_login_attempts > 0:
            user.reset_failed_login()
            await self._user_repo.update(user)

        # Step 9: Emit SUCCEEDED event
        # Note: session_id is no longer emitted here - session creation is separate
        await self._event_bus.publish(
            UserLoginSucceeded(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                user_id=user.id,
                email=user.email,
            ),
            metadata=metadata,
        )

        # Step 10: Return authenticated user data
        return Success(
            value=AuthenticatedUser(
                user_id=user.id,
                email=user.email,
                roles=["user"],  # Default role, extend in authorization feature
            )
        )

    async def _publish_failed_event(
        self,
        email: str,
        reason: str,
        user_id: UUID | None,
        metadata: dict[str, str],
    ) -> None:
        """Publish UserLoginFailed event.

        Args:
            email: Email address attempted.
            reason: Failure reason.
            user_id: User ID if found (for tracking lockout).
            metadata: Request metadata for audit trail.
        """
        await self._event_bus.publish(
            UserLoginFailed(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                email=email,
                reason=reason,
                user_id=user_id,
            ),
            metadata=metadata,
        )
