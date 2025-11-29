"""Unit tests for TokenBucketAdapter algorithm logic.

Tests adapter behavior with mocked storage to verify:
- Key construction for different scopes
- Rule lookup and disabled rule handling
- Event publishing
- Fail-open behavior
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.result import Failure, Success
from src.domain.enums import RateLimitScope
from src.domain.errors import RateLimitError
from src.domain.value_objects.rate_limit_rule import RateLimitRule
from src.infrastructure.rate_limit.token_bucket_adapter import TokenBucketAdapter


@pytest.fixture
def mock_storage():
    """Create mock storage."""
    storage = AsyncMock()
    storage.check_and_consume = AsyncMock(return_value=Success(value=(True, 0.0, 4)))
    storage.get_remaining = AsyncMock(return_value=Success(value=5))
    storage.reset = AsyncMock(return_value=Success(value=None))
    return storage


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
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
        "POST /api/v1/sessions": RateLimitRule(
            max_tokens=5,
            refill_rate=5.0,
            scope=RateLimitScope.IP,
            cost=1,
            enabled=True,
        ),
        "GET /api/v1/accounts": RateLimitRule(
            max_tokens=100,
            refill_rate=100.0,
            scope=RateLimitScope.USER,
            cost=1,
            enabled=True,
        ),
        "POST /api/v1/providers/{provider_id}/sync": RateLimitRule(
            max_tokens=10,
            refill_rate=10.0,
            scope=RateLimitScope.USER_PROVIDER,
            cost=1,
            enabled=True,
        ),
        "GET /api/v1/status": RateLimitRule(
            max_tokens=1000,
            refill_rate=1000.0,
            scope=RateLimitScope.GLOBAL,
            cost=1,
            enabled=True,
        ),
        "POST /api/v1/disabled": RateLimitRule(
            max_tokens=5,
            refill_rate=5.0,
            scope=RateLimitScope.IP,
            cost=1,
            enabled=False,
        ),
    }


@pytest.fixture
def adapter(mock_storage, test_rules, mock_event_bus, mock_logger):
    """Create adapter with mocked dependencies."""
    return TokenBucketAdapter(
        storage=mock_storage,
        rules=test_rules,
        event_bus=mock_event_bus,
        logger=mock_logger,
    )


class TestTokenBucketAdapterKeyConstruction:
    """Tests for Redis key construction based on scope."""

    @pytest.mark.asyncio
    async def test_ip_scope_key(self, adapter, mock_storage) -> None:
        """Should construct key with IP scope format."""
        await adapter.is_allowed(
            endpoint="POST /api/v1/sessions",
            identifier="192.168.1.1",
        )

        # Verify storage was called with correct key
        call_args = mock_storage.check_and_consume.call_args
        key_base = call_args.kwargs["key_base"]
        assert key_base == "rate_limit:ip:192.168.1.1:POST /api/v1/sessions"

    @pytest.mark.asyncio
    async def test_user_scope_key(self, adapter, mock_storage) -> None:
        """Should construct key with USER scope format."""
        user_id = "user-123"
        await adapter.is_allowed(
            endpoint="GET /api/v1/accounts",
            identifier=user_id,
        )

        call_args = mock_storage.check_and_consume.call_args
        key_base = call_args.kwargs["key_base"]
        assert key_base == f"rate_limit:user:{user_id}:GET /api/v1/accounts"

    @pytest.mark.asyncio
    async def test_user_provider_scope_key(self, adapter, mock_storage) -> None:
        """Should construct key with USER_PROVIDER scope format."""
        identifier = "user-123:provider-456"
        await adapter.is_allowed(
            endpoint="POST /api/v1/providers/{provider_id}/sync",
            identifier=identifier,
        )

        call_args = mock_storage.check_and_consume.call_args
        key_base = call_args.kwargs["key_base"]
        assert "rate_limit:user_provider:" in key_base

    @pytest.mark.asyncio
    async def test_global_scope_key(self, adapter, mock_storage) -> None:
        """Should construct key with GLOBAL scope format (no identifier)."""
        await adapter.is_allowed(
            endpoint="GET /api/v1/status",
            identifier="ignored",
        )

        call_args = mock_storage.check_and_consume.call_args
        key_base = call_args.kwargs["key_base"]
        assert key_base == "rate_limit:global:GET /api/v1/status"


class TestTokenBucketAdapterRuleLookup:
    """Tests for rule lookup behavior."""

    @pytest.mark.asyncio
    async def test_unconfigured_endpoint_allowed(self, adapter) -> None:
        """Unconfigured endpoints should be allowed (fail-open)."""
        result = await adapter.is_allowed(
            endpoint="GET /api/v1/unknown",
            identifier="test",
        )

        assert isinstance(result, Success)
        assert result.value.allowed is True

    @pytest.mark.asyncio
    async def test_disabled_rule_allowed(self, adapter) -> None:
        """Disabled rules should allow all requests."""
        result = await adapter.is_allowed(
            endpoint="POST /api/v1/disabled",
            identifier="test",
        )

        assert isinstance(result, Success)
        assert result.value.allowed is True
        # Should return max_tokens as remaining
        assert result.value.remaining == 5

    @pytest.mark.asyncio
    async def test_enabled_rule_checks_storage(self, adapter, mock_storage) -> None:
        """Enabled rules should check storage."""
        await adapter.is_allowed(
            endpoint="POST /api/v1/sessions",
            identifier="192.168.1.1",
        )

        mock_storage.check_and_consume.assert_called_once()


class TestTokenBucketAdapterIsAllowed:
    """Tests for is_allowed method."""

    @pytest.mark.asyncio
    async def test_allowed_returns_success(self, adapter) -> None:
        """Should return Success with allowed=True when tokens available."""
        result = await adapter.is_allowed(
            endpoint="POST /api/v1/sessions",
            identifier="192.168.1.1",
        )

        assert isinstance(result, Success)
        assert result.value.allowed is True
        assert result.value.retry_after == 0.0

    @pytest.mark.asyncio
    async def test_denied_returns_success_with_retry_after(
        self, adapter, mock_storage
    ) -> None:
        """Should return Success with allowed=False when rate limited."""
        mock_storage.check_and_consume.return_value = Success(value=(False, 12.5, 0))

        result = await adapter.is_allowed(
            endpoint="POST /api/v1/sessions",
            identifier="192.168.1.1",
        )

        assert isinstance(result, Success)
        assert result.value.allowed is False
        assert result.value.retry_after == 12.5
        assert result.value.remaining == 0

    @pytest.mark.asyncio
    async def test_custom_cost(self, adapter, mock_storage) -> None:
        """Should pass custom cost to storage."""
        await adapter.is_allowed(
            endpoint="POST /api/v1/sessions",
            identifier="192.168.1.1",
            cost=5,
        )

        call_args = mock_storage.check_and_consume.call_args
        assert call_args.kwargs["cost"] == 5

    @pytest.mark.asyncio
    async def test_result_includes_limit_and_reset(self, adapter) -> None:
        """Result should include limit and reset_seconds from rule."""
        result = await adapter.is_allowed(
            endpoint="POST /api/v1/sessions",
            identifier="192.168.1.1",
        )

        assert result.value.limit == 5  # max_tokens from rule
        assert result.value.reset_seconds > 0  # ttl_seconds from rule


class TestTokenBucketAdapterEventPublishing:
    """Tests for domain event publishing."""

    @pytest.mark.asyncio
    async def test_publishes_attempted_event(self, adapter, mock_event_bus) -> None:
        """Should publish RateLimitCheckAttempted event."""
        await adapter.is_allowed(
            endpoint="POST /api/v1/sessions",
            identifier="192.168.1.1",
        )

        # First publish call should be Attempted event
        calls = mock_event_bus.publish.call_args_list
        assert len(calls) >= 1
        first_event = calls[0][0][0]
        assert first_event.__class__.__name__ == "RateLimitCheckAttempted"

    @pytest.mark.asyncio
    async def test_publishes_allowed_event_on_success(
        self, adapter, mock_event_bus
    ) -> None:
        """Should publish RateLimitCheckAllowed when allowed."""
        await adapter.is_allowed(
            endpoint="POST /api/v1/sessions",
            identifier="192.168.1.1",
        )

        # Should have Attempted and Allowed events
        calls = mock_event_bus.publish.call_args_list
        event_names = [c[0][0].__class__.__name__ for c in calls]
        assert "RateLimitCheckAllowed" in event_names

    @pytest.mark.asyncio
    async def test_publishes_denied_event_on_rate_limit(
        self, adapter, mock_storage, mock_event_bus
    ) -> None:
        """Should publish RateLimitCheckDenied when rate limited."""
        mock_storage.check_and_consume.return_value = Success(value=(False, 12.0, 0))

        await adapter.is_allowed(
            endpoint="POST /api/v1/sessions",
            identifier="192.168.1.1",
        )

        calls = mock_event_bus.publish.call_args_list
        event_names = [c[0][0].__class__.__name__ for c in calls]
        assert "RateLimitCheckDenied" in event_names


class TestTokenBucketAdapterFailOpen:
    """Tests for fail-open behavior."""

    @pytest.mark.asyncio
    async def test_storage_failure_returns_allowed(self, adapter, mock_storage) -> None:
        """Should return allowed=True if storage fails."""
        from src.core.enums import ErrorCode

        # Storage returns Failure
        mock_storage.check_and_consume.return_value = Failure(
            error=RateLimitError(
                code=ErrorCode.RATE_LIMIT_CHECK_FAILED,
                message="Redis connection failed",
            )
        )

        result = await adapter.is_allowed(
            endpoint="POST /api/v1/sessions",
            identifier="192.168.1.1",
        )

        # Should still return Success with allowed=True
        assert isinstance(result, Success)
        assert result.value.allowed is True

    @pytest.mark.asyncio
    async def test_event_publish_failure_continues(
        self, adapter, mock_event_bus
    ) -> None:
        """Should continue if event publishing fails."""
        mock_event_bus.publish.side_effect = Exception("Event bus down")

        # Should not raise, should still return result
        result = await adapter.is_allowed(
            endpoint="POST /api/v1/sessions",
            identifier="192.168.1.1",
        )

        assert isinstance(result, Success)


class TestTokenBucketAdapterGetRemaining:
    """Tests for get_remaining method."""

    @pytest.mark.asyncio
    async def test_returns_remaining_tokens(self, adapter, mock_storage) -> None:
        """Should return remaining tokens from storage."""
        mock_storage.get_remaining.return_value = Success(value=3)

        result = await adapter.get_remaining(
            endpoint="POST /api/v1/sessions",
            identifier="192.168.1.1",
        )

        assert isinstance(result, Success)
        assert result.value == 3

    @pytest.mark.asyncio
    async def test_unconfigured_endpoint_returns_zero(self, adapter) -> None:
        """Unconfigured endpoints should return 0."""
        result = await adapter.get_remaining(
            endpoint="GET /api/v1/unknown",
            identifier="test",
        )

        assert isinstance(result, Success)
        assert result.value == 0


class TestTokenBucketAdapterReset:
    """Tests for reset method."""

    @pytest.mark.asyncio
    async def test_reset_calls_storage(self, adapter, mock_storage) -> None:
        """Should call storage reset."""
        result = await adapter.reset(
            endpoint="POST /api/v1/sessions",
            identifier="192.168.1.1",
        )

        assert isinstance(result, Success)
        mock_storage.reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_unconfigured_endpoint_succeeds(self, adapter) -> None:
        """Reset for unconfigured endpoint should succeed (nothing to reset)."""
        result = await adapter.reset(
            endpoint="GET /api/v1/unknown",
            identifier="test",
        )

        assert isinstance(result, Success)
