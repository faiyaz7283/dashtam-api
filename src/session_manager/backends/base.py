"""Session backend abstract interface.

This module defines the SessionBackend interface for managing
session lifecycle (create, validate, revoke, list).
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models.base import SessionBase


class SessionBackend(ABC):
    """Abstract interface for session backend implementations.

    Backends define HOW sessions are managed (JWT-based, database-backed, etc.).

    Design Pattern:
        - Strategy Pattern: Different session management strategies
        - Open-Closed: Add new backends without modifying interface
        - Single Responsibility: Only concerns session lifecycle logic

    Implementations:
        - JWTSessionBackend: JWT refresh token based sessions
        - DatabaseSessionBackend: Traditional database-backed sessions
        - CustomBackend: Application-specific implementations
    """

    @abstractmethod
    async def create_session(
        self,
        user_id: str,
        device_info: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        **metadata,
    ) -> SessionBase:
        """Create new session.

        Args:
            user_id: User identifier
            device_info: Device/browser information
            ip_address: Client IP address
            user_agent: Full user agent string
            **metadata: Additional metadata (location, etc.)

        Returns:
            New session instance (app's concrete Session model)

        Note:
            Backend creates session domain object. Storage layer persists it.
        """
        pass

    @abstractmethod
    async def validate_session(self, session: SessionBase) -> bool:
        """Validate session is active and valid.

        Args:
            session: Session to validate

        Returns:
            True if valid, False otherwise

        Note:
            Uses SessionBase.is_active() plus backend-specific checks.
        """
        pass

    @abstractmethod
    async def revoke_session(self, session_id: str, reason: str) -> bool:
        """Revoke session.

        Args:
            session_id: Session to revoke
            reason: Revocation reason

        Returns:
            True if revoked, False if not found

        Note:
            Backend handles revocation logic. Storage layer persists change.
        """
        pass

    @abstractmethod
    async def list_sessions(self, user_id: str) -> List[SessionBase]:
        """List all sessions for user.

        Args:
            user_id: User identifier

        Returns:
            List of sessions

        Note:
            Backend may apply additional filtering beyond storage layer.
        """
        pass
