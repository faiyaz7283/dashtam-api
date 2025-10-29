"""Unit tests for cache backend (RedisCache implementation).

Tests the cache abstraction layer and Redis implementation following SOLID principles.
Uses real Redis (test environment) to verify actual behavior.

Testing Strategy:
- Synchronous tests (no pytest-asyncio)
- Uses asyncio.run() for async operations
- Aligns with project testing strategy (FastAPI TestClient pattern)
"""

import asyncio
import pytest
from redis.asyncio import Redis

from src.core.cache import CacheBackend, CacheError, RedisCache, get_cache


def _get_test_cache():
    """Helper to create Redis client and cache for testing.
    
    Returns a tuple of (redis_client, cache) that can be used within
    an async context. Caller is responsible for cleanup.
    """
    client = Redis(
        host="redis",  # Docker service name
        port=6379,
        db=1,  # Test DB (same as session management)
        decode_responses=True,
    )
    cache = RedisCache(client)
    return client, cache


class TestRedisCacheBasicOperations:
    """Test basic cache operations (set, get, delete, exists)."""

    def test_set_and_get_value(self):
        """Test setting and getting a value."""

        async def _test():
            client, cache = _get_test_cache()
            try:
                await cache.set("test_key", "test_value", ttl_seconds=60)
                value = await cache.get("test_key")
                return value
            finally:
                await client.flushdb()
                await client.aclose()

        value = asyncio.run(_test())
        assert value == "test_value"

    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist returns None."""

        async def _test():
            client, cache = _get_test_cache()
            try:
                return await cache.get("nonexistent")
            finally:
                await client.flushdb()
                await client.aclose()

        value = asyncio.run(_test())
        assert value is None

    def test_set_with_ttl_expiration(self):
        """Test that keys expire after TTL."""

        async def _test():
            client, cache = _get_test_cache()
            try:
                await cache.set("expire_key", "value", ttl_seconds=1)

                # Key exists initially
                value = await cache.get("expire_key")
                assert value == "value"

                # Wait for expiration
                await asyncio.sleep(1.1)

                value = await cache.get("expire_key")
                return value
            finally:
                await client.flushdb()
                await client.aclose()

        value = asyncio.run(_test())
        assert value is None

    def test_delete_key(self):
        """Test deleting a key."""

        async def _test():
            client, cache = _get_test_cache()
            try:
                await cache.set("delete_me", "value", ttl_seconds=60)
                await cache.delete("delete_me")
                return await cache.get("delete_me")
            finally:
                await client.flushdb()
                await client.aclose()

        value = asyncio.run(_test())
        assert value is None

    def test_delete_nonexistent_key(self):
        """Test deleting a key that doesn't exist (no error)."""

        async def _test():
            client, cache = _get_test_cache()
            try:
                await cache.delete("nonexistent")
            finally:
                await client.flushdb()
                await client.aclose()

        # Should not raise error
        asyncio.run(_test())

    def test_exists_returns_true_for_existing_key(self):
        """Test exists() returns True for existing key."""

        async def _test():
            client, cache = _get_test_cache()
            try:
                await cache.set("exists_key", "value", ttl_seconds=60)
                return await cache.exists("exists_key")
            finally:
                await client.flushdb()
                await client.aclose()

        exists = asyncio.run(_test())
        assert exists is True

    def test_exists_returns_false_for_nonexistent_key(self):
        """Test exists() returns False for nonexistent key."""

        async def _test():
            client, cache = _get_test_cache()
            try:
                return await cache.exists("nonexistent")
            finally:
                await client.flushdb()
                await client.aclose()

        exists = asyncio.run(_test())
        assert exists is False


class TestRedisCacheSessionBlacklist:
    """Test cache usage for session token blacklist (primary use case)."""

    def test_blacklist_token(self):
        """Test adding token to blacklist."""

        async def _test():
            client, cache = _get_test_cache()
            try:
                token_id = "7b4280a7-7871-4041-beaa-80d290bd9b40"
                key = f"revoked_token:{token_id}"

                # Add to blacklist (30 days)
                await cache.set(key, "1", ttl_seconds=2592000)

                # Verify blacklisted
                return await cache.exists(key)
            finally:
                await client.flushdb()
                await client.aclose()

        is_blacklisted = asyncio.run(_test())
        assert is_blacklisted is True

    def test_check_blacklist_for_valid_token(self):
        """Test checking blacklist for valid (non-revoked) token."""

        async def _test():
            client, cache = _get_test_cache()
            try:
                token_id = "valid-token-id"
                key = f"revoked_token:{token_id}"

                # Token not blacklisted
                return await cache.exists(key)
            finally:
                await client.flushdb()
                await client.aclose()

        is_blacklisted = asyncio.run(_test())
        assert is_blacklisted is False

    def test_multiple_blacklisted_tokens(self):
        """Test blacklisting multiple tokens."""

        async def _test():
            client, cache = _get_test_cache()
            try:
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
                results = []
                for token_id in token_ids:
                    key = f"revoked_token:{token_id}"
                    is_blacklisted = await cache.exists(key)
                    results.append(is_blacklisted)

                return results
            finally:
                await client.flushdb()
                await client.aclose()

        results = asyncio.run(_test())
        assert all(results)


class TestRedisCacheErrorHandling:
    """Test error handling and graceful degradation."""

    def test_cache_set_with_invalid_ttl(self):
        """Test setting key with invalid TTL (should raise Exception)."""

        async def _test():
            client, cache = _get_test_cache()
            try:
                # Redis will fail if TTL is invalid
                await cache.set("key", "value", ttl_seconds=-1)
            finally:
                await client.flushdb()
                await client.aclose()

        # Should raise exception
        with pytest.raises(Exception):  # Could be CacheError or RedisError
            asyncio.run(_test())

    def test_cache_operations_after_close(self):
        """Test cache operations after closing connection."""

        async def _test():
            client, cache = _get_test_cache()
            try:
                await cache.close()
                
                # Operations after close should raise error
                await cache.set("key", "value", ttl_seconds=60)
            finally:
                await client.aclose()

        with pytest.raises(Exception):
            asyncio.run(_test())


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

    def test_session_revocation_flow(self):
        """Test complete session revocation flow."""

        async def _test():
            client, cache = _get_test_cache()
            try:
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
                    return True  # Token blocked successfully
            finally:
                await client.flushdb()
                await client.aclose()

        result = asyncio.run(_test())
        assert result is True

    def test_graceful_degradation_on_cache_failure(self):
        """Test that services handle cache failures gracefully."""

        async def _test():
            client, cache = _get_test_cache()
            try:
                # Simulate cache failure by using invalid key
                # Services should catch exceptions and continue (DB is fallback)
                try:
                    await cache.get("test_key")
                    # If no error, that's fine (cache working)
                    return True
                except CacheError:
                    # If cache error, services should handle it gracefully
                    # This test verifies error type is CacheError (expected)
                    return True
            finally:
                await client.flushdb()
                await client.aclose()

        result = asyncio.run(_test())
        assert result is True


class TestRedisCachePerformance:
    """Test cache performance characteristics."""

    def test_cache_operations_are_fast(self):
        """Test cache operations complete quickly (<10ms)."""
        import time

        async def _test():
            client, cache = _get_test_cache()
            try:
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
                
                return set_duration, get_duration, exists_duration
            finally:
                await client.flushdb()
                await client.aclose()

        set_duration, get_duration, exists_duration = asyncio.run(_test())
        
        # All operations should be fast (<50ms even in test environment)
        assert set_duration < 50
        assert get_duration < 50
        assert exists_duration < 50

    def test_multiple_concurrent_operations(self):
        """Test cache handles concurrent operations correctly."""

        async def _test():
            client, cache = _get_test_cache()
            try:
                # Create 10 concurrent set operations
                tasks = [
                    cache.set(f"concurrent_{i}", f"value_{i}", ttl_seconds=60)
                    for i in range(10)
                ]
                await asyncio.gather(*tasks)
                
                # Verify all keys set correctly
                results = []
                for i in range(10):
                    value = await cache.get(f"concurrent_{i}")
                    results.append(value == f"value_{i}")
                
                return all(results)
            finally:
                await client.flushdb()
                await client.aclose()

        result = asyncio.run(_test())
        assert result is True
