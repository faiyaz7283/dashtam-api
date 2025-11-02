"""Unit tests for JWTSessionBackend.

Tests JWT session backend without external dependencies.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.session_manager.backends.jwt_backend import JWTSessionBackend
from src.session_manager.tests.fixtures.mock_models import MockSession


@pytest.mark.asyncio
class TestJWTSessionBackend:
    """Test JWTSessionBackend session lifecycle."""

    async def test_init_default_ttl(self):
        """Test initialization with default TTL."""
        backend = JWTSessionBackend()

        assert backend.session_ttl_days == 30

    async def test_init_custom_ttl(self):
        """Test initialization with custom TTL."""
        backend = JWTSessionBackend(session_ttl_days=60)

        assert backend.session_ttl_days == 60

    async def test_create_session_basic(self):
        """Test creating a session with basic information."""
        backend = JWTSessionBackend(session_ttl_days=30)

        session_data = await backend.create_session(
            user_id="user-123",
            device_info="Chrome on macOS",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        )

        # Verify all required fields are present
        assert session_data["id"] is not None
        assert session_data["user_id"] == "user-123"
        assert session_data["device_info"] == "Chrome on macOS"
        assert session_data["ip_address"] == "192.168.1.100"
        assert (
            session_data["user_agent"]
            == "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        )
        assert session_data["is_revoked"] is False
        assert session_data["is_trusted"] is False
        assert session_data["revoked_at"] is None
        assert session_data["revoked_reason"] is None

    async def test_create_session_timestamps(self):
        """Test that created_at, last_activity, and expires_at are set correctly."""
        backend = JWTSessionBackend(session_ttl_days=30)

        before = datetime.now(timezone.utc)
        session_data = await backend.create_session(
            user_id="user-123",
            device_info="Test Device",
            ip_address="192.168.1.1",
        )
        after = datetime.now(timezone.utc)

        # created_at and last_activity should be within test window
        assert before <= session_data["created_at"] <= after
        assert before <= session_data["last_activity"] <= after

        # expires_at should be 30 days from created_at
        expected_expiry = session_data["created_at"] + timedelta(days=30)
        assert session_data["expires_at"] == expected_expiry

    async def test_create_session_with_metadata(self):
        """Test creating session with additional metadata."""
        backend = JWTSessionBackend()

        session_data = await backend.create_session(
            user_id="user-123",
            device_info="Test Device",
            ip_address="192.168.1.1",
            location="San Francisco, USA",
            is_trusted=True,
        )

        assert session_data["location"] == "San Francisco, USA"
        assert session_data["is_trusted"] is True

    async def test_create_session_without_user_agent(self):
        """Test creating session without user_agent (optional)."""
        backend = JWTSessionBackend()

        session_data = await backend.create_session(
            user_id="user-123",
            device_info="Test Device",
            ip_address="192.168.1.1",
        )

        assert session_data["user_agent"] is None

    async def test_validate_session_active(self):
        """Test validating an active session."""
        backend = JWTSessionBackend()

        # Create active session
        active_session = MockSession(user_id="user-123", is_revoked=False)

        result = await backend.validate_session(active_session)

        assert result is True

    async def test_validate_session_revoked(self):
        """Test validating a revoked session."""
        backend = JWTSessionBackend()

        # Create revoked session
        revoked_session = MockSession(user_id="user-123", is_revoked=True)

        result = await backend.validate_session(revoked_session)

        assert result is False

    async def test_validate_session_expired(self):
        """Test validating an expired session."""
        backend = JWTSessionBackend()

        # Create expired session
        expired_session = MockSession(
            user_id="user-123",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        result = await backend.validate_session(expired_session)

        assert result is False

    async def test_revoke_session(self):
        """Test revoking a session (simplified implementation)."""
        backend = JWTSessionBackend()

        # Current implementation always returns True
        # (actual revocation handled by storage layer)
        result = await backend.revoke_session("session-id-123", reason="user_logout")

        assert result is True

    async def test_list_sessions(self):
        """Test listing sessions (simplified implementation)."""
        backend = JWTSessionBackend()

        # Current implementation returns empty list
        # (actual listing handled by storage layer)
        sessions = await backend.list_sessions("user-123")

        assert sessions == []

    async def test_create_session_custom_ttl(self):
        """Test session creation with custom TTL."""
        backend = JWTSessionBackend(session_ttl_days=7)

        session_data = await backend.create_session(
            user_id="user-123",
            device_info="Test Device",
            ip_address="192.168.1.1",
        )

        # Verify expires_at is 7 days from created_at
        expected_expiry = session_data["created_at"] + timedelta(days=7)
        assert session_data["expires_at"] == expected_expiry

    async def test_create_session_unique_ids(self):
        """Test that each created session has a unique ID."""
        backend = JWTSessionBackend()

        session1 = await backend.create_session(
            user_id="user-123",
            device_info="Device 1",
            ip_address="192.168.1.1",
        )

        session2 = await backend.create_session(
            user_id="user-123",
            device_info="Device 2",
            ip_address="192.168.1.2",
        )

        # IDs should be different
        assert session1["id"] != session2["id"]
