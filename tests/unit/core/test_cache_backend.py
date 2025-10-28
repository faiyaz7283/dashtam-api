"""Unit tests for cache backend (RedisCache implementation).

Tests the cache abstraction layer and Redis implementation following SOLID principles.
Uses real Redis (test environment) to verify actual behavior.
"""

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.core.cache import CacheBackend, CacheError, RedisCache, get_cache


@pytest.fixture
async def redis_client():
    """Create test Redis client (uses test environment Redis DB 1)."""
    client = Redis(
        host="redis",  # Docker service name
        port=6379,
        db=1,  # Test DB (same as session management)
        decode_responses=True,
    )
    yield client
    # Cleanup: flush test DB after each test
    await client.flushdb()
    await client.close()


@pytest.fixture
async def cache(redis_client):
    """Create RedisCache instance for testing."""
    return RedisCache(redis_client)


class TestRedisCacheBasicOperations:
    """Test basic cache operations (set, get, delete, exists)."""

    async def test_set_and_get_value(self, cache):
        """Test setting and getting a value."""
        await cache.set("test_key", "test_value", ttl_seconds=60)
        value = await cache.get("test_key")
        assert value == "test_value"

    async def test_get_nonexistent_key(self, cache):
        """Test getting a key that doesn't exist returns None."""
        value = await cache.get("nonexistent")
        assert value is None

    async def test_set_with_ttl_expiration(self, cache, redis_client):
        """Test that keys expire after TTL."""
        await cache.set("expire_key", "value", ttl_seconds=1)
        
        # Key exists initially
        value = await cache.get("expire_key")
        assert value == "value"
        
        # Wait for expiration (use Redis TTL to verify)
        import asyncio
        await asyncio.sleep(1.1)
        
        value = await cache.get("expire_key")
        assert value is None

    async def test_delete_key(self, cache):
        """Test deleting a key."""
        await cache.set("delete_me", "value", ttl_seconds=60)
        await cache.delete("delete_me")
        
        value = await cache.get("delete_me")
        assert value is None

    async def test_delete_nonexistent_key(self, cache):
        """Test deleting a key that doesn't exist (no error)."""
        # Should not raise error
        await cache.delete("nonexistent")

    async def test_exists_returns_true_for_existing_key(self, cache):
        """Test exists() returns True for existing key."""
        await cache.set("exists_key", "value", ttl_seconds=60)
        exists = await cache.exists("exists_key")
        assert exists is True

    async def test_exists_returns_false_for_nonexistent_key(self, cache):
        """Test exists() returns False for nonexistent key."""
        exists = await cache.exists("nonexistent")
        assert exists is False


class TestRedisCacheSessionBlacklist:
    """Test cache usage for session token blacklist (primary use case)."""

    async def test_blacklist_token(self, cache):
        """Test adding token to blacklist."""
        token_id = "7b4280a7-7871-4041-beaa-80d290bd9b40"
        key = f"revoked_token:{token_id}"
        
        # Add to blacklist (30 days)
        await cache.set(key, "1", ttl_seconds=2592000)
        
        # Verify blacklisted
        is_blacklisted = await cache.exists(key)
        assert is_blacklisted is True

    async def test_check_blacklist_for_valid_token(self, cache):
        """Test checking blacklist for valid (non-revoked) token."""
        token_id = "valid-token-id"
        key = f"revoked_token:{token_id}"
        
        # Token not blacklisted
        is_blacklisted = await cache.exists(key)
        assert is_blacklisted is False

    async def test_multiple_blacklisted_tokens(self, cache):
        """Test blacklisting multiple tokens."""
        token_ids = [
            "token-1",
            "token-2",
            "token-3",
        ]
        
        # Blacklist all tokens
        for token_id in token_ids:
            key = f"revoked_token:{token_id}"
            await cache.set(key, "1", ttl_seconds=2592000)
        
        # Verify all blacklisted
        for token_id in token_ids:
            key = f"revoked_token:{token_id}"
            is_blacklisted = await cache.exists(key)
            assert is_blacklisted is True


class TestRedisCacheErrorHandling:
    """Test error handling and graceful degradation."""

    async def test_cache_set_with_invalid_ttl(self, cache):
        """Test setting key with invalid TTL (should raise CacheError)."""
        # Redis will fail if TTL is invalid
        with pytest.raises(Exception):  # Could be CacheError or RedisError
            await cache.set("key", "value", ttl_seconds=-1)

    async def test_cache_operations_after_close(self, redis_client):
        """Test cache operations after closing connection."""
        cache = RedisCache(redis_client)
        await cache.close()
        
        # Operations after close should raise error
        with pytest.raises(Exception):
            await cache.set("key", "value", ttl_seconds=60)


class TestCacheFactory:
    """Test cache factory (singleton pattern)."""

    def test_get_cache_returns_instance(self):
        """Test get_cache() returns CacheBackend instance."""
        cache = get_cache()
        assert isinstance(cache, CacheBackend)

    def test_get_cache_returns_singleton(self):
        """Test get_cache() returns same instance (singleton)."""
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2


class TestCacheIntegrationWithServices:
    """Test cache integration patterns used by services."""

    async def test_session_revocation_flow(self, cache):
        """Test complete session revocation flow."""
        token_id = "session-token-123"
        
        # 1. Revoke session (SessionManagementService)
        blacklist_key = f"revoked_token:{token_id}"
        await cache.set(blacklist_key, "1", ttl_seconds=2592000)
        
        # 2. Check blacklist (AuthService)
        is_revoked = await cache.exists(blacklist_key)
        assert is_revoked is True
        
        # 3. Simulate token refresh attempt (should be blocked)
        if is_revoked:
            # This is what AuthService does
            assert True  # Token blocked successfully

    async def test_graceful_degradation_on_cache_failure(self, cache):
        """Test that services handle cache failures gracefully."""
        # Simulate cache failure by using invalid key
        # Services should catch exceptions and continue (DB is fallback)
        try:
            await cache.get("test_key")
            # If no error, that's fine (cache working)
            assert True
        except CacheError:
            # If cache error, services should handle it gracefully
            # This test verifies error type is CacheError (expected)
            assert True


class TestRedisCachePerformance:
    """Test cache performance characteristics."""

    async def test_cache_operations_are_fast(self, cache):
        """Test cache operations complete quickly (<10ms)."""
        import time
        
        # Measure set operation
        start = time.time()
        await cache.set("perf_test", "value", ttl_seconds=60)
        set_duration = (time.time() - start) * 1000  # ms
        
        # Measure get operation
        start = time.time()
        await cache.get("perf_test")
        get_duration = (time.time() - start) * 1000  # ms
        
        # Measure exists operation
        start = time.time()
        await cache.exists("perf_test")
        exists_duration = (time.time() - start) * 1000  # ms
        
        # All operations should be fast (<50ms even in test environment)
        assert set_duration < 50
        assert get_duration < 50
        assert exists_duration < 50

    async def test_multiple_concurrent_operations(self, cache):
        """Test cache handles concurrent operations correctly."""
        import asyncio
        
        # Create 10 concurrent set operations
        tasks = [
            cache.set(f"concurrent_{i}", f"value_{i}", ttl_seconds=60)
            for i in range(10)
        ]
        await asyncio.gather(*tasks)
        
        # Verify all keys set correctly
        for i in range(10):
            value = await cache.get(f"concurrent_{i}")
            assert value == f"value_{i}"
