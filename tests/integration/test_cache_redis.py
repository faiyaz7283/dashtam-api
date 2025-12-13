"""Integration tests for Redis cache adapter.

Tests the RedisAdapter implementation against a real Redis instance.
Following F0.4 patterns: NO unit tests for infrastructure adapters,
only integration tests that verify real Redis operations.

Architecture:
- Tests against real Redis (not mocked)
- Uses test environment Redis (database 1)
- Tests all CacheProtocol methods
- Verifies Result type error handling
- Uses fresh Redis connections per test (bypasses singleton)
"""

import pytest

from src.core.result import Failure, Success
from src.infrastructure.errors import CacheError


@pytest.mark.integration
class TestCacheIntegration:
    """Integration tests for cache infrastructure.

    Uses fixtures from conftest.py:
    - cache_adapter: Fresh RedisAdapter per test (bypasses singleton)
    - redis_test_client: Fresh Redis client per test

    Pattern matches database tests: tests get fresh instances,
    production uses singleton for connection pooling efficiency.
    """

    @pytest.mark.asyncio
    async def test_cache_connection_works(self, cache_adapter):
        """Test that we can connect to the real Redis instance."""
        result = await cache_adapter.ping()
        assert isinstance(result, Success)
        assert result.value is True

    @pytest.mark.asyncio
    async def test_set_and_get_string(self, cache_adapter):
        """Test setting and getting a string value."""
        # Set value
        set_result = await cache_adapter.set("test_key", "test_value")
        assert isinstance(set_result, Success)
        assert set_result.value is None

        # Get value
        get_result = await cache_adapter.get("test_key")
        assert isinstance(get_result, Success)
        assert get_result.value == "test_value"

    @pytest.mark.asyncio
    async def test_get_nonexistent_key_returns_none(self, cache_adapter):
        """Test getting a key that doesn't exist returns None."""
        result = await cache_adapter.get("nonexistent_key")
        assert isinstance(result, Success)
        assert result.value is None

    @pytest.mark.asyncio
    async def test_set_and_get_json(self, cache_adapter):
        """Test setting and getting JSON data."""
        test_data = {"user_id": "123", "email": "test@example.com", "active": True}

        # Set JSON
        set_result = await cache_adapter.set_json("user:123", test_data)
        assert isinstance(set_result, Success)

        # Get JSON
        get_result = await cache_adapter.get_json("user:123")
        assert isinstance(get_result, Success)
        assert get_result.value == test_data

    @pytest.mark.asyncio
    async def test_delete_existing_key(self, cache_adapter):
        """Test deleting an existing key returns True."""
        # Set value
        await cache_adapter.set("to_delete", "value")

        # Delete
        result = await cache_adapter.delete("to_delete")
        assert isinstance(result, Success)
        assert result.value is True

        # Verify deleted
        get_result = await cache_adapter.get("to_delete")
        assert isinstance(get_result, Success)
        assert get_result.value is None

    @pytest.mark.asyncio
    async def test_set_with_ttl(self, cache_adapter):
        """Test setting a value with TTL."""
        # Set with 60 second TTL
        result = await cache_adapter.set("ttl_key", "value", ttl=60)
        assert isinstance(result, Success)

        # Check TTL is set
        ttl_result = await cache_adapter.ttl("ttl_key")
        assert isinstance(ttl_result, Success)
        assert ttl_result.value is not None
        assert 0 < ttl_result.value <= 60

    @pytest.mark.asyncio
    async def test_increment_counter(self, cache_adapter):
        """Test incrementing a counter (atomic operation)."""
        # Increment new key starts at 1
        result = await cache_adapter.increment("test_increment_counter")
        assert isinstance(result, Success)
        assert result.value == 1

        # Increment again
        result = await cache_adapter.increment("test_increment_counter")
        assert isinstance(result, Success)
        assert result.value == 2

    @pytest.mark.asyncio
    async def test_decrement_counter(self, cache_adapter):
        """Test decrementing a counter (atomic operation)."""
        # Set counter to 10 (starts at 0, increment by 10)
        result_inc = await cache_adapter.increment("test_decrement_counter", amount=10)
        assert result_inc.value == 10

        # Decrement by 3 (10 - 3 = 7)
        result = await cache_adapter.decrement("test_decrement_counter", amount=3)
        assert isinstance(result, Success)
        assert result.value == 7

    @pytest.mark.asyncio
    async def test_exists_with_existing_key(self, cache_adapter):
        """Test exists returns True for existing key."""
        await cache_adapter.set("existing_key", "value")

        result = await cache_adapter.exists("existing_key")
        assert isinstance(result, Success)
        assert result.value is True

    @pytest.mark.asyncio
    async def test_exists_with_nonexistent_key(self, cache_adapter):
        """Test exists returns False for nonexistent key."""
        result = await cache_adapter.exists("nonexistent")
        assert isinstance(result, Success)
        assert result.value is False

    @pytest.mark.asyncio
    async def test_error_handling_invalid_json(self, cache_adapter, redis_test_client):
        """Test getting invalid JSON returns error."""
        # Set invalid JSON directly via Redis client
        await redis_test_client.set("invalid_json", "not a json string {]")

        # Try to get as JSON
        result = await cache_adapter.get_json("invalid_json")
        assert isinstance(result, Failure)
        assert isinstance(result.error, CacheError)
        assert "parse json" in result.error.message.lower()  # Case-insensitive check

    @pytest.mark.asyncio
    async def test_flush_clears_all_keys(self, cache_adapter):
        """Test flush removes all keys from database."""
        # Set multiple keys
        await cache_adapter.set("key1", "value1")
        await cache_adapter.set("key2", "value2")
        await cache_adapter.set("key3", "value3")

        # Flush
        result = await cache_adapter.flush()
        assert isinstance(result, Success)

        # Verify all keys are gone
        result1 = await cache_adapter.get("key1")
        result2 = await cache_adapter.get("key2")
        result3 = await cache_adapter.get("key3")

        assert result1.value is None
        assert result2.value is None
        assert result3.value is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key_returns_false(self, cache_adapter):
        """Test deleting nonexistent key returns False."""
        result = await cache_adapter.delete("nonexistent_key")
        assert isinstance(result, Success)
        assert result.value is False

    @pytest.mark.asyncio
    async def test_expire_existing_key(self, cache_adapter):
        """Test setting expiration on existing key returns True."""
        # Set key
        await cache_adapter.set("expire_test", "value")

        # Set expiration
        result = await cache_adapter.expire("expire_test", 30)
        assert isinstance(result, Success)
        assert result.value is True

        # Verify TTL is set
        ttl_result = await cache_adapter.ttl("expire_test")
        assert isinstance(ttl_result, Success)
        assert ttl_result.value is not None
        assert 0 < ttl_result.value <= 30

    @pytest.mark.asyncio
    async def test_expire_nonexistent_key_returns_false(self, cache_adapter):
        """Test setting expiration on nonexistent key returns False."""
        result = await cache_adapter.expire("nonexistent", 30)
        assert isinstance(result, Success)
        assert result.value is False

    @pytest.mark.asyncio
    async def test_ttl_on_key_without_expiration_returns_none(self, cache_adapter):
        """Test TTL on key without expiration returns None."""
        # Set key without TTL
        await cache_adapter.set("no_ttl_key", "value")

        # Get TTL
        result = await cache_adapter.ttl("no_ttl_key")
        assert isinstance(result, Success)
        assert result.value is None

    @pytest.mark.asyncio
    async def test_ttl_on_nonexistent_key_returns_none(self, cache_adapter):
        """Test TTL on nonexistent key returns None."""
        result = await cache_adapter.ttl("nonexistent")
        assert isinstance(result, Success)
        assert result.value is None

    @pytest.mark.asyncio
    async def test_increment_with_custom_amount(self, cache_adapter):
        """Test incrementing counter by custom amount."""
        # Increment by 5
        result = await cache_adapter.increment("custom_incr", amount=5)
        assert isinstance(result, Success)
        assert result.value == 5

        # Increment by 10
        result = await cache_adapter.increment("custom_incr", amount=10)
        assert isinstance(result, Success)
        assert result.value == 15

    @pytest.mark.asyncio
    async def test_decrement_with_custom_amount(self, cache_adapter):
        """Test decrementing counter by custom amount."""
        # Set counter to 100
        await cache_adapter.increment("custom_decr", amount=100)

        # Decrement by 25
        result = await cache_adapter.decrement("custom_decr", amount=25)
        assert isinstance(result, Success)
        assert result.value == 75

    @pytest.mark.asyncio
    async def test_error_handling_set_json_invalid_type(self, cache_adapter):
        """Test set_json with non-serializable type returns error."""
        # Try to set non-serializable object (function)
        invalid_data = {"func": lambda x: x}  # type: ignore[dict-item]

        result = await cache_adapter.set_json("invalid", invalid_data)
        assert isinstance(result, Failure)
        assert isinstance(result.error, CacheError)
        assert "serialize" in result.error.message.lower()

    @pytest.mark.asyncio
    async def test_get_json_with_nonexistent_key_returns_none(self, cache_adapter):
        """Test get_json on nonexistent key returns None."""
        result = await cache_adapter.get_json("nonexistent_json")
        assert isinstance(result, Success)
        assert result.value is None

    @pytest.mark.asyncio
    async def test_delete_pattern_removes_matching_keys(self, cache_adapter):
        """Test delete_pattern removes all keys matching glob pattern."""
        # Set multiple keys with a common prefix
        await cache_adapter.set("session:user123:abc", "session1")
        await cache_adapter.set("session:user123:def", "session2")
        await cache_adapter.set("session:user123:ghi", "session3")
        await cache_adapter.set("session:user456:xyz", "other_user")

        # Delete all sessions for user123
        result = await cache_adapter.delete_pattern("session:user123:*")
        assert isinstance(result, Success)
        assert result.value == 3  # 3 keys deleted

        # Verify user123 sessions are gone
        result1 = await cache_adapter.get("session:user123:abc")
        result2 = await cache_adapter.get("session:user123:def")
        result3 = await cache_adapter.get("session:user123:ghi")
        assert result1.value is None
        assert result2.value is None
        assert result3.value is None

        # Verify user456 session still exists
        result4 = await cache_adapter.get("session:user456:xyz")
        assert result4.value == "other_user"

    @pytest.mark.asyncio
    async def test_delete_pattern_returns_zero_when_no_matches(self, cache_adapter):
        """Test delete_pattern returns 0 when no keys match pattern."""
        result = await cache_adapter.delete_pattern("nonexistent:*")
        assert isinstance(result, Success)
        assert result.value == 0

    @pytest.mark.asyncio
    async def test_get_many_retrieves_multiple_values(self, cache_adapter):
        """Test get_many retrieves multiple values in single operation."""
        # Set multiple keys
        await cache_adapter.set("batch:key1", "value1")
        await cache_adapter.set("batch:key2", "value2")
        await cache_adapter.set("batch:key3", "value3")

        # Get all at once
        result = await cache_adapter.get_many(
            ["batch:key1", "batch:key2", "batch:key3", "batch:missing"]
        )
        assert isinstance(result, Success)
        assert result.value == {
            "batch:key1": "value1",
            "batch:key2": "value2",
            "batch:key3": "value3",
            "batch:missing": None,  # Missing key returns None
        }

    @pytest.mark.asyncio
    async def test_get_many_with_empty_list_returns_empty_dict(self, cache_adapter):
        """Test get_many with empty list returns empty dict."""
        result = await cache_adapter.get_many([])
        assert isinstance(result, Success)
        assert result.value == {}

    @pytest.mark.asyncio
    async def test_set_many_stores_multiple_values(self, cache_adapter):
        """Test set_many stores multiple values in single operation."""
        mapping = {
            "multi:a": "alpha",
            "multi:b": "beta",
            "multi:c": "gamma",
        }

        # Set all at once
        result = await cache_adapter.set_many(mapping)
        assert isinstance(result, Success)
        assert result.value is None

        # Verify all were set
        get_result = await cache_adapter.get_many(["multi:a", "multi:b", "multi:c"])
        assert isinstance(get_result, Success)
        assert get_result.value == mapping

    @pytest.mark.asyncio
    async def test_set_many_with_ttl(self, cache_adapter):
        """Test set_many stores values with TTL."""
        mapping = {
            "ttl_multi:x": "x_value",
            "ttl_multi:y": "y_value",
        }

        # Set with 60 second TTL
        result = await cache_adapter.set_many(mapping, ttl=60)
        assert isinstance(result, Success)

        # Verify TTLs are set
        ttl_x = await cache_adapter.ttl("ttl_multi:x")
        ttl_y = await cache_adapter.ttl("ttl_multi:y")
        assert isinstance(ttl_x, Success)
        assert isinstance(ttl_y, Success)
        assert ttl_x.value is not None and 0 < ttl_x.value <= 60
        assert ttl_y.value is not None and 0 < ttl_y.value <= 60

    @pytest.mark.asyncio
    async def test_set_many_with_empty_dict_succeeds(self, cache_adapter):
        """Test set_many with empty dict succeeds without error."""
        result = await cache_adapter.set_many({})
        assert isinstance(result, Success)
        assert result.value is None
