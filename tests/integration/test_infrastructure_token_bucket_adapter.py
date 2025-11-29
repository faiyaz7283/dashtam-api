"""Integration tests for TokenBucketAdapter with real Redis.

Tests full adapter flow including:
- Storage integration
- Event publishing
- Complete rate limit scenarios
"""

import pytest
import pytest_asyncio
from redis.asyncio import ConnectionPool, Redis
from unittest.mock import AsyncMock, MagicMock

from src.core.config import settings
from src.core.result import Success
from src.domain.enums import RateLimitScope
from src.domain.value_objects.rate_limit_rule import RateLimitRule
from src.infrastructure.rate_limit.redis_storage import RedisStorage
from src.infrastructure.rate_limit.token_bucket_adapter import TokenBucketAdapter


@pytest_asyncio.fixture
async def redis_client():
    """Create Redis client for testing."""
    pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=5,
        decode_responses=False,
    )
    client = Redis(connection_pool=pool)
    await client.ping()
    yield client
    await client.aclose()
    await pool.disconnect()


@pytest_asyncio.fixture
async def clean_keys(redis_client):
    """Cleanup rate limit keys after each test."""
    yield
    keys = await redis_client.keys("rate_limit:*")
    if keys:
        await redis_client.delete(*keys)


@pytest.fixture
def mock_event_bus():
    """Create mock event bus for testing."""
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_logger():
    """Create mock logger."""
    logger = MagicMock()
    logger.debug = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    return logger


@pytest.fixture
def test_rules():
    """Create test rate limit rules."""
    return {
        "POST /api/v1/login": RateLimitRule(
            max_tokens=5,
            refill_rate=5.0,  # 1 token per 12 seconds
            scope=RateLimitScope.IP,
            cost=1,
            enabled=True,
        ),
        "GET /api/v1/data": RateLimitRule(
            max_tokens=10,
            refill_rate=60.0,  # 1 token per second
            scope=RateLimitScope.USER,
            cost=1,
            enabled=True,
        ),
        "POST /api/v1/expensive": RateLimitRule(
            max_tokens=10,
            refill_rate=10.0,
            scope=RateLimitScope.USER,
            cost=5,  # Higher cost
            enabled=True,
        ),
    }


@pytest_asyncio.fixture
async def adapter(redis_client, test_rules, mock_event_bus, mock_logger):
    """Create adapter with real Redis storage."""
    storage = RedisStorage(redis_client=redis_client)
    return TokenBucketAdapter(
        storage=storage,
        rules=test_rules,
        event_bus=mock_event_bus,
        logger=mock_logger,
    )


@pytest.mark.integration
class TestAdapterFullFlow:
    """Tests for complete rate limit flow."""

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, adapter, clean_keys) -> None:
        """First request should be allowed."""
        result = await adapter.is_allowed(
            endpoint="POST /api/v1/login",
            identifier="192.168.1.1",
        )

        assert isinstance(result, Success)
        assert result.value.allowed is True
        assert result.value.remaining == 4  # 5 - 1

    @pytest.mark.asyncio
    async def test_multiple_requests_consume_tokens(self, adapter, clean_keys) -> None:
        """Multiple requests should consume tokens."""
        identifier = "192.168.1.100"

        for expected_remaining in [4, 3, 2, 1, 0]:
            result = await adapter.is_allowed(
                endpoint="POST /api/v1/login",
                identifier=identifier,
            )
            assert result.value.remaining == expected_remaining

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, adapter, clean_keys) -> None:
        """Should deny request when rate limit exceeded."""
        identifier = "192.168.1.200"

        # Exhaust all tokens
        for _ in range(5):
            await adapter.is_allowed(
                endpoint="POST /api/v1/login",
                identifier=identifier,
            )

        # 6th request should be denied
        result = await adapter.is_allowed(
            endpoint="POST /api/v1/login",
            identifier=identifier,
        )

        assert result.value.allowed is False
        assert result.value.retry_after > 0
        assert result.value.remaining == 0

    @pytest.mark.asyncio
    async def test_different_identifiers_isolated(self, adapter, clean_keys) -> None:
        """Different identifiers should have separate buckets."""
        # Exhaust bucket for IP 1
        for _ in range(5):
            await adapter.is_allowed(
                endpoint="POST /api/v1/login",
                identifier="10.0.0.1",
            )

        # IP 1 should be rate limited
        result1 = await adapter.is_allowed(
            endpoint="POST /api/v1/login",
            identifier="10.0.0.1",
        )
        assert result1.value.allowed is False

        # IP 2 should still be allowed
        result2 = await adapter.is_allowed(
            endpoint="POST /api/v1/login",
            identifier="10.0.0.2",
        )
        assert result2.value.allowed is True

    @pytest.mark.asyncio
    async def test_different_endpoints_isolated(self, adapter, clean_keys) -> None:
        """Different endpoints should have separate buckets."""
        user_id = "user-123"

        # Exhaust bucket for /data endpoint
        for _ in range(10):
            await adapter.is_allowed(
                endpoint="GET /api/v1/data",
                identifier=user_id,
            )

        # /data should be rate limited
        result1 = await adapter.is_allowed(
            endpoint="GET /api/v1/data",
            identifier=user_id,
        )
        assert result1.value.allowed is False

        # /expensive should still be allowed (different endpoint)
        result2 = await adapter.is_allowed(
            endpoint="POST /api/v1/expensive",
            identifier=user_id,
        )
        assert result2.value.allowed is True


@pytest.mark.integration
class TestAdapterWithCost:
    """Tests for variable cost operations."""

    @pytest.mark.asyncio
    async def test_high_cost_operation(self, adapter, clean_keys) -> None:
        """High cost operations should consume more tokens."""
        user_id = "user-cost-test"

        # First request costs 5 tokens (default for this endpoint)
        result1 = await adapter.is_allowed(
            endpoint="POST /api/v1/expensive",
            identifier=user_id,
        )
        assert result1.value.remaining == 5  # 10 - 5

        # Second request should also succeed
        result2 = await adapter.is_allowed(
            endpoint="POST /api/v1/expensive",
            identifier=user_id,
        )
        assert result2.value.remaining == 0  # 5 - 5

        # Third request should be denied
        result3 = await adapter.is_allowed(
            endpoint="POST /api/v1/expensive",
            identifier=user_id,
        )
        assert result3.value.allowed is False


@pytest.mark.integration
class TestAdapterEventPublishing:
    """Tests for event publishing integration."""

    @pytest.mark.asyncio
    async def test_events_published_on_allowed(
        self, adapter, mock_event_bus, clean_keys
    ) -> None:
        """Should publish Attempted and Allowed events."""
        await adapter.is_allowed(
            endpoint="POST /api/v1/login",
            identifier="192.168.1.1",
        )

        # Should have published 2 events
        assert mock_event_bus.publish.call_count == 2

        # Check event types
        calls = mock_event_bus.publish.call_args_list
        event_names = [c[0][0].__class__.__name__ for c in calls]
        assert "RateLimitCheckAttempted" in event_names
        assert "RateLimitCheckAllowed" in event_names

    @pytest.mark.asyncio
    async def test_events_published_on_denied(
        self, adapter, mock_event_bus, clean_keys
    ) -> None:
        """Should publish Attempted and Denied events."""
        # Exhaust tokens
        for _ in range(5):
            await adapter.is_allowed(
                endpoint="POST /api/v1/login",
                identifier="192.168.1.50",
            )

        # Reset mock to count only the denied request
        mock_event_bus.publish.reset_mock()

        # This request should be denied
        await adapter.is_allowed(
            endpoint="POST /api/v1/login",
            identifier="192.168.1.50",
        )

        calls = mock_event_bus.publish.call_args_list
        event_names = [c[0][0].__class__.__name__ for c in calls]
        assert "RateLimitCheckAttempted" in event_names
        assert "RateLimitCheckDenied" in event_names


@pytest.mark.integration
class TestAdapterReset:
    """Tests for rate limit reset."""

    @pytest.mark.asyncio
    async def test_reset_restores_bucket(self, adapter, clean_keys) -> None:
        """Reset should restore bucket to full capacity."""
        identifier = "192.168.1.99"

        # Exhaust bucket
        for _ in range(5):
            await adapter.is_allowed(
                endpoint="POST /api/v1/login",
                identifier=identifier,
            )

        # Verify exhausted
        result1 = await adapter.is_allowed(
            endpoint="POST /api/v1/login",
            identifier=identifier,
        )
        assert result1.value.allowed is False

        # Reset
        reset_result = await adapter.reset(
            endpoint="POST /api/v1/login",
            identifier=identifier,
        )
        assert isinstance(reset_result, Success)

        # Should be allowed again
        result2 = await adapter.is_allowed(
            endpoint="POST /api/v1/login",
            identifier=identifier,
        )
        assert result2.value.allowed is True
        assert result2.value.remaining == 4


@pytest.mark.integration
class TestAdapterGetRemaining:
    """Tests for get_remaining method."""

    @pytest.mark.asyncio
    async def test_get_remaining_accurate(self, adapter, clean_keys) -> None:
        """get_remaining should return accurate count."""
        identifier = "user-remaining"

        # Consume 3 tokens
        for _ in range(3):
            await adapter.is_allowed(
                endpoint="GET /api/v1/data",
                identifier=identifier,
            )

        # Check remaining
        result = await adapter.get_remaining(
            endpoint="GET /api/v1/data",
            identifier=identifier,
        )

        assert isinstance(result, Success)
        assert result.value == 7  # 10 - 3 = 7
