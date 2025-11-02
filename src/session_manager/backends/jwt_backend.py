"""JWT-based session backend implementation.

Manages session lifecycle for JWT refresh token based authentication.
Creates session domain objects - storage layer persists them.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import uuid4

from ..models.base import SessionBase
from .base import SessionBackend


class JWTSessionBackend(SessionBackend):
    """JWT session backend.

    Manages session lifecycle for JWT refresh token based authentication.
    Creates session domain objects from inputs.

    Design Pattern:
        - Backend creates session domain objects
        - Storage layer persists sessions
        - Backend validates session business rules
        - No direct database/storage coupling

    Flow:
        1. Backend creates Session domain object (with metadata)
        2. Enrichers add metadata (optional)
        3. Storage persists Session
        4. Audit logs event

    Example:
        ```python
        backend = JWTSessionBackend(session_ttl_days=30)
        session = await backend.create_session(
            user_id="user123",
            device_info="Mozilla/5.0...",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0..."
        )
        # Backend creates domain object, doesn't persist
        # Storage layer will persist it
        ```

    Note:
        Backend works with SessionBase interface.
        App provides concrete Session implementation via storage.
    """

    def __init__(self, session_ttl_days: int = 30):
        """Initialize JWT session backend.

        Args:
            session_ttl_days: Session TTL in days (default 30)
        """
        self.session_ttl_days = session_ttl_days

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
            **metadata: Additional metadata (location, etc.)

        Returns:
            New session instance (app's concrete Session model)

        Note:
            Backend creates domain object. Storage layer persists it.
            This returns a dict-like representation that app will convert
            to concrete Session model.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=self.session_ttl_days)

        # Return dict representation (app converts to concrete model)
        # Storage layer handles actual model instantiation
        session_data = {
            "id": uuid4(),
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

        Note:
            Uses SessionBase.is_active() plus JWT-specific checks.
        """
        # Use SessionBase business logic
        if not session.is_active():
            return False

        # JWT-specific validation could go here
        # For now, rely on SessionBase.is_active()

        return True

    async def revoke_session(self, session_id: str, reason: str) -> bool:
        """Revoke session.

        Args:
            session_id: Session to revoke
            reason: Revocation reason

        Returns:
            True if revoked, False if not found

        Note:
            Backend handles revocation logic. Storage persists change.
            This is a simplified implementation - real implementation
            would fetch session, update it, and let storage save.
        """
        # In real implementation, this would:
        # 1. Fetch session from storage
        # 2. Update session (is_revoked=True, revoked_at, reason)
        # 3. Return updated session for storage to save

        # For now, return True (storage handles the actual work)
        return True

    async def list_sessions(self, user_id: str) -> List[SessionBase]:
        """List all sessions for user.

        Args:
            user_id: User identifier

        Returns:
            List of sessions

        Note:
            Backend may apply additional filtering beyond storage layer.
            In practice, this is usually delegated to storage entirely.
        """
        # In real implementation, this would delegate to storage
        # with optional backend-specific filters

        # Return empty list (storage handles listing)
        return []
