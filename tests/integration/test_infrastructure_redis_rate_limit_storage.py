"""Integration tests for RedisStorage rate limit storage.

Tests atomic Lua script execution and token bucket behavior with real Redis.
"""

import pytest
import pytest_asyncio
from redis.asyncio import ConnectionPool, Redis

from src.core.config import settings
from src.core.result import Success
from src.domain.enums import RateLimitScope
from src.domain.value_objects.rate_limit_rule import RateLimitRule
from src.infrastructure.rate_limit.redis_storage import RedisStorage


@pytest_asyncio.fixture
async def redis_client():
    """Create Redis client for testing."""
    pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=5,
        decode_responses=False,  # Lua scripts need bytes
    )
    client = Redis(connection_pool=pool)
    await client.ping()
    yield client
    await client.aclose()
    await pool.disconnect()


@pytest_asyncio.fixture
async def storage(redis_client):
    """Create RedisStorage instance."""
    return RedisStorage(redis_client=redis_client)


@pytest_asyncio.fixture
async def clean_keys(redis_client):
    """Cleanup rate limit keys after each test."""
    yield
    # Delete all rate limit keys
    keys = await redis_client.keys("rate_limit:*")
    if keys:
        await redis_client.delete(*keys)


@pytest.fixture
def test_rule():
    """Create a test rate limit rule."""
    return RateLimitRule(
        max_tokens=5,
        refill_rate=60.0,  # 1 token per second for easier testing
        scope=RateLimitScope.IP,
        cost=1,
        enabled=True,
    )


@pytest.mark.integration
class TestRedisStorageCheckAndConsume:
    """Tests for check_and_consume method."""

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, storage, test_rule, clean_keys) -> None:
        """First request should be allowed with full bucket."""
        result = await storage.check_and_consume(
            key_base="rate_limit:test:first",
            rule=test_rule,
        )

        assert isinstance(result, Success)
        allowed, retry_after, remaining = result.value
        assert allowed is True
        assert retry_after == 0.0
        assert remaining == 4  # 5 - 1 = 4

    @pytest.mark.asyncio
    async def test_consecutive_requests_consume_tokens(
        self, storage, test_rule, clean_keys
    ) -> None:
        """Consecutive requests should consume tokens."""
        key = "rate_limit:test:consecutive"

        # First request
        result1 = await storage.check_and_consume(key_base=key, rule=test_rule)
        assert result1.value[2] == 4  # remaining

        # Second request
        result2 = await storage.check_and_consume(key_base=key, rule=test_rule)
        assert result2.value[2] == 3

        # Third request
        result3 = await storage.check_and_consume(key_base=key, rule=test_rule)
        assert result3.value[2] == 2

    @pytest.mark.asyncio
    async def test_bucket_exhaustion_denies_request(
        self, storage, test_rule, clean_keys
    ) -> None:
        """Should deny request when bucket is exhausted."""
        key = "rate_limit:test:exhaust"
        now = 1000.0  # Fixed timestamp to avoid timing issues

        # Exhaust all 5 tokens at same timestamp
        for _ in range(5):
            await storage.check_and_consume(key_base=key, rule=test_rule, now_ts=now)

        # 6th request should be denied (same timestamp = no refill)
        result = await storage.check_and_consume(
            key_base=key, rule=test_rule, now_ts=now
        )
        allowed, retry_after, remaining = result.value

        assert allowed is False
        assert retry_after > 0
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_retry_after_calculation(self, storage, clean_keys) -> None:
        """Should calculate correct retry_after seconds."""
        # Rule: 5 tokens, 5/min refill = 1 token every 12 seconds
        rule = RateLimitRule(
            max_tokens=5,
            refill_rate=5.0,
            scope=RateLimitScope.IP,
        )
        key = "rate_limit:test:retry"

        # Exhaust all tokens
        for _ in range(5):
            await storage.check_and_consume(key_base=key, rule=rule)

        # Check retry_after
        result = await storage.check_and_consume(key_base=key, rule=rule)
        _, retry_after, _ = result.value

        # Should be around 12 seconds (1 token at 5/min)
        assert 10 <= retry_after <= 14

    @pytest.mark.asyncio
    async def test_custom_cost(self, storage, clean_keys) -> None:
        """Should consume multiple tokens for higher cost operations."""
        rule = RateLimitRule(
            max_tokens=10,
            refill_rate=60.0,
            scope=RateLimitScope.USER,
        )
        key = "rate_limit:test:cost"

        # Request with cost=3
        result = await storage.check_and_consume(key_base=key, rule=rule, cost=3)
        assert result.value[2] == 7  # 10 - 3 = 7

        # Another request with cost=5
        result2 = await storage.check_and_consume(key_base=key, rule=rule, cost=5)
        assert result2.value[2] == 2  # 7 - 5 = 2

    @pytest.mark.asyncio
    async def test_token_refill_over_time(self, storage, clean_keys) -> None:
        """Should refill tokens based on elapsed time."""
        # Rule: 5 tokens, 60/min refill = 1 token per second
        rule = RateLimitRule(
            max_tokens=5,
            refill_rate=60.0,
            scope=RateLimitScope.IP,
        )
        key = "rate_limit:test:refill"
        now = 1000.0  # Fixed timestamp

        # Consume all tokens at time=1000
        for _ in range(5):
            await storage.check_and_consume(key_base=key, rule=rule, now_ts=now)

        # Check at time=1003 (3 seconds later = 3 tokens refilled)
        result = await storage.check_and_consume(
            key_base=key, rule=rule, now_ts=now + 3
        )
        allowed, _, remaining = result.value

        assert allowed is True
        assert remaining == 2  # Had 0, refilled 3, consumed 1 = 2

    @pytest.mark.asyncio
    async def test_bucket_caps_at_max_tokens(
        self, storage, test_rule, clean_keys
    ) -> None:
        """Refill should not exceed max_tokens."""
        key = "rate_limit:test:cap"
        now = 1000.0

        # Consume 2 tokens
        await storage.check_and_consume(key_base=key, rule=test_rule, now_ts=now)
        await storage.check_and_consume(key_base=key, rule=test_rule, now_ts=now)

        # Wait a long time (100 seconds with 60/min = 100 tokens refilled)
        result = await storage.check_and_consume(
            key_base=key, rule=test_rule, now_ts=now + 100
        )
        _, _, remaining = result.value

        # Should cap at max_tokens - 1 (after consuming 1)
        assert remaining == 4  # max 5, consumed 1 = 4


@pytest.mark.integration
class TestRedisStorageGetRemaining:
    """Tests for get_remaining method."""

    @pytest.mark.asyncio
    async def test_get_remaining_full_bucket(
        self, storage, test_rule, clean_keys
    ) -> None:
        """Should return max_tokens for new bucket."""
        result = await storage.get_remaining(
            key_base="rate_limit:test:remaining:new",
            rule=test_rule,
        )

        assert isinstance(result, Success)
        # New bucket starts full
        assert result.value == 5

    @pytest.mark.asyncio
    async def test_get_remaining_after_consumption(
        self, storage, test_rule, clean_keys
    ) -> None:
        """Should return correct remaining after consumption."""
        key = "rate_limit:test:remaining:consumed"

        # Consume 2 tokens
        await storage.check_and_consume(key_base=key, rule=test_rule)
        await storage.check_and_consume(key_base=key, rule=test_rule)

        result = await storage.get_remaining(key_base=key, rule=test_rule)
        assert result.value == 3

    @pytest.mark.asyncio
    async def test_get_remaining_does_not_consume(
        self, storage, test_rule, clean_keys
    ) -> None:
        """get_remaining should not consume tokens."""
        key = "rate_limit:test:remaining:no-consume"

        # Check remaining multiple times
        for _ in range(10):
            result = await storage.get_remaining(key_base=key, rule=test_rule)
            assert result.value == 5  # Always full


@pytest.mark.integration
class TestRedisStorageReset:
    """Tests for reset method."""

    @pytest.mark.asyncio
    async def test_reset_restores_full_bucket(
        self, storage, test_rule, clean_keys
    ) -> None:
        """Reset should restore bucket to full capacity."""
        key = "rate_limit:test:reset"

        # Exhaust bucket
        for _ in range(5):
            await storage.check_and_consume(key_base=key, rule=test_rule)

        # Verify exhausted
        result1 = await storage.check_and_consume(key_base=key, rule=test_rule)
        assert result1.value[0] is False  # denied

        # Reset
        reset_result = await storage.reset(key_base=key, rule=test_rule)
        assert isinstance(reset_result, Success)

        # Should be allowed again
        result2 = await storage.check_and_consume(key_base=key, rule=test_rule)
        allowed, _, remaining = result2.value
        assert allowed is True
        assert remaining == 4  # 5 - 1


@pytest.mark.integration
class TestRedisStorageFailOpen:
    """Tests for fail-open behavior."""

    @pytest.mark.asyncio
    async def test_check_and_consume_returns_success_always(
        self, storage, test_rule, clean_keys
    ) -> None:
        """check_and_consume should never return Failure (fail-open)."""
        # Even with valid inputs, should always return Success
        result = await storage.check_and_consume(
            key_base="rate_limit:test:failopen",
            rule=test_rule,
        )
        assert isinstance(result, Success)
