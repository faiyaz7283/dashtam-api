"""Revoke session handler.

Flow:
1. Find session by ID
2. Verify ownership (user_id matches)
3. Mark session as revoked
4. Update database
5. Remove from cache
6. Publish SessionRevoked event
7. Return success

Architecture:
- Application layer ONLY imports from domain layer (entities, protocols, events)
- NO infrastructure imports (repositories are injected via protocols)
"""

from datetime import UTC, datetime
from uuid import UUID
from uuid_extensions import uuid7

from src.application.commands.session_commands import RevokeSession
from src.core.result import Failure, Result, Success
from src.domain.events.session_events import (
    SessionRevocationAttempted,
    SessionRevokedEvent,
    SessionRevocationFailed,
)
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.session_cache_protocol import SessionCache
from src.domain.protocols.session_repository import SessionRepository


class RevokeSessionError:
    """Revoke session error reasons."""

    SESSION_NOT_FOUND = "session_not_found"
    NOT_OWNER = "not_session_owner"
    ALREADY_REVOKED = "session_already_revoked"


class RevokeSessionHandler:
    """Handler for session revocation command.

    Handles single session revocation (logout, manual revoke).
    """

    def __init__(
        self,
        session_repo: SessionRepository,
        session_cache: SessionCache,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize revoke session handler with dependencies.

        Args:
            session_repo: Session repository for persistence.
            session_cache: Session cache for fast lookups.
            event_bus: Event bus for publishing domain events.
        """
        self._session_repo = session_repo
        self._session_cache = session_cache
        self._event_bus = event_bus

    async def handle(self, cmd: RevokeSession) -> Result[UUID, str]:
        """Handle revoke session command.

        Args:
            cmd: RevokeSession command with session_id, user_id, reason.

        Returns:
            Success(session_id) on successful revocation.
            Failure(error_message) on failure.

        Side Effects:
            - Updates session in database (marks revoked).
            - Removes session from cache.
            - Publishes 3-state events (Attempted/Succeeded/Failed).
        """
        now = datetime.now(UTC)

        # Step 1: Emit ATTEMPTED event
        await self._event_bus.publish(
            SessionRevocationAttempted(
                event_id=uuid7(),
                occurred_at=now,
                session_id=cmd.session_id,
                user_id=cmd.user_id,
                reason=cmd.reason,
            )
        )

        # Step 2: Find session
        session = await self._session_repo.find_by_id(cmd.session_id)
        if session is None:
            await self._event_bus.publish(
                SessionRevocationFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    session_id=cmd.session_id,
                    user_id=cmd.user_id,
                    reason=cmd.reason,
                    failure_reason=RevokeSessionError.SESSION_NOT_FOUND,
                )
            )
            return Failure(error=RevokeSessionError.SESSION_NOT_FOUND)

        # Step 3: Verify ownership
        if session.user_id != cmd.user_id:
            await self._event_bus.publish(
                SessionRevocationFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    session_id=cmd.session_id,
                    user_id=cmd.user_id,
                    reason=cmd.reason,
                    failure_reason=RevokeSessionError.NOT_OWNER,
                )
            )
            return Failure(error=RevokeSessionError.NOT_OWNER)

        # Step 4: Check not already revoked
        if session.is_revoked:
            await self._event_bus.publish(
                SessionRevocationFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    session_id=cmd.session_id,
                    user_id=cmd.user_id,
                    reason=cmd.reason,
                    failure_reason=RevokeSessionError.ALREADY_REVOKED,
                )
            )
            return Failure(error=RevokeSessionError.ALREADY_REVOKED)

        # Step 5: Mark as revoked
        revoked_at = datetime.now(UTC)
        session.is_revoked = True
        session.revoked_at = revoked_at
        session.revoked_reason = cmd.reason

        # Step 6: Update database
        await self._session_repo.save(session)

        # Step 7: Remove from cache
        await self._session_cache.delete(cmd.session_id)
        await self._session_cache.remove_user_session(cmd.user_id, cmd.session_id)

        # Step 8: Emit SUCCEEDED event
        await self._event_bus.publish(
            SessionRevokedEvent(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                session_id=cmd.session_id,
                user_id=cmd.user_id,
                reason=cmd.reason,
                device_info=session.device_info,
            )
        )

        # Step 9: Return success
        return Success(value=cmd.session_id)
