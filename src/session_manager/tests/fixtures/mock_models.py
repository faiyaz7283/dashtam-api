"""Mock models for session manager package testing.

These are test doubles that implement the package interfaces without
any real database dependencies. Used for isolated unit testing.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

from src.session_manager.models.base import SessionBase


class MockSession(SessionBase):
    """Mock Session model for testing (implements SessionBase).

    This is a simple in-memory implementation with no database dependencies.
    Used for unit testing package components in isolation.
    """

    def __init__(
        self,
        id: Optional[UUID] = None,
        user_id: str = "test-user",
        device_info: Optional[str] = "Test Device",
        ip_address: Optional[str] = "127.0.0.1",
        user_agent: Optional[str] = "Test/1.0",
        location: Optional[str] = None,
        created_at: Optional[datetime] = None,
        last_activity: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        is_revoked: bool = False,
        is_trusted: bool = False,
        revoked_at: Optional[datetime] = None,
        revoked_reason: Optional[str] = None,
    ):
        """Initialize mock session with test data."""
        self.id = id or uuid4()
        self.user_id = user_id
        self.device_info = device_info
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.location = location
        self.created_at = created_at or datetime.now(timezone.utc)
        self.last_activity = last_activity
        self.expires_at = expires_at or (self.created_at + timedelta(days=30))
        self.is_revoked = is_revoked
        self.is_trusted = is_trusted
        self.revoked_at = revoked_at
        self.revoked_reason = revoked_reason

    def is_session_active(self) -> bool:
        """Check if session is active (delegates to SessionBase)."""
        return super().is_session_active()


class MockAuditLog:
    """Mock audit log model for testing.

    Simple in-memory audit log without database dependencies.
    """

    def __init__(
        self,
        id: Optional[UUID] = None,
        event_type: str = "session_created",
        session_id: Optional[UUID] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        """Initialize mock audit log."""
        self.id = id or uuid4()
        self.event_type = event_type
        self.session_id = session_id
        self.user_id = user_id
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.details = details
        self.created_at = created_at or datetime.now(timezone.utc)
