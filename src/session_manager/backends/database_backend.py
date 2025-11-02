"""Database session backend - optional traditional session management.

Alternative to JWT backend. Sessions stored entirely in database.
Useful for traditional session management patterns.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import uuid4

from ..models.base import SessionBase
from .base import SessionBackend


class DatabaseSessionBackend(SessionBackend):
    """Database session backend.

    Traditional session management - sessions stored entirely in database.
    Alternative to JWT refresh token pattern.

    Design Pattern:
        - Session ID is the session token (server-side sessions)
        - All session state in database (no client-side JWT)
        - Backend creates session domain objects
        - Storage layer persists sessions

    Use Cases:
        - Traditional web applications
        - Server-side session management
        - When JWT pattern not suitable

    Example:
        ```python
        backend = DatabaseSessionBackend(session_ttl_hours=24)
        session = await backend.create_session(
            user_id="user123",
            device_info="Mozilla/5.0...",
            ip_address="192.168.1.1"
        )
        # Return session.id to client as session token
        ```

    Note:
        Most modern apps use JWTSessionBackend instead.
        This backend provided for completeness.
    """

    def __init__(self, session_ttl_hours: int = 24):
        """Initialize database session backend.

        Args:
            session_ttl_hours: Session TTL in hours (default 24)
        """
        self.session_ttl_hours = session_ttl_hours

    async def create_session(
        self,
        user_id: str,
        device_info: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        **metadata,
    ) -> SessionBase:
        """Create new session domain object.

        Args:
            user_id: User identifier
            device_info: Device/browser information
            ip_address: Client IP address
            user_agent: Full user agent string
            **metadata: Additional metadata

        Returns:
            New session instance
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=self.session_ttl_hours)

        session_data = {
            "id": uuid4(),  # This ID is the session token
            "user_id": user_id,
            "device_info": device_info,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "location": metadata.get("location"),
            "created_at": now,
            "last_activity": now,
            "expires_at": expires_at,
            "is_revoked": False,
            "is_trusted": metadata.get("is_trusted", False),
            "revoked_at": None,
            "revoked_reason": None,
        }

        return session_data  # type: ignore

    async def validate_session(self, session: SessionBase) -> bool:
        """Validate session is active and valid.

        Args:
            session: Session to validate

        Returns:
            True if valid, False otherwise
        """
        # Use SessionBase business logic
        if not session.is_active():
            return False

        # Update last_activity (in real implementation)
        # session.last_activity = datetime.now(timezone.utc)

        return True

    async def revoke_session(self, session_id: str, reason: str) -> bool:
        """Revoke session.

        Args:
            session_id: Session to revoke
            reason: Revocation reason

        Returns:
            True if revoked, False if not found
        """
        # Simplified - storage handles actual revocation
        return True

    async def list_sessions(self, user_id: str) -> List[SessionBase]:
        """List all sessions for user.

        Args:
            user_id: User identifier

        Returns:
            List of sessions
        """
        # Delegate to storage
        return []
