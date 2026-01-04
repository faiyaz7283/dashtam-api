"""DisconnectProvider command handler.

Handles provider disconnection requests. Transitions connection to
DISCONNECTED status and clears credentials.

Architecture:
- Application layer handler (orchestrates business logic)
- Imports only from domain layer (entities, protocols, events)
- Uses Result types for error handling
- Emits 3-state domain events (Attempted → Succeeded/Failed)

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/provider-domain-model.md
"""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from uuid_extensions import uuid7

from src.application.commands.provider_commands import DisconnectProvider
from src.core.result import Failure, Result, Success
from src.domain.events.provider_events import (
    ProviderDisconnectionAttempted,
    ProviderDisconnectionFailed,
    ProviderDisconnectionSucceeded,
)
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)


class DisconnectProviderError:
    """DisconnectProvider-specific errors."""

    CONNECTION_NOT_FOUND = "Connection not found"
    NOT_OWNED_BY_USER = "Connection not owned by user"
    DATABASE_ERROR = "Database error occurred"


class DisconnectProviderHandler:
    """Handler for DisconnectProvider command.

    Disconnects a provider connection by transitioning to DISCONNECTED
    status. Connection record is kept for audit trail.

    Dependencies (injected via constructor):
        - ProviderConnectionRepository: For persistence
        - EventBusProtocol: For domain events
    """

    def __init__(
        self,
        connection_repo: ProviderConnectionRepository,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            connection_repo: Provider connection repository.
            event_bus: Event bus for publishing domain events.
        """
        self._connection_repo = connection_repo
        self._event_bus = event_bus

    async def handle(self, cmd: DisconnectProvider) -> Result[None, str]:
        """Handle DisconnectProvider command.

        Finds the connection, verifies ownership, and transitions to
        DISCONNECTED status. Credentials are cleared.

        Args:
            cmd: DisconnectProvider command with user and connection IDs.

        Returns:
            Success(None): Connection disconnected successfully.
            Failure(error): Connection not found, not owned, or database error.

        Side Effects:
            - Publishes ProviderDisconnectionAttempted event (always)
            - Publishes ProviderDisconnectionSucceeded event (on success)
            - Publishes ProviderDisconnectionFailed event (on failure)
            - Updates ProviderConnection in database (on success)
        """
        # We need to fetch the connection first to get provider details for events
        connection = await self._connection_repo.find_by_id(cmd.connection_id)

        # Use placeholders if connection not found (for event emission)
        provider_id = connection.provider_id if connection else cmd.connection_id
        provider_slug = connection.provider_slug if connection else "unknown"

        # Step 1: Emit ATTEMPTED event
        await self._event_bus.publish(
            ProviderDisconnectionAttempted(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                user_id=cmd.user_id,
                connection_id=cmd.connection_id,
                provider_id=provider_id,
                provider_slug=provider_slug,
            )
        )

        try:
            # Step 2: Verify connection exists
            if connection is None:
                await self._emit_failed(
                    cmd,
                    provider_id,
                    provider_slug,
                    DisconnectProviderError.CONNECTION_NOT_FOUND,
                )
                return cast(Result[None, str], Failure(error=DisconnectProviderError.CONNECTION_NOT_FOUND))

            # Step 3: Verify ownership
            if connection.user_id != cmd.user_id:
                await self._emit_failed(
                    cmd,
                    connection.provider_id,
                    connection.provider_slug,
                    DisconnectProviderError.NOT_OWNED_BY_USER,
                )
                return cast(Result[None, str], Failure(error=DisconnectProviderError.NOT_OWNED_BY_USER))

            # Step 4: Transition to DISCONNECTED
            # mark_disconnected() always succeeds (any state → DISCONNECTED)
            connection.mark_disconnected()

            # Step 5: Save to database
            await self._connection_repo.save(connection)

            # Step 6: Emit SUCCEEDED event
            await self._event_bus.publish(
                ProviderDisconnectionSucceeded(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    user_id=cmd.user_id,
                    connection_id=cmd.connection_id,
                    provider_id=connection.provider_id,
                    provider_slug=connection.provider_slug,
                )
            )

            return Success(value=None)

        except Exception as e:
            # Catch-all for database errors
            error_msg = f"{DisconnectProviderError.DATABASE_ERROR}: {str(e)}"
            await self._emit_failed(cmd, provider_id, provider_slug, error_msg)
            return cast(Result[None, str], Failure(error=error_msg))

    async def _emit_failed(
        self,
        cmd: DisconnectProvider,
        provider_id: UUID,
        provider_slug: str,
        reason: str,
    ) -> None:
        """Emit ProviderDisconnectionFailed event.

        Args:
            cmd: Original command.
            provider_id: Provider UUID.
            provider_slug: Provider slug for logging.
            reason: Failure reason.
        """
        await self._event_bus.publish(
            ProviderDisconnectionFailed(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                user_id=cmd.user_id,
                connection_id=cmd.connection_id,
                provider_id=provider_id,
                provider_slug=provider_slug,
                reason=reason,
            )
        )
