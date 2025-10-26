"""Unit tests for Token Bucket algorithm.

Tests the TokenBucketAlgorithm implementation with mocked storage backend,
verifying algorithm logic in isolation.

SOLID Principles Tested:
    - L: TokenBucketAlgorithm is substitutable for RateLimitAlgorithm
    - D: Algorithm depends on storage abstraction (mocked here)
"""

import pytest
from unittest.mock import AsyncMock

from src.rate_limiter.algorithms.token_bucket import TokenBucketAlgorithm
from src.rate_limiter.config import (
    RateLimitRule,
    RateLimitStrategy,
    RateLimitStorage,
)


@pytest.fixture
def token_bucket_algorithm():
    """Fixture providing TokenBucketAlgorithm instance."""
    return TokenBucketAlgorithm()


@pytest.fixture
def mock_storage():
    """Fixture providing mocked storage backend."""
    storage = AsyncMock()
    return storage


@pytest.fixture
def sample_rule():
    """Fixture providing sample rate limit rule."""
    return RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=20,
        refill_rate=5.0,
        scope="ip",
        enabled=True,
    )


class TestTokenBucketAlgorithm:
    """Test TokenBucketAlgorithm implementation."""

    @pytest.mark.asyncio
    async def test_is_allowed_success(
        self, token_bucket_algorithm, mock_storage, sample_rule
    ):
        """Test successful rate limit check (tokens available)."""
        # Mock storage returns success
        mock_storage.check_and_consume.return_value = (True, 0.0, 19)

        allowed, retry_after = await token_bucket_algorithm.is_allowed(
            storage=mock_storage,
            key="ip:192.168.1.1:login",
            rule=sample_rule,
            cost=1,
        )

        assert allowed is True
        assert retry_after == 0.0
        mock_storage.check_and_consume.assert_called_once_with(
            key="ip:192.168.1.1:login",
            max_tokens=20,
            refill_rate=5.0,
            cost=1,
        )

    @pytest.mark.asyncio
    async def test_is_allowed_rate_limited(
        self, token_bucket_algorithm, mock_storage, sample_rule
    ):
        """Test rate limited check (no tokens available)."""
        # Mock storage returns rate limited (12 seconds to wait)
        mock_storage.check_and_consume.return_value = (False, 12.0, 0)

        allowed, retry_after = await token_bucket_algorithm.is_allowed(
            storage=mock_storage,
            key="ip:192.168.1.1:login",
            rule=sample_rule,
            cost=1,
        )

        assert allowed is False
        assert retry_after == 12.0
        mock_storage.check_and_consume.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_allowed_with_custom_cost(
        self, token_bucket_algorithm, mock_storage, sample_rule
    ):
        """Test rate limit check with custom token cost."""
        # Mock storage returns success with cost=5
        mock_storage.check_and_consume.return_value = (True, 0.0, 15)

        allowed, retry_after = await token_bucket_algorithm.is_allowed(
            storage=mock_storage,
            key="user:123:schwab_api",
            rule=sample_rule,
            cost=5,  # Expensive operation
        )

        assert allowed is True
        assert retry_after == 0.0
        mock_storage.check_and_consume.assert_called_once_with(
            key="user:123:schwab_api",
            max_tokens=20,
            refill_rate=5.0,
            cost=5,
        )

    @pytest.mark.asyncio
    async def test_fail_open_on_storage_error(
        self, token_bucket_algorithm, mock_storage, sample_rule
    ):
        """Test fail-open behavior when storage fails."""
        # Mock storage raises exception
        mock_storage.check_and_consume.side_effect = Exception(
            "Redis connection failed"
        )

        allowed, retry_after = await token_bucket_algorithm.is_allowed(
            storage=mock_storage,
            key="ip:192.168.1.1:login",
            rule=sample_rule,
            cost=1,
        )

        # Should fail-open (allow request)
        assert allowed is True
        assert retry_after == 0.0

    @pytest.mark.asyncio
    async def test_fail_open_on_timeout(
        self, token_bucket_algorithm, mock_storage, sample_rule
    ):
        """Test fail-open behavior on storage timeout."""
        # Mock storage times out
        mock_storage.check_and_consume.side_effect = TimeoutError("Redis timeout")

        allowed, retry_after = await token_bucket_algorithm.is_allowed(
            storage=mock_storage,
            key="ip:192.168.1.1:login",
            rule=sample_rule,
            cost=1,
        )

        # Should fail-open
        assert allowed is True
        assert retry_after == 0.0

    @pytest.mark.asyncio
    async def test_multiple_requests_sequence(
        self, token_bucket_algorithm, mock_storage, sample_rule
    ):
        """Test sequence of multiple requests."""
        # First request: success (19 remaining)
        mock_storage.check_and_consume.return_value = (True, 0.0, 19)
        allowed1, retry1 = await token_bucket_algorithm.is_allowed(
            storage=mock_storage,
            key="ip:192.168.1.1:login",
            rule=sample_rule,
            cost=1,
        )
        assert allowed1 is True

        # Second request: success (18 remaining)
        mock_storage.check_and_consume.return_value = (True, 0.0, 18)
        allowed2, retry2 = await token_bucket_algorithm.is_allowed(
            storage=mock_storage,
            key="ip:192.168.1.1:login",
            rule=sample_rule,
            cost=1,
        )
        assert allowed2 is True

        # Third request: rate limited (0 remaining)
        mock_storage.check_and_consume.return_value = (False, 12.0, 0)
        allowed3, retry3 = await token_bucket_algorithm.is_allowed(
            storage=mock_storage,
            key="ip:192.168.1.1:login",
            rule=sample_rule,
            cost=1,
        )
        assert allowed3 is False
        assert retry3 == 12.0

    @pytest.mark.asyncio
    async def test_different_keys_independent(
        self, token_bucket_algorithm, mock_storage, sample_rule
    ):
        """Test that different keys are rate limited independently."""
        # First IP: success
        mock_storage.check_and_consume.return_value = (True, 0.0, 19)
        allowed1, _ = await token_bucket_algorithm.is_allowed(
            storage=mock_storage,
            key="ip:192.168.1.1:login",
            rule=sample_rule,
            cost=1,
        )
        assert allowed1 is True

        # Different IP: also success (independent buckets)
        mock_storage.check_and_consume.return_value = (True, 0.0, 19)
        allowed2, _ = await token_bucket_algorithm.is_allowed(
            storage=mock_storage,
            key="ip:192.168.1.2:login",
            rule=sample_rule,
            cost=1,
        )
        assert allowed2 is True

        # Verify different keys were passed
        assert mock_storage.check_and_consume.call_count == 2
        calls = mock_storage.check_and_consume.call_args_list
        assert calls[0][1]["key"] == "ip:192.168.1.1:login"
        assert calls[1][1]["key"] == "ip:192.168.1.2:login"

    @pytest.mark.asyncio
    async def test_respects_rule_parameters(self, token_bucket_algorithm, mock_storage):
        """Test that algorithm respects all rule parameters."""
        rule = RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=100,
            refill_rate=50.0,
            scope="user",
            enabled=True,
        )

        mock_storage.check_and_consume.return_value = (True, 0.0, 99)

        await token_bucket_algorithm.is_allowed(
            storage=mock_storage,
            key="user:123:api",
            rule=rule,
            cost=1,
        )

        # Verify storage called with correct parameters from rule
        mock_storage.check_and_consume.assert_called_once_with(
            key="user:123:api",
            max_tokens=100,
            refill_rate=50.0,
            cost=1,
        )
