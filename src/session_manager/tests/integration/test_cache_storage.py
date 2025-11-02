"""Integration tests for CacheSessionStorage using fakeredis.

Verifies that sessions are correctly serialized/deserialized,
TTL is respected, and list/revoke/delete operations work as expected.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.session_manager.storage.cache import CacheSessionStorage
from src.session_manager.tests.fixtures.mock_models import MockSession
from src.session_manager.models.filters import SessionFilters


@pytest.mark.asyncio
async def test_cache_storage_save_and_get(fakeredis_client):
    """Test saving and retrieving a session from cache storage."""
    storage = CacheSessionStorage(
        session_model=MockSession,
        cache_client=fakeredis_client,
        ttl=3600,
    )

    session = MockSession(
        id=uuid4(),
        user_id="user-1",
        device_info="Device A",
        ip_address="10.0.0.1",
    )

    await storage.save_session(session)

    retrieved = await storage.get_session(str(session.id))
    assert retrieved is not None
    assert str(retrieved.id) == str(session.id)
    assert retrieved.user_id == session.user_id
    assert retrieved.device_info == session.device_info


@pytest.mark.asyncio
async def test_cache_storage_ttl_expiration(fakeredis_client):
    """Test that sessions expire after TTL."""
    storage = CacheSessionStorage(
        session_model=MockSession,
        cache_client=fakeredis_client,
        ttl=1,  # 1 second TTL
    )

    session = MockSession(user_id="user-1")
    await storage.save_session(session)

    # Immediately available
    assert await storage.get_session(str(session.id)) is not None

    # Wait past TTL
    import asyncio

    await asyncio.sleep(1.2)

    # Should be expired now
    assert await storage.get_session(str(session.id)) is None


@pytest.mark.asyncio
async def test_cache_storage_list_sessions(fakeredis_client):
    """Test listing sessions for a user with filters."""
    storage = CacheSessionStorage(
        session_model=MockSession,
        cache_client=fakeredis_client,
        ttl=3600,
    )

    # Create sessions for two users
    s1 = MockSession(user_id="user-1", device_info="Chrome", ip_address="1.1.1.1")
    s2 = MockSession(user_id="user-1", device_info="Firefox", ip_address="2.2.2.2")
    s3 = MockSession(user_id="user-2", device_info="Safari", ip_address="3.3.3.3")

    await storage.save_session(s1)
    await storage.save_session(s2)
    await storage.save_session(s3)

    # List only user-1
    sessions = await storage.list_sessions("user-1")
    assert len(sessions) == 2
    assert all(s.user_id == "user-1" for s in sessions)

    # Filter by device type
    filters = SessionFilters(device_type="Chrome")
    sessions = await storage.list_sessions("user-1", filters)
    assert len(sessions) == 1
    assert sessions[0].device_info and "Chrome" in sessions[0].device_info


@pytest.mark.asyncio
async def test_cache_storage_revoke_and_delete(fakeredis_client):
    """Test revoking and deleting sessions in cache storage."""
    storage = CacheSessionStorage(
        session_model=MockSession,
        cache_client=fakeredis_client,
        ttl=3600,
    )

    session = MockSession(user_id="user-1")
    await storage.save_session(session)

    # Revoke
    revoked = await storage.revoke_session(str(session.id), reason="test")
    assert revoked is True

    # Retrieve and verify revoked state
    retrieved = await storage.get_session(str(session.id))
    assert retrieved is not None
    assert retrieved.is_revoked is True

    # Delete
    deleted = await storage.delete_session(str(session.id))
    assert deleted is True

    # Should be gone
    assert await storage.get_session(str(session.id)) is None
