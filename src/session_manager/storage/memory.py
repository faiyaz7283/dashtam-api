"""In-memory session storage implementation.

Concrete implementation using Python dict with TTL tracking.
No external dependencies - useful for testing and development.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..models.base import SessionBase
from ..models.filters import SessionFilters
from .base import SessionStorage


class MemorySessionStorage(SessionStorage):
    """In-memory dict storage with TTL.

    Concrete implementation with no external dependencies.
    Sessions stored in memory - lost on restart.

    Design Pattern:
        - Concrete implementation (no abstraction needed)
        - No external dependencies (pure Python)
        - TTL-based automatic cleanup
        - Useful for testing and development

    Usage:
        ```python
        storage = MemorySessionStorage()
        await storage.save_session(session)
        ```

    Note:
        Not suitable for production with multiple processes/servers.
        Sessions lost on restart. Use DatabaseSessionStorage for production.
    """

    def __init__(self):
        """Initialize in-memory storage."""
        self._sessions: Dict[str, SessionBase] = {}

    def _cleanup_expired(self) -> None:
        """Remove expired sessions from memory.

        Called automatically during operations.
        """
        now = datetime.now(timezone.utc)
        expired_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.expires_at and session.expires_at < now
        ]

        for session_id in expired_ids:
            del self._sessions[session_id]

    async def save_session(self, session: SessionBase) -> None:
        """Store session in memory.

        Args:
            session: Session to save
        """
        self._cleanup_expired()
        self._sessions[str(session.id)] = session

    async def get_session(self, session_id: str) -> Optional[SessionBase]:
        """Retrieve session from memory.

        Args:
            session_id: Session identifier

        Returns:
            Session or None if not found or expired
        """
        self._cleanup_expired()
        session = self._sessions.get(session_id)

        # Check if expired
        if session and session.expires_at:
            if datetime.now(timezone.utc) > session.expires_at:
                del self._sessions[session_id]
                return None

        return session

    async def list_sessions(
        self, user_id: str, filters: Optional[SessionFilters] = None
    ) -> List[SessionBase]:
        """List sessions for user with optional filters.

        Args:
            user_id: User identifier
            filters: Optional filters

        Returns:
            List of sessions
        """
        self._cleanup_expired()

        # Get all sessions for user
        sessions = [s for s in self._sessions.values() if s.user_id == user_id]

        # Apply filters if provided
        if filters:
            if filters.active_only:
                now = datetime.now(timezone.utc)
                sessions = [
                    s
                    for s in sessions
                    if not s.is_revoked and (not s.expires_at or s.expires_at > now)
                ]

            if filters.device_type:
                sessions = [
                    s
                    for s in sessions
                    if s.device_info and filters.device_type in s.device_info
                ]

            if filters.ip_address:
                sessions = [s for s in sessions if s.ip_address == filters.ip_address]

            if filters.location:
                sessions = [
                    s for s in sessions if s.location and filters.location in s.location
                ]

            if filters.created_after:
                sessions = [
                    s for s in sessions if s.created_at >= filters.created_after
                ]

            if filters.created_before:
                sessions = [
                    s for s in sessions if s.created_at <= filters.created_before
                ]

            if filters.is_trusted is not None:
                sessions = [s for s in sessions if s.is_trusted == filters.is_trusted]

        # Sort by most recent first
        sessions.sort(key=lambda s: s.created_at, reverse=True)

        # Apply pagination (offset + limit)
        if filters:
            offset = filters.offset or 0
            limit = filters.limit

            # Apply offset
            if offset > 0:
                sessions = sessions[offset:]

            # Apply limit
            if limit and limit > 0:
                sessions = sessions[:limit]

        return sessions

    async def revoke_session(self, session_id: str, reason: str) -> bool:
        """Mark session as revoked.

        Args:
            session_id: Session to revoke
            reason: Revocation reason

        Returns:
            True if revoked, False if not found
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        session.is_revoked = True
        session.revoked_at = datetime.now(timezone.utc)
        session.revoked_reason = reason

        return True

    async def delete_session(self, session_id: str) -> bool:
        """Permanently delete session from memory.

        Args:
            session_id: Session to delete

        Returns:
            True if deleted, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def clear_all(self) -> None:
        """Clear all sessions from memory.

        Useful for testing.
        """
        self._sessions.clear()

    def session_count(self) -> int:
        """Get total number of sessions in memory.

        Returns:
            Number of sessions

        Note:
            Includes expired sessions. Call _cleanup_expired() first for accurate count.
        """
        return len(self._sessions)
