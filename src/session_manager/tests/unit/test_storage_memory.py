"""Unit tests for MemorySessionStorage.

Tests in-memory storage implementation without any external dependencies.
"""

import pytest

from src.session_manager.models.filters import SessionFilters
from src.session_manager.storage.memory import MemorySessionStorage
from src.session_manager.tests.fixtures.mock_models import MockSession


@pytest.mark.asyncio
class TestMemorySessionStorage:
    """Test MemorySessionStorage CRUD operations."""

    async def test_save_and_get_session(self):
        """Test saving and retrieving a session."""
        storage = MemorySessionStorage()
        session = MockSession(user_id="user-123")

        # Save session
        await storage.save_session(session)

        # Retrieve session
        retrieved = await storage.get_session(str(session.id))

        assert retrieved is not None
        assert retrieved.id == session.id
        assert retrieved.user_id == "user-123"

    async def test_get_nonexistent_session(self):
        """Test retrieving a session that doesn't exist."""
        storage = MemorySessionStorage()

        result = await storage.get_session("nonexistent-id")

        assert result is None

    async def test_list_sessions_by_user(self):
        """Test listing all sessions for a user."""
        storage = MemorySessionStorage()

        # Create multiple sessions for same user
        session1 = MockSession(user_id="user-123", device_info="Device 1")
        session2 = MockSession(user_id="user-123", device_info="Device 2")
        session3 = MockSession(user_id="user-456", device_info="Device 3")

        await storage.save_session(session1)
        await storage.save_session(session2)
        await storage.save_session(session3)

        # List sessions for user-123
        sessions = await storage.list_sessions("user-123")

        assert len(sessions) == 2
        assert all(s.user_id == "user-123" for s in sessions)

    async def test_list_sessions_with_filters_active_only(self):
        """Test listing sessions with active_only filter."""
        storage = MemorySessionStorage()

        # Create active and revoked sessions
        active_session = MockSession(
            user_id="user-123", device_info="Active", is_revoked=False
        )
        revoked_session = MockSession(
            user_id="user-123", device_info="Revoked", is_revoked=True
        )

        await storage.save_session(active_session)
        await storage.save_session(revoked_session)

        # Filter for active only
        filters = SessionFilters(active_only=True)
        sessions = await storage.list_sessions("user-123", filters)

        assert len(sessions) == 1
        assert sessions[0].device_info == "Active"
        assert sessions[0].is_revoked is False

    async def test_list_sessions_with_filters_device_type(self):
        """Test listing sessions filtered by device_type."""
        storage = MemorySessionStorage()

        # Create sessions with different device types
        mobile_session = MockSession(user_id="user-123", device_info="mobile device")
        desktop_session = MockSession(
            user_id="user-123", device_info="desktop computer"
        )

        await storage.save_session(mobile_session)
        await storage.save_session(desktop_session)

        # Filter by device type
        filters = SessionFilters(device_type="mobile")
        sessions = await storage.list_sessions("user-123", filters)

        assert len(sessions) == 1
        assert "mobile" in sessions[0].device_info.lower()

    async def test_revoke_session(self):
        """Test revoking a session."""
        storage = MemorySessionStorage()
        session = MockSession(user_id="user-123", is_revoked=False)

        await storage.save_session(session)

        # Revoke session
        result = await storage.revoke_session(str(session.id), reason="user_logout")

        assert result is True

        # Verify session is revoked
        retrieved = await storage.get_session(str(session.id))
        assert retrieved.is_revoked is True
        assert retrieved.revoked_reason == "user_logout"
        assert retrieved.revoked_at is not None

    async def test_revoke_nonexistent_session(self):
        """Test revoking a session that doesn't exist."""
        storage = MemorySessionStorage()

        result = await storage.revoke_session("nonexistent-id", reason="test")

        assert result is False

    async def test_delete_session(self):
        """Test deleting a session."""
        storage = MemorySessionStorage()
        session = MockSession(user_id="user-123")

        await storage.save_session(session)

        # Delete session
        result = await storage.delete_session(str(session.id))

        assert result is True

        # Verify session is deleted
        retrieved = await storage.get_session(str(session.id))
        assert retrieved is None

    async def test_delete_nonexistent_session(self):
        """Test deleting a session that doesn't exist."""
        storage = MemorySessionStorage()

        result = await storage.delete_session("nonexistent-id")

        assert result is False

    async def test_clear_all(self):
        """Test clearing all sessions from memory."""
        storage = MemorySessionStorage()

        # Create multiple sessions
        session1 = MockSession(user_id="user-123", device_info="Device 1")
        session2 = MockSession(user_id="user-123", device_info="Device 2")
        session3 = MockSession(user_id="user-456", device_info="Device 3")

        await storage.save_session(session1)
        await storage.save_session(session2)
        await storage.save_session(session3)

        # Verify sessions exist
        assert storage.session_count() == 3

        # Clear all sessions
        storage.clear_all()

        # Verify all sessions are gone
        assert storage.session_count() == 0
        assert await storage.get_session(str(session1.id)) is None
        assert await storage.get_session(str(session2.id)) is None
        assert await storage.get_session(str(session3.id)) is None

    async def test_storage_isolation(self):
        """Test that separate storage instances are isolated."""
        storage1 = MemorySessionStorage()
        storage2 = MemorySessionStorage()

        session = MockSession(user_id="user-123")

        # Save to storage1
        await storage1.save_session(session)

        # Should NOT exist in storage2 (different instance)
        retrieved = await storage2.get_session(str(session.id))
        assert retrieved is None

    async def test_session_expiration(self):
        """Test that expired sessions are automatically cleaned up."""
        from datetime import datetime, timedelta, timezone

        storage = MemorySessionStorage()

        # Create expired session
        expired_session = MockSession(
            user_id="user-123",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        await storage.save_session(expired_session)

        # Try to retrieve expired session
        retrieved = await storage.get_session(str(expired_session.id))

        # Should return None (expired)
        assert retrieved is None

    async def test_list_sessions_filter_ip_address(self):
        """Test listing sessions filtered by IP address."""
        storage = MemorySessionStorage()

        session1 = MockSession(user_id="user-123", ip_address="192.168.1.100")
        session2 = MockSession(user_id="user-123", ip_address="10.0.0.5")

        await storage.save_session(session1)
        await storage.save_session(session2)

        # Filter by IP
        filters = SessionFilters(ip_address="192.168.1.100")
        sessions = await storage.list_sessions("user-123", filters)

        assert len(sessions) == 1
        assert sessions[0].ip_address == "192.168.1.100"

    async def test_list_sessions_filter_location(self):
        """Test listing sessions filtered by location."""
        storage = MemorySessionStorage()

        session1 = MockSession(user_id="user-123", location="San Francisco, USA")
        session2 = MockSession(user_id="user-123", location="London, UK")

        await storage.save_session(session1)
        await storage.save_session(session2)

        # Filter by location (partial match)
        filters = SessionFilters(location="San Francisco")
        sessions = await storage.list_sessions("user-123", filters)

        assert len(sessions) == 1
        assert "San Francisco" in sessions[0].location

    async def test_list_sessions_filter_created_after(self):
        """Test listing sessions created after a specific time."""
        from datetime import datetime, timedelta, timezone

        storage = MemorySessionStorage()

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        session1 = MockSession(
            user_id="user-123", created_at=two_days_ago, device_info="Old"
        )
        session2 = MockSession(user_id="user-123", created_at=now, device_info="New")

        await storage.save_session(session1)
        await storage.save_session(session2)

        # Filter for sessions created after yesterday
        filters = SessionFilters(created_after=yesterday)
        sessions = await storage.list_sessions("user-123", filters)

        assert len(sessions) == 1
        assert sessions[0].device_info == "New"

    async def test_list_sessions_filter_created_before(self):
        """Test listing sessions created before a specific time."""
        from datetime import datetime, timedelta, timezone

        storage = MemorySessionStorage()

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        session1 = MockSession(
            user_id="user-123", created_at=two_days_ago, device_info="Old"
        )
        session2 = MockSession(user_id="user-123", created_at=now, device_info="New")

        await storage.save_session(session1)
        await storage.save_session(session2)

        # Filter for sessions created before yesterday
        filters = SessionFilters(created_before=yesterday)
        sessions = await storage.list_sessions("user-123", filters)

        assert len(sessions) == 1
        assert sessions[0].device_info == "Old"

    async def test_list_sessions_filter_is_trusted(self):
        """Test listing sessions filtered by is_trusted flag."""
        storage = MemorySessionStorage()

        trusted_session = MockSession(
            user_id="user-123", device_info="Trusted", is_trusted=True
        )
        untrusted_session = MockSession(
            user_id="user-123", device_info="Untrusted", is_trusted=False
        )

        await storage.save_session(trusted_session)
        await storage.save_session(untrusted_session)

        # Filter for trusted only
        filters = SessionFilters(is_trusted=True)
        sessions = await storage.list_sessions("user-123", filters)

        assert len(sessions) == 1
        assert sessions[0].is_trusted is True
        assert sessions[0].device_info == "Trusted"

    async def test_list_sessions_sorting(self):
        """Test that sessions are sorted by created_at (most recent first)."""
        from datetime import datetime, timedelta, timezone

        storage = MemorySessionStorage()

        now = datetime.now(timezone.utc)

        # Create sessions with different timestamps
        session1 = MockSession(
            user_id="user-123",
            created_at=now - timedelta(hours=3),
            device_info="Oldest",
        )
        session2 = MockSession(
            user_id="user-123",
            created_at=now - timedelta(hours=1),
            device_info="Middle",
        )
        session3 = MockSession(user_id="user-123", created_at=now, device_info="Newest")

        # Save in random order
        await storage.save_session(session2)
        await storage.save_session(session1)
        await storage.save_session(session3)

        # List sessions
        sessions = await storage.list_sessions("user-123")

        # Should be sorted newest first
        assert len(sessions) == 3
        assert sessions[0].device_info == "Newest"
        assert sessions[1].device_info == "Middle"
        assert sessions[2].device_info == "Oldest"

    async def test_list_sessions_pagination_limit(self):
        """Test pagination with limit."""
        storage = MemorySessionStorage()

        # Create 5 sessions
        for i in range(5):
            session = MockSession(user_id="user-123", device_info=f"Device {i}")
            await storage.save_session(session)

        # Request only 3
        filters = SessionFilters(limit=3)
        sessions = await storage.list_sessions("user-123", filters)

        assert len(sessions) == 3

    async def test_list_sessions_pagination_offset(self):
        """Test pagination with offset."""
        from datetime import datetime, timedelta, timezone

        storage = MemorySessionStorage()
        now = datetime.now(timezone.utc)

        # Create 5 sessions with known order
        for i in range(5):
            session = MockSession(
                user_id="user-123",
                created_at=now - timedelta(hours=i),
                device_info=f"Device {i}",
            )
            await storage.save_session(session)

        # Skip first 2 sessions
        filters = SessionFilters(offset=2)
        sessions = await storage.list_sessions("user-123", filters)

        assert len(sessions) == 3
        assert sessions[0].device_info == "Device 2"

    async def test_list_sessions_pagination_offset_and_limit(self):
        """Test pagination with both offset and limit."""
        from datetime import datetime, timedelta, timezone

        storage = MemorySessionStorage()
        now = datetime.now(timezone.utc)

        # Create 10 sessions
        for i in range(10):
            session = MockSession(
                user_id="user-123",
                created_at=now - timedelta(hours=i),
                device_info=f"Device {i}",
            )
            await storage.save_session(session)

        # Skip first 3, get next 2 (devices 3 and 4)
        filters = SessionFilters(offset=3, limit=2)
        sessions = await storage.list_sessions("user-123", filters)

        assert len(sessions) == 2
        assert sessions[0].device_info == "Device 3"
        assert sessions[1].device_info == "Device 4"

    async def test_list_sessions_pagination_offset_beyond_results(self):
        """Test pagination when offset is beyond available results."""
        storage = MemorySessionStorage()

        # Create 3 sessions
        for i in range(3):
            session = MockSession(user_id="user-123")
            await storage.save_session(session)

        # Offset beyond results
        filters = SessionFilters(offset=10)
        sessions = await storage.list_sessions("user-123", filters)

        assert len(sessions) == 0
