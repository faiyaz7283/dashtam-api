"""Integration tests for Redis session cache.

Tests the RedisSessionCache implementation against a real Redis instance.
Following F0.4/F0.5 patterns: NO unit tests for infrastructure adapters,
only integration tests that verify real Redis operations.

Architecture:
- Tests against real Redis (not mocked)
- Uses test environment Redis (database 1)
- Tests all SessionCache protocol methods
- Verifies session data serialization/deserialization
- Uses fresh Redis connections per test (bypasses singleton)

Reference:
    - docs/architecture/session-management-architecture.md
"""

from datetime import UTC, datetime
from uuid_extensions import uuid7
from freezegun import freeze_time

import pytest

from src.domain.protocols.session_repository import SessionData


@freeze_time("2024-01-01 12:00:00")
def create_test_session_data(
    session_id=None,
    user_id=None,
    device_info="Chrome on Windows",
    user_agent="Mozilla/5.0 Chrome/120.0",
    ip_address="192.168.1.1",
    location="New York, US",
    is_revoked=False,
    is_trusted=False,
    expires_at=None,
    refresh_token_id=None,
) -> SessionData:
    """Create test SessionData with sensible defaults."""
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    return SessionData(
        id=session_id or uuid7(),
        user_id=user_id or uuid7(),
        device_info=device_info,
        user_agent=user_agent,
        ip_address=ip_address,
        location=location,
        created_at=now,
        last_activity_at=now,
        expires_at=expires_at
        or datetime(2024, 1, 31, 12, 0, 0, tzinfo=UTC),  # 30 days later
        is_revoked=is_revoked,
        is_trusted=is_trusted,
        revoked_at=None,
        revoked_reason=None,
        refresh_token_id=refresh_token_id,
        last_ip_address=ip_address,
        suspicious_activity_count=0,
        last_provider_accessed=None,
        last_provider_sync_at=None,
        providers_accessed=None,
    )


@pytest.mark.integration
class TestSessionCacheGetSet:
    """Test session cache get and set operations."""

    @pytest.mark.asyncio
    async def test_set_and_get_session(self, session_cache):
        """Test storing and retrieving session data."""
        # Arrange
        session_data = create_test_session_data()

        # Act
        await session_cache.set(session_data)
        result = await session_cache.get(session_data.id)

        # Assert
        assert result is not None
        assert result.id == session_data.id
        assert result.user_id == session_data.user_id
        assert result.device_info == session_data.device_info
        assert result.ip_address == session_data.ip_address
        assert result.location == session_data.location

    @pytest.mark.asyncio
    async def test_get_nonexistent_session_returns_none(self, session_cache):
        """Test getting a session that doesn't exist returns None."""
        result = await session_cache.get(uuid7())
        assert result is None

    @pytest.mark.asyncio
    async def test_set_with_explicit_ttl(self, session_cache, cache_adapter):
        """Test setting session with explicit TTL."""
        # Arrange
        session_data = create_test_session_data()
        ttl_seconds = 60

        # Act
        await session_cache.set(session_data, ttl_seconds=ttl_seconds)

        # Assert - verify TTL is set
        key = f"session:{session_data.id}"
        ttl_result = await cache_adapter.ttl(key)
        assert ttl_result.value is not None
        assert 0 < ttl_result.value <= ttl_seconds

    @pytest.mark.asyncio
    @freeze_time("2024-01-01 12:00:00")
    async def test_set_calculates_ttl_from_expires_at(
        self, session_cache, cache_adapter
    ):
        """Test TTL is calculated from session expires_at if not provided."""
        # Arrange
        expires_at = datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC)  # 1 hour later
        session_data = create_test_session_data(expires_at=expires_at)

        # Act
        await session_cache.set(session_data)

        # Assert - TTL should be exactly 1 hour
        key = f"session:{session_data.id}"
        ttl_result = await cache_adapter.ttl(key)
        assert ttl_result.value is not None
        # Exact 3600 seconds (allow small Redis variance)
        assert 3590 < ttl_result.value <= 3600

    @pytest.mark.asyncio
    async def test_set_session_adds_to_user_index(self, session_cache):
        """Test that set() adds session to user's session index."""
        # Arrange
        user_id = uuid7()
        session_data = create_test_session_data(user_id=user_id)

        # Act
        await session_cache.set(session_data)

        # Assert
        user_session_ids = await session_cache.get_user_session_ids(user_id)
        assert session_data.id in user_session_ids

    @pytest.mark.asyncio
    @freeze_time("2024-01-01 12:00:00")
    async def test_session_data_serialization_all_fields(self, session_cache):
        """Test all SessionData fields are properly serialized/deserialized."""
        # Arrange - session with all fields populated
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        refresh_token_id = uuid7()
        session_data = SessionData(
            id=uuid7(),
            user_id=uuid7(),
            device_info="Safari on macOS",
            user_agent="Mozilla/5.0 Safari/605.1.15",
            ip_address="10.0.0.1",
            location="San Francisco, US",
            created_at=now,
            last_activity_at=now,
            expires_at=datetime(2024, 1, 8, 12, 0, 0, tzinfo=UTC),  # 7 days later
            is_revoked=False,
            is_trusted=True,
            revoked_at=None,
            revoked_reason=None,
            refresh_token_id=refresh_token_id,
            last_ip_address="10.0.0.2",
            suspicious_activity_count=3,
            last_provider_accessed="schwab",
            last_provider_sync_at=now,
            providers_accessed=["schwab", "fidelity"],
        )

        # Act
        await session_cache.set(session_data)
        result = await session_cache.get(session_data.id)

        # Assert - all fields preserved
        assert result is not None
        assert result.id == session_data.id
        assert result.user_id == session_data.user_id
        assert result.device_info == session_data.device_info
        assert result.user_agent == session_data.user_agent
        assert result.ip_address == session_data.ip_address
        assert result.location == session_data.location
        assert result.is_trusted == session_data.is_trusted
        assert result.refresh_token_id == refresh_token_id
        assert result.last_ip_address == session_data.last_ip_address
        assert (
            result.suspicious_activity_count == session_data.suspicious_activity_count
        )
        assert result.last_provider_accessed == session_data.last_provider_accessed
        assert result.providers_accessed == session_data.providers_accessed


@pytest.mark.integration
class TestSessionCacheDelete:
    """Test session cache delete operations."""

    @pytest.mark.asyncio
    async def test_delete_existing_session(self, session_cache):
        """Test deleting an existing session returns True."""
        # Arrange
        session_data = create_test_session_data()
        await session_cache.set(session_data)

        # Act
        result = await session_cache.delete(session_data.id)

        # Assert
        assert result is True

        # Verify deleted
        get_result = await session_cache.get(session_data.id)
        assert get_result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session_returns_false(self, session_cache):
        """Test deleting nonexistent session returns False."""
        result = await session_cache.delete(uuid7())
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_all_for_user(self, session_cache):
        """Test deleting all sessions for a user."""
        # Arrange - create multiple sessions for same user
        user_id = uuid7()
        session1 = create_test_session_data(user_id=user_id)
        session2 = create_test_session_data(user_id=user_id)
        session3 = create_test_session_data(user_id=user_id)

        await session_cache.set(session1)
        await session_cache.set(session2)
        await session_cache.set(session3)

        # Verify all sessions exist
        assert await session_cache.get(session1.id) is not None
        assert await session_cache.get(session2.id) is not None
        assert await session_cache.get(session3.id) is not None

        # Act
        deleted_count = await session_cache.delete_all_for_user(user_id)

        # Assert
        assert deleted_count == 3

        # Verify all deleted
        assert await session_cache.get(session1.id) is None
        assert await session_cache.get(session2.id) is None
        assert await session_cache.get(session3.id) is None

        # Verify user index is empty
        user_sessions = await session_cache.get_user_session_ids(user_id)
        assert len(user_sessions) == 0

    @pytest.mark.asyncio
    async def test_delete_all_for_user_with_no_sessions(self, session_cache):
        """Test delete_all_for_user with user having no sessions."""
        result = await session_cache.delete_all_for_user(uuid7())
        assert result == 0


@pytest.mark.integration
class TestSessionCacheExists:
    """Test session cache exists operation."""

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_existing_session(self, session_cache):
        """Test exists returns True for cached session."""
        # Arrange
        session_data = create_test_session_data()
        await session_cache.set(session_data)

        # Act
        result = await session_cache.exists(session_data.id)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_nonexistent_session(self, session_cache):
        """Test exists returns False for non-cached session."""
        result = await session_cache.exists(uuid7())
        assert result is False


@pytest.mark.integration
class TestSessionCacheUserIndex:
    """Test session cache user session index operations."""

    @pytest.mark.asyncio
    async def test_get_user_session_ids_returns_all_sessions(self, session_cache):
        """Test getting all session IDs for a user."""
        # Arrange
        user_id = uuid7()
        session1 = create_test_session_data(user_id=user_id)
        session2 = create_test_session_data(user_id=user_id)

        await session_cache.set(session1)
        await session_cache.set(session2)

        # Act
        session_ids = await session_cache.get_user_session_ids(user_id)

        # Assert
        assert len(session_ids) == 2
        assert session1.id in session_ids
        assert session2.id in session_ids

    @pytest.mark.asyncio
    async def test_get_user_session_ids_returns_empty_for_unknown_user(
        self, session_cache
    ):
        """Test getting session IDs for user with no sessions."""
        result = await session_cache.get_user_session_ids(uuid7())
        assert result == []

    @pytest.mark.asyncio
    async def test_add_user_session(self, session_cache):
        """Test adding session to user index directly."""
        # Arrange
        user_id = uuid7()
        session_id = uuid7()

        # Act
        await session_cache.add_user_session(user_id, session_id)

        # Assert
        session_ids = await session_cache.get_user_session_ids(user_id)
        assert session_id in session_ids

    @pytest.mark.asyncio
    async def test_add_user_session_idempotent(self, session_cache):
        """Test adding same session twice doesn't duplicate."""
        # Arrange
        user_id = uuid7()
        session_id = uuid7()

        # Act - add twice
        await session_cache.add_user_session(user_id, session_id)
        await session_cache.add_user_session(user_id, session_id)

        # Assert - only one entry
        session_ids = await session_cache.get_user_session_ids(user_id)
        assert len(session_ids) == 1
        assert session_id in session_ids

    @pytest.mark.asyncio
    async def test_remove_user_session(self, session_cache):
        """Test removing session from user index."""
        # Arrange
        user_id = uuid7()
        session_id1 = uuid7()
        session_id2 = uuid7()

        await session_cache.add_user_session(user_id, session_id1)
        await session_cache.add_user_session(user_id, session_id2)

        # Act
        await session_cache.remove_user_session(user_id, session_id1)

        # Assert
        session_ids = await session_cache.get_user_session_ids(user_id)
        assert session_id1 not in session_ids
        assert session_id2 in session_ids

    @pytest.mark.asyncio
    async def test_remove_last_user_session_clears_index(self, session_cache):
        """Test removing last session clears the user index key."""
        # Arrange
        user_id = uuid7()
        session_id = uuid7()
        await session_cache.add_user_session(user_id, session_id)

        # Act
        await session_cache.remove_user_session(user_id, session_id)

        # Assert
        session_ids = await session_cache.get_user_session_ids(user_id)
        assert len(session_ids) == 0

    @pytest.mark.asyncio
    async def test_remove_nonexistent_session_from_user_index(self, session_cache):
        """Test removing non-existent session from user index is safe."""
        # Arrange
        user_id = uuid7()
        existing_session = uuid7()
        nonexistent_session = uuid7()
        await session_cache.add_user_session(user_id, existing_session)

        # Act - should not raise
        await session_cache.remove_user_session(user_id, nonexistent_session)

        # Assert - existing session still there
        session_ids = await session_cache.get_user_session_ids(user_id)
        assert existing_session in session_ids


@pytest.mark.integration
class TestSessionCacheUpdateActivity:
    """Test session cache update_last_activity operation."""

    @pytest.mark.asyncio
    @freeze_time("2024-01-01 12:00:00")
    async def test_update_last_activity_updates_timestamp(self, session_cache):
        """Test update_last_activity updates the last_activity_at field."""
        # Arrange
        old_time = datetime(2024, 1, 1, 11, 0, 0, tzinfo=UTC)  # 1 hour ago
        session_data = SessionData(
            id=uuid7(),
            user_id=uuid7(),
            device_info="Chrome on Windows",
            user_agent="Mozilla/5.0",
            ip_address="192.168.1.1",
            location="New York, US",
            created_at=old_time,
            last_activity_at=old_time,
            expires_at=datetime(2024, 1, 31, 12, 0, 0, tzinfo=UTC),  # 30 days later
            is_revoked=False,
            is_trusted=False,
            revoked_at=None,
            revoked_reason=None,
            refresh_token_id=None,
            last_ip_address="192.168.1.1",
            suspicious_activity_count=0,
            last_provider_accessed=None,
            last_provider_sync_at=None,
            providers_accessed=None,
        )
        await session_cache.set(session_data)

        # Act
        result = await session_cache.update_last_activity(session_data.id)

        # Assert
        assert result is True

        # Verify timestamp updated
        updated = await session_cache.get(session_data.id)
        assert updated is not None
        assert updated.last_activity_at > old_time

    @pytest.mark.asyncio
    async def test_update_last_activity_updates_ip_address(self, session_cache):
        """Test update_last_activity can update last_ip_address."""
        # Arrange
        session_data = create_test_session_data(ip_address="192.168.1.1")
        await session_cache.set(session_data)

        # Act
        new_ip = "10.0.0.1"
        result = await session_cache.update_last_activity(
            session_data.id, ip_address=new_ip
        )

        # Assert
        assert result is True

        # Verify IP updated
        updated = await session_cache.get(session_data.id)
        assert updated is not None
        assert updated.last_ip_address == new_ip

    @pytest.mark.asyncio
    async def test_update_last_activity_nonexistent_returns_false(self, session_cache):
        """Test update_last_activity on non-cached session returns False."""
        result = await session_cache.update_last_activity(uuid7())
        assert result is False


@pytest.mark.integration
class TestSessionCacheEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_session_with_none_optional_fields(self, session_cache):
        """Test session with None optional fields is handled correctly."""
        # Arrange - session with minimal data
        session_data = SessionData(
            id=uuid7(),
            user_id=uuid7(),
            device_info=None,
            user_agent=None,
            ip_address=None,
            location=None,
            created_at=None,
            last_activity_at=None,
            expires_at=None,
            is_revoked=False,
            is_trusted=False,
            revoked_at=None,
            revoked_reason=None,
            refresh_token_id=None,
            last_ip_address=None,
            suspicious_activity_count=0,
            last_provider_accessed=None,
            last_provider_sync_at=None,
            providers_accessed=None,
        )

        # Act
        await session_cache.set(session_data)
        result = await session_cache.get(session_data.id)

        # Assert
        assert result is not None
        assert result.id == session_data.id
        assert result.device_info is None
        assert result.location is None

    @pytest.mark.asyncio
    async def test_multiple_users_sessions_isolated(self, session_cache):
        """Test sessions for different users are properly isolated."""
        # Arrange
        user1_id = uuid7()
        user2_id = uuid7()

        user1_session = create_test_session_data(user_id=user1_id)
        user2_session = create_test_session_data(user_id=user2_id)

        await session_cache.set(user1_session)
        await session_cache.set(user2_session)

        # Act
        user1_sessions = await session_cache.get_user_session_ids(user1_id)
        user2_sessions = await session_cache.get_user_session_ids(user2_id)

        # Assert - each user only sees their own sessions
        assert len(user1_sessions) == 1
        assert len(user2_sessions) == 1
        assert user1_session.id in user1_sessions
        assert user2_session.id in user2_sessions
        assert user1_session.id not in user2_sessions
        assert user2_session.id not in user1_sessions

    @pytest.mark.asyncio
    async def test_delete_user_sessions_does_not_affect_other_users(
        self, session_cache
    ):
        """Test delete_all_for_user doesn't affect other users' sessions."""
        # Arrange
        user1_id = uuid7()
        user2_id = uuid7()

        user1_session = create_test_session_data(user_id=user1_id)
        user2_session = create_test_session_data(user_id=user2_id)

        await session_cache.set(user1_session)
        await session_cache.set(user2_session)

        # Act - delete user1's sessions
        await session_cache.delete_all_for_user(user1_id)

        # Assert - user2's session still exists
        assert await session_cache.get(user1_session.id) is None
        assert await session_cache.get(user2_session.id) is not None

        user2_sessions = await session_cache.get_user_session_ids(user2_id)
        assert user2_session.id in user2_sessions
