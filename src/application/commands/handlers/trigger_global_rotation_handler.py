"""Handler for TriggerGlobalTokenRotation command.

Flow:
1. Emit GlobalTokenRotationAttempted event
2. Get current security config
3. Increment global_min_token_version
4. Update security config with new version and reason
5. Emit GlobalTokenRotationSucceeded event
6. Return Success(GlobalRotationResult)

On failure:
- Emit GlobalTokenRotationFailed event
- Return Failure(error)
"""

from datetime import UTC, datetime
from uuid_extensions import uuid7

from src.application.commands.rotation_commands import (
    GlobalRotationResult,
    TriggerGlobalTokenRotation,
)
from src.core.result import Failure, Result, Success
from src.domain.events.auth_events import (
    GlobalTokenRotationAttempted,
    GlobalTokenRotationFailed,
    GlobalTokenRotationSucceeded,
)
from src.domain.protocols import SecurityConfigRepository
from src.domain.protocols.event_bus_protocol import EventBusProtocol


class TriggerGlobalTokenRotationHandler:
    """Handler for global token rotation command.

    Increments the global minimum token version, which causes all
    existing refresh tokens with lower versions to fail validation.

    This is an admin-only operation typically used during:
    - Security incidents (database breach)
    - Compliance requirements
    - Token generation vulnerabilities
    """

    def __init__(
        self,
        security_config_repo: SecurityConfigRepository,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            security_config_repo: Security config repository.
            event_bus: Event bus for publishing domain events.
        """
        self._security_config_repo = security_config_repo
        self._event_bus = event_bus

    async def handle(
        self,
        cmd: TriggerGlobalTokenRotation,
    ) -> Result[GlobalRotationResult, str]:
        """Handle global token rotation command.

        Args:
            cmd: TriggerGlobalTokenRotation command.

        Returns:
            Success(GlobalRotationResult) on success.
            Failure(error) on failure.
        """
        # Step 1: Emit ATTEMPTED event
        await self._event_bus.publish(
            GlobalTokenRotationAttempted(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                triggered_by=cmd.triggered_by,
                reason=cmd.reason,
            )
        )

        try:
            # Step 2: Get current security config
            config = await self._security_config_repo.get_or_create_default()
            previous_version = config.global_min_token_version

            # Step 3-4: Increment version and update
            new_version = previous_version + 1
            rotation_time = datetime.now(UTC)

            updated_config = await self._security_config_repo.update_global_version(
                new_version=new_version,
                reason=cmd.reason,
                rotation_time=rotation_time,
            )

            # Step 5: Emit SUCCEEDED event
            await self._event_bus.publish(
                GlobalTokenRotationSucceeded(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    triggered_by=cmd.triggered_by,
                    previous_version=previous_version,
                    new_version=new_version,
                    reason=cmd.reason,
                    grace_period_seconds=updated_config.grace_period_seconds,
                )
            )

            # Step 6: Return success
            return Success(
                value=GlobalRotationResult(
                    previous_version=previous_version,
                    new_version=new_version,
                    grace_period_seconds=updated_config.grace_period_seconds,
                )
            )

        except Exception as e:
            # Emit FAILED event
            await self._event_bus.publish(
                GlobalTokenRotationFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    triggered_by=cmd.triggered_by,
                    reason=cmd.reason,
                    failure_reason=str(e),
                )
            )
            return Failure(error=f"rotation_failed: {e!s}")
