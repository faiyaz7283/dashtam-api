"""Session cache protocol for fast session lookups.

This module defines the port (interface) for session caching.
Infrastructure layer implements with Redis for <5ms lookups.

Reference:
    - docs/architecture/session-management-architecture.md
"""

from typing import Protocol
from uuid import UUID

from src.domain.protocols.session_repository import SessionData


class SessionCache(Protocol):
    """Session cache protocol (port) for fast lookups.

    Provides <5ms session lookups via Redis caching.
    Acts as write-through cache: writes go to both cache and database.

    Cache Strategy:
        - Session data cached on creation
        - Cache invalidated on revocation/update
        - TTL matches session expiration
        - Database is source of truth

    Key Patterns:
        - session:{session_id} -> SessionData
        - user:{user_id}:sessions -> Set of session IDs
        - session:{session_id}:validation -> Quick validation data

    Example:
        >>> class RedisSessionCache:
        ...     async def get(self, session_id: UUID) -> SessionData | None:
        ...         # Look up in Redis
        ...         ...
        ...     async def set(self, session_data: SessionData) -> None:
        ...         # Store in Redis with TTL
        ...         ...
    """

    async def get(self, session_id: UUID) -> SessionData | None:
        """Get session data from cache.

        Args:
            session_id: Session identifier.

        Returns:
            SessionData if cached, None otherwise.
        """
        ...

    async def set(
        self,
        session_data: SessionData,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store session data in cache.

        Args:
            session_data: Session data to cache.
            ttl_seconds: Cache TTL in seconds. If None, calculates from
                session expires_at. Defaults to 30 days if no expiry.
        """
        ...

    async def delete(self, session_id: UUID) -> bool:
        """Remove session from cache.

        Called when session is revoked or expired.

        Args:
            session_id: Session identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def delete_all_for_user(self, user_id: UUID) -> int:
        """Remove all sessions for a user from cache.

        Called when all sessions are revoked (e.g., password change).

        Args:
            user_id: User identifier.

        Returns:
            Number of sessions removed from cache.
        """
        ...

    async def exists(self, session_id: UUID) -> bool:
        """Check if session exists in cache (quick validation).

        Faster than full get() when only existence check needed.

        Args:
            session_id: Session identifier.

        Returns:
            True if session exists in cache, False otherwise.
        """
        ...

    async def get_user_session_ids(self, user_id: UUID) -> list[UUID]:
        """Get all session IDs for a user from cache.

        Args:
            user_id: User identifier.

        Returns:
            List of session IDs, empty if none cached.
        """
        ...

    async def add_user_session(self, user_id: UUID, session_id: UUID) -> None:
        """Add session ID to user's session set.

        Called when new session created. Maintains reverse index.

        Args:
            user_id: User identifier.
            session_id: Session identifier.
        """
        ...

    async def remove_user_session(self, user_id: UUID, session_id: UUID) -> None:
        """Remove session ID from user's session set.

        Called when session revoked/deleted.

        Args:
            user_id: User identifier.
            session_id: Session identifier.
        """
        ...

    async def update_last_activity(
        self,
        session_id: UUID,
        ip_address: str | None = None,
    ) -> bool:
        """Update session's last activity in cache.

        Lightweight update for activity tracking.

        Args:
            session_id: Session identifier.
            ip_address: Current IP address (optional).

        Returns:
            True if updated, False if session not in cache.
        """
        ...
