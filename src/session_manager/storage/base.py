"""Session storage abstract interface.

This module defines the SessionStorage interface that all storage
implementations must follow (database, cache, memory).
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models.base import SessionBase
from ..models.filters import SessionFilters


class SessionStorage(ABC):
    """Abstract interface for session storage implementations.

    All storage backends (database, cache, memory) must implement this interface.

    Design Pattern:
        - Open-Closed Principle: Add new storage without modifying this interface
        - Liskov Substitution: All implementations are interchangeable
        - Dependency Inversion: High-level code depends on this abstraction

    Implementations:
        - DatabaseSessionStorage: Works with any SQLAlchemy AsyncSession
        - CacheSessionStorage: Works with any cache client (Redis, Memcached)
        - MemorySessionStorage: In-memory dict with TTL
    """

    @abstractmethod
    async def save_session(self, session: SessionBase) -> None:
        """Persist session to storage.

        Args:
            session: Session instance to save (app's concrete Session model)

        Raises:
            StorageError: If save operation fails
        """
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[SessionBase]:
        """Retrieve session by ID.

        Args:
            session_id: Session identifier

        Returns:
            App's concrete Session model or None if not found
        """
        pass

    @abstractmethod
    async def list_sessions(
        self, user_id: str, filters: Optional[SessionFilters] = None
    ) -> List[SessionBase]:
        """List sessions with optional filters.

        Args:
            user_id: User ID to list sessions for
            filters: Optional filters (active_only, device_type, ip_address, etc.)

        Returns:
            List of app's concrete Session models
        """
        pass

    @abstractmethod
    async def revoke_session(self, session_id: str, reason: str) -> bool:
        """Mark session as revoked.

        Args:
            session_id: Session to revoke
            reason: Revocation reason (e.g., "user_logout", "security_breach")

        Returns:
            True if revoked, False if session not found
        """
        pass

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Permanently delete session.

        Args:
            session_id: Session to delete

        Returns:
            True if deleted, False if session not found
        """
        pass
