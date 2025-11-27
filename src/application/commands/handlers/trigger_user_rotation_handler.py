"""Handler for TriggerUserTokenRotation command.

Flow:
1. Emit UserTokenRotationAttempted event
2. Get user from database
3. Verify user exists
4. Increment user.min_token_version
5. Save user
6. Emit UserTokenRotationSucceeded event
7. Return Success(UserRotationResult)

On failure:
- Emit UserTokenRotationFailed event
- Return Failure(error)
"""

from datetime import UTC, datetime
from uuid import uuid4

from src.application.commands.rotation_commands import (
    TriggerUserTokenRotation,
    UserRotationResult,
)
from src.core.result import Failure, Result, Success
from src.domain.events.auth_events import (
    UserTokenRotationAttempted,
    UserTokenRotationFailed,
    UserTokenRotationSucceeded,
)
from src.domain.protocols import UserRepository
from src.domain.protocols.event_bus_protocol import EventBusProtocol


class RotationError:
    """User rotation error reasons."""

    USER_NOT_FOUND = "user_not_found"


class TriggerUserTokenRotationHandler:
    """Handler for per-user token rotation command.

    Increments the user's minimum token version, which causes only
    that user's existing refresh tokens to fail validation.

    Use cases:
    - Password change (automatic integration)
    - "Log out everywhere" user action
    - Admin action on suspicious accounts
    """

    def __init__(
        self,
        user_repo: UserRepository,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            user_repo: User repository for persistence.
            event_bus: Event bus for publishing domain events.
        """
        self._user_repo = user_repo
        self._event_bus = event_bus

    async def handle(
        self,
        cmd: TriggerUserTokenRotation,
    ) -> Result[UserRotationResult, str]:
        """Handle per-user token rotation command.

        Args:
            cmd: TriggerUserTokenRotation command.

        Returns:
            Success(UserRotationResult) on success.
            Failure(error) on failure.
        """
        # Step 1: Emit ATTEMPTED event
        await self._event_bus.publish(
            UserTokenRotationAttempted(
                event_id=uuid4(),
                occurred_at=datetime.now(UTC),
                user_id=cmd.user_id,
                triggered_by=cmd.triggered_by,
                reason=cmd.reason,
            )
        )

        # Step 2: Get user from database
        user = await self._user_repo.find_by_id(cmd.user_id)

        # Step 3: Verify user exists
        if user is None:
            await self._event_bus.publish(
                UserTokenRotationFailed(
                    event_id=uuid4(),
                    occurred_at=datetime.now(UTC),
                    user_id=cmd.user_id,
                    triggered_by=cmd.triggered_by,
                    reason=cmd.reason,
                    failure_reason=RotationError.USER_NOT_FOUND,
                )
            )
            return Failure(error=RotationError.USER_NOT_FOUND)

        # Step 4: Increment user.min_token_version
        previous_version = user.min_token_version
        user.min_token_version = previous_version + 1
        user.updated_at = datetime.now(UTC)

        # Step 5: Save user
        await self._user_repo.update(user)

        # Step 6: Emit SUCCEEDED event
        await self._event_bus.publish(
            UserTokenRotationSucceeded(
                event_id=uuid4(),
                occurred_at=datetime.now(UTC),
                user_id=cmd.user_id,
                triggered_by=cmd.triggered_by,
                previous_version=previous_version,
                new_version=user.min_token_version,
                reason=cmd.reason,
            )
        )

        # Step 7: Return success
        return Success(
            value=UserRotationResult(
                user_id=cmd.user_id,
                previous_version=previous_version,
                new_version=user.min_token_version,
            )
        )
