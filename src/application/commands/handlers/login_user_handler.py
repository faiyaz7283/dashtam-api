"""Login handler for User Authentication.

Flow:
1. Emit UserLoginAttempted event
2. Find user by email
3. Check account exists
4. Check email verified
5. Check account not locked
6. Verify password
7. Reset failed login counter on success
8. Generate JWT access token
9. Generate opaque refresh token
10. Save refresh token to database
11. Emit UserLoginSucceeded event
12. Return Success(tokens)

On failure:
- Increment failed login counter (if password wrong)
- Emit UserLoginFailed event
- Return Failure(error)

Architecture:
- Application layer ONLY imports from domain layer (entities, protocols, events)
- NO infrastructure imports (repositories are injected via protocols)
- Handler orchestrates business logic without knowing persistence details
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.application.commands.auth_commands import LoginUser
from src.core.result import Failure, Result, Success
from src.domain.events.auth_events import (
    UserLoginAttempted,
    UserLoginFailed,
    UserLoginSucceeded,
)
from src.domain.protocols import (
    PasswordHashingProtocol,
    RefreshTokenRepository,
    TokenGenerationProtocol,
    UserRepository,
)
from src.domain.protocols.event_bus_protocol import EventBusProtocol

if TYPE_CHECKING:
    from src.infrastructure.security.refresh_token_service import RefreshTokenService


class LoginError:
    """Login-specific error reasons."""

    INVALID_CREDENTIALS = "invalid_credentials"
    EMAIL_NOT_VERIFIED = "email_not_verified"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_INACTIVE = "account_inactive"


@dataclass
class LoginResponse:
    """Response data for successful login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes in seconds


class LoginUserHandler:
    """Handler for user login command.

    Follows hexagonal architecture:
    - Application layer (this handler)
    - Domain layer (User entity, protocols)
    - Infrastructure layer (repositories, services via dependency injection)
    """

    def __init__(
        self,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        password_service: PasswordHashingProtocol,
        token_service: TokenGenerationProtocol,
        refresh_token_service: "RefreshTokenService",  # Forward reference
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize login handler with dependencies.

        Args:
            user_repo: User repository for persistence.
            refresh_token_repo: Refresh token repository for persistence.
            password_service: Password hashing/verification service.
            token_service: JWT token generation service.
            refresh_token_service: Refresh token generation service.
            event_bus: Event bus for publishing domain events.
        """
        self._user_repo = user_repo
        self._refresh_token_repo = refresh_token_repo
        self._password_service = password_service
        self._token_service = token_service
        self._refresh_token_service = refresh_token_service
        self._event_bus = event_bus

    async def handle(self, cmd: LoginUser) -> Result[LoginResponse, str]:
        """Handle user login command.

        Args:
            cmd: LoginUser command (email and password validated by Annotated types).

        Returns:
            Success(LoginResponse) on successful login.
            Failure(error_message) on failure.

        Side Effects:
            - Publishes UserLoginAttempted event (always).
            - Publishes UserLoginSucceeded event (on success).
            - Publishes UserLoginFailed event (on failure).
            - Updates User failed_login_attempts on wrong password.
            - Creates RefreshToken in database.
        """
        # Step 1: Emit ATTEMPTED event
        await self._event_bus.publish(
            UserLoginAttempted(
                event_id=uuid4(),
                occurred_at=datetime.now(UTC),
                email=cmd.email,
            )
        )

        # Step 2: Find user by email
        user = await self._user_repo.find_by_email(cmd.email)

        # Step 3: Check account exists
        if user is None:
            await self._publish_failed_event(
                email=cmd.email,
                reason=LoginError.INVALID_CREDENTIALS,
                user_id=None,
            )
            # Use generic message to prevent user enumeration
            return Failure(error=LoginError.INVALID_CREDENTIALS)

        # Step 4: Check email verified
        if not user.is_verified:
            await self._publish_failed_event(
                email=cmd.email,
                reason=LoginError.EMAIL_NOT_VERIFIED,
                user_id=user.id,
            )
            return Failure(error=LoginError.EMAIL_NOT_VERIFIED)

        # Step 5: Check account not locked
        if user.is_locked():
            await self._publish_failed_event(
                email=cmd.email,
                reason=LoginError.ACCOUNT_LOCKED,
                user_id=user.id,
            )
            return Failure(error=LoginError.ACCOUNT_LOCKED)

        # Check account active
        if not user.is_active:
            await self._publish_failed_event(
                email=cmd.email,
                reason=LoginError.ACCOUNT_INACTIVE,
                user_id=user.id,
            )
            return Failure(error=LoginError.ACCOUNT_INACTIVE)

        # Step 6: Verify password
        if not self._password_service.verify_password(cmd.password, user.password_hash):
            # Increment failed login counter
            user.increment_failed_login()
            await self._user_repo.update(user)

            await self._publish_failed_event(
                email=cmd.email,
                reason=LoginError.INVALID_CREDENTIALS,
                user_id=user.id,
            )
            return Failure(error=LoginError.INVALID_CREDENTIALS)

        # Step 7: Reset failed login counter on success
        if user.failed_login_attempts > 0:
            user.reset_failed_login()
            await self._user_repo.update(user)

        # Step 8: Generate JWT access token
        # Note: session_id will be from F1.3, using placeholder UUID for now
        session_id = uuid4()  # TODO: Create actual session in F1.3
        access_token = self._token_service.generate_access_token(
            user_id=user.id,
            email=user.email,
            roles=["user"],  # Default role, extend in F1.1b
            session_id=session_id,
        )

        # Step 9: Generate opaque refresh token
        refresh_token, token_hash = self._refresh_token_service.generate_token()

        # Step 10: Save refresh token to database
        expires_at = self._refresh_token_service.calculate_expiration()
        await self._refresh_token_repo.save(
            user_id=user.id,
            token_hash=token_hash,
            session_id=session_id,
            expires_at=expires_at,
        )

        # Step 11: Emit SUCCEEDED event
        await self._event_bus.publish(
            UserLoginSucceeded(
                event_id=uuid4(),
                occurred_at=datetime.now(UTC),
                user_id=user.id,
                email=user.email,
                session_id=session_id,
            )
        )

        # Step 12: Return Success
        return Success(
            value=LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
            )
        )

    async def _publish_failed_event(
        self,
        email: str,
        reason: str,
        user_id: UUID | None,
    ) -> None:
        """Publish UserLoginFailed event.

        Args:
            email: Email address attempted.
            reason: Failure reason.
            user_id: User ID if found (for tracking lockout).
        """
        await self._event_bus.publish(
            UserLoginFailed(
                event_id=uuid4(),
                occurred_at=datetime.now(UTC),
                email=email,
                reason=reason,
                user_id=user_id,
            )
        )
