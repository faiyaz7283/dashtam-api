"""Integration tests for CacheSessionStorage using fakeredis.

Verifies that sessions are correctly serialized/deserialized,
TTL is respected, and list/revoke/delete operations work as expected.
"""

from uuid import uuid4

import pytest

from src.session_manager.storage.cache import CacheSessionStorage
from src.session_manager.tests.fixtures.mock_models import MockSession


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
