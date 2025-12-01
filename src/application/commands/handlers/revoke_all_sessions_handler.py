"""Revoke all sessions handler.

Flow:
1. Revoke all sessions in database (bulk update)
2. Clear all sessions from cache
3. Publish AllSessionsRevoked event
4. Return count of revoked sessions

Used for:
- Password change (revoke all except current)
- Security events (revoke all)
- User-initiated "logout everywhere"

Architecture:
- Application layer ONLY imports from domain layer (entities, protocols, events)
- NO infrastructure imports (repositories are injected via protocols)
"""

from datetime import UTC, datetime
from uuid_extensions import uuid7

from src.application.commands.session_commands import RevokeAllUserSessions
from src.core.result import Result, Success
from src.domain.events.session_events import AllSessionsRevokedEvent
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.session_cache import SessionCache
from src.domain.protocols.session_repository import SessionRepository


class RevokeAllSessionsHandler:
    """Handler for revoking all user sessions.

    Handles bulk session revocation for password change, security events,
    or user-initiated "logout everywhere".
    """

    def __init__(
        self,
        session_repo: SessionRepository,
        session_cache: SessionCache,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize revoke all sessions handler with dependencies.

        Args:
            session_repo: Session repository for persistence.
            session_cache: Session cache for fast lookups.
            event_bus: Event bus for publishing domain events.
        """
        self._session_repo = session_repo
        self._session_cache = session_cache
        self._event_bus = event_bus

    async def handle(self, cmd: RevokeAllUserSessions) -> Result[int, str]:
        """Handle revoke all sessions command.

        Args:
            cmd: RevokeAllUserSessions command with user_id, reason, except_session_id.

        Returns:
            Success(count) with number of sessions revoked.

        Side Effects:
            - Bulk updates sessions in database (marks revoked).
            - Clears all user sessions from cache.
            - Publishes AllSessionsRevokedEvent.
        """
        # Step 1: Revoke all sessions in database
        revoked_count = await self._session_repo.revoke_all_for_user(
            user_id=cmd.user_id,
            reason=cmd.reason,
            except_session_id=cmd.except_session_id,
        )

        # Step 2: Clear cache
        # Note: We clear all sessions for user, even the excluded one will be re-cached on next access
        await self._session_cache.delete_all_for_user(cmd.user_id)

        # Step 3: Re-cache the excluded session if present
        if cmd.except_session_id is not None:
            excluded_session = await self._session_repo.find_by_id(
                cmd.except_session_id
            )
            if excluded_session is not None and not excluded_session.is_revoked:
                await self._session_cache.set(excluded_session)

        # Step 4: Publish event
        now = datetime.now(UTC)
        await self._event_bus.publish(
            AllSessionsRevokedEvent(
                event_id=uuid7(),
                occurred_at=now,
                user_id=cmd.user_id,
                reason=cmd.reason,
                session_count=revoked_count,
                except_session_id=cmd.except_session_id,
            )
        )

        # Step 5: Return count
        return Success(value=revoked_count)
