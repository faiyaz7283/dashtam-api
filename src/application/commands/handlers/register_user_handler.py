"""Registration handler for User Authentication (F1.1).

Implements the registration flow as specified in:
docs/architecture/authentication-architecture.md lines 250-261

Flow:
1. Emit UserRegistrationAttempted event
2. Validate email/password (handled by Annotated types)
3. Check email uniqueness
4. Hash password
5. Create User entity
6. Generate verification token (via repository)
7. Save user and token
8. Emit UserRegistrationSucceeded event (triggers email via EmailEventHandler)
9. Return Success(user_id)

On failure:
- Emit UserRegistrationFailed event
- Return Failure(error)

Architecture:
- Application layer ONLY imports from domain layer (entities, protocols, events)
- NO infrastructure imports (repositories are injected via protocols)
- Handler orchestrates business logic without knowing persistence details
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID
from uuid_extensions import uuid7

from src.application.commands.auth_commands import RegisterUser

if TYPE_CHECKING:
    from fastapi import Request
from src.core.result import Failure, Result, Success
from src.domain.entities.user import User
from src.domain.events.auth_events import (
    UserRegistrationAttempted,
    UserRegistrationFailed,
    UserRegistrationSucceeded,
)
from src.domain.protocols import (
    EmailVerificationTokenRepository,
    PasswordHashingProtocol,
    UserRepository,
)
from src.domain.protocols.event_bus_protocol import EventBusProtocol


class RegistrationError:
    """Registration-specific errors."""

    EMAIL_ALREADY_EXISTS = "Email already registered"
    VALIDATION_FAILED = "Validation failed"
    DATABASE_ERROR = "Database error occurred"


class RegisterUserHandler:
    """Handler for user registration command.

    Follows hexagonal architecture:
    - Application layer (this handler)
    - Domain layer (User entity, protocols)
    - Infrastructure layer (repositories, services via dependency injection)
    """

    def __init__(
        self,
        user_repo: UserRepository,
        verification_token_repo: EmailVerificationTokenRepository,
        password_service: PasswordHashingProtocol,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize registration handler with dependencies.

        Args:
            user_repo: User repository for persistence
            verification_token_repo: Email verification token repository
            password_service: Password hashing service
            event_bus: Event bus for publishing domain events
        """
        self._user_repo = user_repo
        self._verification_token_repo = verification_token_repo
        self._password_service = password_service
        self._event_bus = event_bus

    async def handle(
        self, cmd: RegisterUser, request: "Request | None" = None
    ) -> Result[UUID, str]:
        """Handle user registration command.

        Args:
            cmd: RegisterUser command (email and password validated by Annotated types)
            request: Optional FastAPI Request for IP/user agent tracking (PCI-DSS 10.2.7).

        Returns:
            Success(user_id) on successful registration
            Failure(error_message) on failure

        Side Effects:
            - Publishes UserRegistrationAttempted event (always)
            - Publishes UserRegistrationSucceeded event (on success, triggers email)
            - Publishes UserRegistrationFailed event (on failure)
            - Creates User in database
            - Creates EmailVerificationToken in database
        """
        # Extract request metadata for audit trail (PCI-DSS 10.2.7)
        metadata: dict[str, str] = {}
        if request and request.client:
            metadata["ip_address"] = request.client.host
            metadata["user_agent"] = request.headers.get("user-agent", "Unknown")
        # Step 1: Emit ATTEMPTED event
        await self._event_bus.publish(
            UserRegistrationAttempted(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                email=cmd.email,
            ),
            metadata=metadata,
        )

        try:
            # Step 2: Email/password validation already handled by Annotated types
            # (see domain/validators.py and domain/types.py)

            # Step 3: Check email uniqueness
            existing_user = await self._user_repo.find_by_email(cmd.email)
            if existing_user is not None:
                # Emit FAILED event
                await self._event_bus.publish(
                    UserRegistrationFailed(
                        event_id=uuid7(),
                        occurred_at=datetime.now(UTC),
                        email=cmd.email,
                        reason=RegistrationError.EMAIL_ALREADY_EXISTS,
                    ),
                    metadata=metadata,
                )
                return Failure(error=RegistrationError.EMAIL_ALREADY_EXISTS)

            # Step 4: Hash password
            password_hash = self._password_service.hash_password(cmd.password)

            # Step 5: Create User entity
            user_id = uuid7()
            now = datetime.now(UTC)
            user = User(
                id=user_id,
                email=cmd.email,
                password_hash=password_hash,
                is_verified=False,  # Email verification required
                is_active=True,  # New users are active by default
                failed_login_attempts=0,  # No failed attempts yet
                locked_until=None,  # Not locked
                created_at=now,
                updated_at=now,
            )

            # Step 6: Generate verification token
            verification_token = secrets.token_hex(32)  # 64-char hex string

            # Step 7: Save user and token to database
            # Note: Handler doesn't construct models - repository handles persistence details
            await self._user_repo.save(user)
            await self._verification_token_repo.save(
                user_id=user_id,
                token=verification_token,
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )

            # Step 8: Emit SUCCEEDED event (triggers email via EmailEventHandler)
            await self._event_bus.publish(
                UserRegistrationSucceeded(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    user_id=user_id,
                    email=cmd.email,
                    verification_token=verification_token,
                ),
                metadata=metadata,
            )

            # Step 9: Return Success
            return Success(value=user_id)

        except Exception as e:
            # Catch-all for database errors or unexpected issues
            await self._event_bus.publish(
                UserRegistrationFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    email=cmd.email,
                    reason=f"{RegistrationError.DATABASE_ERROR}: {str(e)}",
                ),
                metadata=metadata,
            )
            return Failure(error=f"{RegistrationError.DATABASE_ERROR}: {str(e)}")
