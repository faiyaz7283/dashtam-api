"""List sessions query handler.

Retrieves all sessions for a user, optionally filtering to active only.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.queries.session_queries import ListUserSessions
from src.core.result import Result, Success
from src.domain.protocols.session_repository import SessionRepository


@dataclass
class SessionListItem:
    """Individual session in list result."""

    id: UUID
    device_info: str | None
    ip_address: str | None
    location: str | None
    created_at: datetime | None
    last_activity_at: datetime | None
    expires_at: datetime | None
    is_revoked: bool
    is_current: bool


@dataclass
class SessionListResult:
    """Session list query result."""

    sessions: list[SessionListItem]
    total_count: int
    active_count: int


class ListSessionsHandler:
    """Handler for listing user sessions.

    Fetches from database (no cache for list operations).
    """

    def __init__(
        self,
        session_repo: SessionRepository,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            session_repo: Session repository for persistence.
        """
        self._session_repo = session_repo

    async def handle(self, query: ListUserSessions) -> Result[SessionListResult, str]:
        """Handle list sessions query.

        Args:
            query: ListUserSessions query with user_id and filters.

        Returns:
            Success(SessionListResult) with list of sessions.
        """
        # Fetch sessions from database
        sessions = await self._session_repo.find_by_user_id(
            user_id=query.user_id,
            active_only=query.active_only,
        )

        # Count active sessions (may differ if active_only=False)
        active_count = sum(1 for s in sessions if not s.is_revoked)

        # Map to result items
        items = [
            SessionListItem(
                id=session.id,
                device_info=session.device_info,
                ip_address=session.ip_address,
                location=session.location,
                created_at=session.created_at,
                last_activity_at=session.last_activity_at,
                expires_at=session.expires_at,
                is_revoked=session.is_revoked,
                is_current=session.id == query.current_session_id,
            )
            for session in sessions
        ]

        return Success(
            value=SessionListResult(
                sessions=items,
                total_count=len(items),
                active_count=active_count,
            )
        )
