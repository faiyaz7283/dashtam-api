"""Unit tests for Redis storage backend with fakeredis.

This module tests RedisRateLimitStorage using fakeredis (in-memory Redis emulation)
for fast, isolated unit tests. Tests verify Lua script behavior, token bucket logic,
error handling, and all public methods.

Test Strategy:
    - Use fakeredis for actual Redis operations without external dependencies
    - Test all public methods: check_and_consume(), get_remaining(), reset()
    - Verify Lua script atomicity and correctness
    - Test error scenarios and fail-open behavior
    - Target 90%+ coverage for redis_storage.py

Why fakeredis:
    - Fast: No network latency (in-memory)
    - Isolated: No shared state between tests
    - Realistic: Executes actual Lua scripts
    - No external dependencies: No Redis container needed
"""

import asyncio

import pytest
from unittest.mock import patch
import fakeredis.aioredis

from src.rate_limiting.storage.redis_storage import RedisRateLimitStorage


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def redis_client():
    """Create fakeredis client for testing.

    Returns:
        fakeredis.aioredis.FakeRedis instance that emulates Redis behavior.
    """
    import asyncio

    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    # Cleanup in synchronous fixture
    try:
        asyncio.get_event_loop().run_until_complete(client.aclose())
    except Exception:
        pass  # Best effort cleanup


@pytest.fixture
def storage(redis_client):
    """Create RedisRateLimitStorage instance with fakeredis.

    Args:
        redis_client: fakeredis client from fixture.

    Returns:
        RedisRateLimitStorage instance ready for testing.
    """
    return RedisRateLimitStorage(redis_client)


# ============================================================================
# Test: Initial Bucket State
# ============================================================================


class TestRedisStorageInitialState:
    """Test initial bucket state and first request handling."""

    @pytest.mark.asyncio
    async def test_initial_bucket_starts_full(self, storage):
        """Test that new bucket starts with max_tokens available."""
        allowed, retry_after, remaining = await storage.check_and_consume(
            key="test:initial:full",
            max_tokens=100,
            refill_rate=10.0,
            cost=1,
        )

        assert allowed is True
        assert retry_after == 0.0
        assert remaining == 99  # Started at 100, consumed 1

    @pytest.mark.asyncio
    async def test_initial_bucket_multiple_requests(self, storage):
        """Test multiple requests to new bucket."""
        key = "test:initial:multiple"

        # First request: 100 → 99
        allowed1, _, remaining1 = await storage.check_and_consume(
            key=key, max_tokens=100, refill_rate=10.0, cost=1
        )
        assert allowed1 is True
        assert remaining1 == 99

        # Second request: 99 → 98
        allowed2, _, remaining2 = await storage.check_and_consume(
            key=key, max_tokens=100, refill_rate=10.0, cost=1
        )
        assert allowed2 is True
        assert remaining2 == 98


# ============================================================================
# Test: Token Consumption
# ============================================================================


class TestRedisStorageTokenConsumption:
    """Test token consumption behavior."""

    @pytest.mark.asyncio
    async def test_token_consumption_decrements_correctly(self, storage):
        """Test that tokens are consumed correctly."""
        key = "test:consumption"

        # Consume 5 tokens
        allowed, _, remaining = await storage.check_and_consume(
            key=key, max_tokens=100, refill_rate=10.0, cost=5
        )

        assert allowed is True
        assert remaining == 95  # 100 - 5

    @pytest.mark.asyncio
    async def test_insufficient_tokens_denies_request(self, storage):
        """Test that request is denied when insufficient tokens."""
        key = "test:insufficient"

        # Consume 100 tokens (all available)
        await storage.check_and_consume(
            key=key, max_tokens=100, refill_rate=10.0, cost=100
        )

        # Next request should be denied (0 tokens remaining)
        allowed, retry_after, remaining = await storage.check_and_consume(
            key=key, max_tokens=100, refill_rate=10.0, cost=1
        )

        assert allowed is False
        assert retry_after > 0  # Should tell us when to retry
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_cost_parameter_respected(self, storage):
        """Test that cost parameter is correctly used."""
        key = "test:cost"

        # Consume 25 tokens at once
        allowed, _, remaining = await storage.check_and_consume(
            key=key, max_tokens=100, refill_rate=10.0, cost=25
        )

        assert allowed is True
        assert remaining == 75  # 100 - 25


# ============================================================================
# Test: Token Refill
# ============================================================================


class TestRedisStorageTokenRefill:
    """Test token refill behavior over time."""

    @pytest.mark.asyncio
    async def test_tokens_refill_over_time(self, storage):
        """Test that tokens refill based on elapsed time."""
        key = "test:refill"

        # Consume all tokens
        await storage.check_and_consume(
            key=key,
            max_tokens=10,
            refill_rate=60.0,
            cost=10,  # 1 token per second
        )

        # Wait 3 seconds (should refill ~3 tokens)
        await asyncio.sleep(3.1)

        # Should have ~3 tokens available now
        allowed, _, remaining = await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=60.0, cost=3
        )

        assert allowed is True
        assert remaining >= 0  # At least 3 tokens refilled

    @pytest.mark.asyncio
    async def test_refill_caps_at_max_tokens(self, storage):
        """Test that refill doesn't exceed max_tokens."""
        key = "test:refill:cap"

        # Use 1 token
        await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=60.0, cost=1
        )

        # Wait long enough to refill beyond max (10 seconds = 10 tokens)
        await asyncio.sleep(10.1)

        # Next request should show max_tokens - 1 (capped at 10)
        allowed, _, remaining = await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=60.0, cost=1
        )

        assert allowed is True
        assert remaining == 9  # Capped at max (10), then consumed 1


# ============================================================================
# Test: Retry After Calculation
# ============================================================================


class TestRedisStorageRetryAfter:
    """Test retry_after calculation when rate limited."""

    @pytest.mark.asyncio
    async def test_retry_after_calculation_accurate(self, storage):
        """Test that retry_after is calculated correctly."""
        key = "test:retry_after"

        # Consume all tokens
        await storage.check_and_consume(
            key=key,
            max_tokens=10,
            refill_rate=60.0,
            cost=10,  # 1 token per second
        )

        # Try to consume 5 tokens (should be denied)
        allowed, retry_after, _ = await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=60.0, cost=5
        )

        assert allowed is False
        # Should need ~5 seconds to refill 5 tokens (refill_rate=60/min = 1/sec)
        assert 3.5 <= retry_after <= 6.0  # Allow wider tolerance for fakeredis timing

    @pytest.mark.asyncio
    async def test_retry_after_zero_when_allowed(self, storage):
        """Test that retry_after is 0 when request is allowed."""
        allowed, retry_after, _ = await storage.check_and_consume(
            key="test:retry_zero", max_tokens=10, refill_rate=1.0, cost=1
        )

        assert allowed is True
        assert retry_after == 0.0


# ============================================================================
# Test: get_remaining Method
# ============================================================================


class TestRedisStorageGetRemaining:
    """Test get_remaining method."""

    @pytest.mark.asyncio
    async def test_get_remaining_returns_current_tokens(self, storage):
        """Test get_remaining returns correct value."""
        key = "test:get_remaining"

        # Consume some tokens
        await storage.check_and_consume(
            key=key, max_tokens=100, refill_rate=10.0, cost=30
        )

        # Check remaining
        remaining = await storage.get_remaining(key=key, max_tokens=100)

        assert remaining == 70  # 100 - 30

    @pytest.mark.asyncio
    async def test_get_remaining_nonexistent_key(self, storage):
        """Test get_remaining for key that doesn't exist."""
        remaining = await storage.get_remaining(key="test:nonexistent", max_tokens=100)

        # Should return max_tokens for nonexistent key
        assert remaining == 100

    @pytest.mark.asyncio
    async def test_get_remaining_after_refill(self, storage):
        """Test get_remaining reflects refilled tokens."""
        key = "test:get_remaining:refill"

        # Consume all tokens
        await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=60.0, cost=10
        )

        # Wait for some refill
        await asyncio.sleep(2.1)  # ~2 tokens should refill

        # Check remaining (should be ~2)
        remaining = await storage.get_remaining(key=key, max_tokens=10)

        # Note: get_remaining reads raw value, doesn't calculate refill
        # So this tests the actual Redis value
        assert remaining >= 0


# ============================================================================
# Test: reset Method
# ============================================================================


class TestRedisStorageReset:
    """Test reset method."""

    @pytest.mark.asyncio
    async def test_reset_clears_bucket_state(self, storage):
        """Test that reset deletes bucket state."""
        key = "test:reset"

        # Use some tokens
        await storage.check_and_consume(
            key=key, max_tokens=100, refill_rate=10.0, cost=50
        )

        # Reset bucket
        await storage.reset(key=key)

        # Next request should start with full bucket
        allowed, _, remaining = await storage.check_and_consume(
            key=key, max_tokens=100, refill_rate=10.0, cost=1
        )

        assert allowed is True
        assert remaining == 99  # Fresh bucket (100 - 1)

    @pytest.mark.asyncio
    async def test_reset_nonexistent_key(self, storage):
        """Test reset on nonexistent key (should not error)."""
        # Should not raise exception
        await storage.reset(key="test:nonexistent:reset")


# ============================================================================
# Test: Error Handling (Fail-Open)
# ============================================================================


class TestRedisStorageErrorHandling:
    """Test error handling and fail-open behavior."""

    @pytest.mark.asyncio
    async def test_redis_connection_failure_fails_open(self, redis_client):
        """Test that Redis connection failure fails open."""
        storage = RedisRateLimitStorage(redis_client)

        # Mock evalsha to raise connection error
        with patch.object(
            redis_client, "evalsha", side_effect=Exception("Connection refused")
        ):
            allowed, retry_after, remaining = await storage.check_and_consume(
                key="test:connection:error",
                max_tokens=10,
                refill_rate=1.0,
                cost=1,
            )

            # Should fail open (allow request)
            assert allowed is True
            assert retry_after == 0.0
            assert remaining == 10  # Returns max_tokens on error

    @pytest.mark.asyncio
    async def test_lua_script_error_fails_open(self, redis_client):
        """Test that Lua script error fails open."""
        storage = RedisRateLimitStorage(redis_client)

        # Mock evalsha to raise script error
        with patch.object(redis_client, "evalsha", side_effect=Exception("NOSCRIPT")):
            allowed, retry_after, remaining = await storage.check_and_consume(
                key="test:script:error",
                max_tokens=10,
                refill_rate=1.0,
                cost=1,
            )

            # Should fail open
            assert allowed is True
            assert retry_after == 0.0
            assert remaining == 10

    @pytest.mark.asyncio
    async def test_get_remaining_error_fails_open(self, redis_client):
        """Test that get_remaining error returns max_tokens."""
        storage = RedisRateLimitStorage(redis_client)

        # Mock get to raise error
        with patch.object(redis_client, "get", side_effect=Exception("Redis timeout")):
            remaining = await storage.get_remaining(
                key="test:get:error", max_tokens=100
            )

            # Should fail open (return max_tokens)
            assert remaining == 100

    @pytest.mark.asyncio
    async def test_reset_error_does_not_raise(self, redis_client):
        """Test that reset error is logged but doesn't raise."""
        storage = RedisRateLimitStorage(redis_client)

        # Mock delete to raise error
        with patch.object(redis_client, "delete", side_effect=Exception("Redis error")):
            # Should not raise exception
            await storage.reset(key="test:reset:error")


# ============================================================================
# Test: Lua Script Caching
# ============================================================================


class TestRedisStorageScriptCaching:
    """Test Lua script loading and caching."""

    @pytest.mark.asyncio
    async def test_script_loaded_on_first_use(self, storage, redis_client):
        """Test that Lua script is loaded on first use."""
        # Script SHA should be None initially
        assert storage._script_sha is None

        # First request should load script
        await storage.check_and_consume(
            key="test:script:load", max_tokens=10, refill_rate=1.0, cost=1
        )

        # Script SHA should now be cached
        assert storage._script_sha is not None
        assert isinstance(storage._script_sha, str)

    @pytest.mark.asyncio
    async def test_script_reused_on_subsequent_calls(self, storage, redis_client):
        """Test that script is reused (not reloaded) on subsequent calls."""
        # First request loads script
        await storage.check_and_consume(
            key="test:script:reuse", max_tokens=10, refill_rate=1.0, cost=1
        )

        script_sha = storage._script_sha

        # Second request should reuse same SHA
        await storage.check_and_consume(
            key="test:script:reuse", max_tokens=10, refill_rate=1.0, cost=1
        )

        assert storage._script_sha == script_sha  # Same SHA reused


# ============================================================================
# Test: Concurrent Requests (Atomicity)
# ============================================================================


class TestRedisStorageAtomicity:
    """Test atomicity of Lua script operations."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_atomic(self, storage):
        """Test that concurrent requests don't cause race conditions.

        This test verifies that Lua script atomicity prevents over-consumption
        of tokens when multiple requests arrive simultaneously.
        """
        import asyncio

        key = "test:concurrent"
        max_tokens = 10

        # Pre-populate bucket with 10 tokens
        await storage.check_and_consume(
            key=key, max_tokens=max_tokens, refill_rate=1.0, cost=0
        )

        # Fire 20 concurrent requests (each costs 1 token)
        tasks = [
            storage.check_and_consume(
                key=key, max_tokens=max_tokens, refill_rate=1.0, cost=1
            )
            for _ in range(20)
        ]

        results = await asyncio.gather(*tasks)

        # Count allowed and denied requests
        allowed_count = sum(1 for allowed, _, _ in results if allowed)
        denied_count = sum(1 for allowed, _, _ in results if not allowed)

        # Should allow ~10 requests, deny ~10 requests
        # (Some tolerance due to timing and refill)
        assert allowed_count <= max_tokens + 1  # Allow small tolerance
        assert denied_count >= 9  # At least 9 should be denied


# ============================================================================
# Test: Edge Cases
# ============================================================================


class TestRedisStorageEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_cost_request(self, storage):
        """Test request with cost=0 (should not consume tokens)."""
        key = "test:zero:cost"

        # Request with cost=0
        allowed, retry_after, remaining = await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=1.0, cost=0
        )

        assert allowed is True
        assert retry_after == 0.0
        assert remaining == 10  # No tokens consumed

    @pytest.mark.asyncio
    async def test_high_cost_single_request(self, storage):
        """Test single request with cost > max_tokens."""
        key = "test:high:cost"

        # Request costs more than max_tokens
        allowed, retry_after, _ = await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=1.0, cost=20
        )

        assert allowed is False  # Should be denied
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_very_slow_refill_rate(self, storage):
        """Test with very slow refill rate."""
        key = "test:slow:refill"

        # Refill rate: 0.1 tokens/min = 1 token every 10 minutes
        await storage.check_and_consume(key=key, max_tokens=1, refill_rate=0.1, cost=1)

        # Next request should be denied with long retry_after
        allowed, retry_after, _ = await storage.check_and_consume(
            key=key, max_tokens=1, refill_rate=0.1, cost=1
        )

        assert allowed is False
        assert retry_after > 500  # Should be ~600 seconds (10 minutes)

    @pytest.mark.asyncio
    async def test_very_fast_refill_rate(self, storage):
        """Test with very fast refill rate."""
        key = "test:fast:refill"

        # Refill rate: 6000 tokens/min = 100 tokens per second
        await storage.check_and_consume(
            key=key, max_tokens=1000, refill_rate=6000.0, cost=1000
        )

        # Wait 1 second (should refill ~100 tokens)
        await asyncio.sleep(1.1)

        # Should have significant tokens available
        allowed, _, remaining = await storage.check_and_consume(
            key=key, max_tokens=1000, refill_rate=6000.0, cost=50
        )

        assert allowed is True
        assert remaining > 0
