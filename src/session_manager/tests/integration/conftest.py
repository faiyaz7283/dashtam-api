"""Shared fixtures for integration tests.

Provides reusable fixtures for testing with real components
and test doubles (fakeredis, test databases).
"""

import asyncio

import pytest


@pytest.fixture
def fakeredis_client():
    """Create fakeredis client for cache storage testing.

    Returns:
        fakeredis.aioredis.FakeRedis instance (in-memory Redis emulation)

    Note:
        Requires: pip install fakeredis[lua]
    """
    import fakeredis.aioredis

    client = fakeredis.aioredis.FakeRedis(decode_responses=False)
    yield client

    # Cleanup
    try:
        asyncio.get_event_loop().run_until_complete(client.aclose())
    except Exception:
        pass  # Best effort cleanup


@pytest.fixture
def sample_session_data():
    """Provide sample session data for testing.

    Returns:
        dict: Session data that can be used to create test sessions
    """
    return {
        "user_id": "test-user-123",
        "device_info": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "ip_address": "192.168.1.1",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
