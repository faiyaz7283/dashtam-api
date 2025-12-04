"""Get session query handler.

Retrieves a single session by ID with authorization check.
Uses cache-first strategy for performance.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.queries.session_queries import GetSession
from src.core.result import Failure, Result, Success
from src.domain.protocols.session_cache_protocol import SessionCache
from src.domain.protocols.session_repository import SessionRepository


class GetSessionError:
    """Get session error reasons."""

    SESSION_NOT_FOUND = "session_not_found"
    NOT_OWNER = "not_session_owner"


@dataclass
class SessionResult:
    """Session query result."""

    id: UUID
    user_id: UUID
    device_info: str | None
    ip_address: str | None
    location: str | None
    created_at: datetime | None
    last_activity_at: datetime | None
    expires_at: datetime | None
    is_revoked: bool
    is_current: bool = False


class GetSessionHandler:
    """Handler for getting a single session.

    Uses cache-first strategy:
    1. Try cache
    2. Fall back to database
    3. Populate cache on miss
    """

    def __init__(
        self,
        session_repo: SessionRepository,
        session_cache: SessionCache,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            session_repo: Session repository for persistence.
            session_cache: Session cache for fast lookups.
        """
        self._session_repo = session_repo
        self._session_cache = session_cache

    async def handle(self, query: GetSession) -> Result[SessionResult, str]:
        """Handle get session query.

        Args:
            query: GetSession query with session_id and user_id.

        Returns:
            Success(SessionResult) with session data.
            Failure(error_message) if not found or not owner.
        """
        # Step 1: Try cache first
        session = await self._session_cache.get(query.session_id)

        # Step 2: Fall back to database
        if session is None:
            session = await self._session_repo.find_by_id(query.session_id)

            # Populate cache on miss (if found and not revoked)
            if session is not None and not session.is_revoked:
                await self._session_cache.set(session)

        # Step 3: Check found
        if session is None:
            return Failure(error=GetSessionError.SESSION_NOT_FOUND)

        # Step 4: Check ownership
        if session.user_id != query.user_id:
            return Failure(error=GetSessionError.NOT_OWNER)

        # Step 5: Return result
        return Success(
            value=SessionResult(
                id=session.id,
                user_id=session.user_id,
                device_info=session.device_info,
                ip_address=session.ip_address,
                location=session.location,
                created_at=session.created_at,
                last_activity_at=session.last_activity_at,
                expires_at=session.expires_at,
                is_revoked=session.is_revoked,
                is_current=False,  # Caller sets this
            )
        )
