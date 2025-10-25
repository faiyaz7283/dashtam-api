"""Unit tests for RateLimiterService orchestrator.

Tests the service layer that orchestrates configuration, algorithms, and storage,
verifying dependency injection and fail-open behavior.

SOLID Principles Tested:
    - S: Service has single responsibility (orchestration only)
    - D: Service depends on abstractions (mocked algorithm and storage)
"""

import pytest
from unittest.mock import AsyncMock, patch

from src.rate_limiting.service import RateLimiterService


@pytest.fixture
def mock_algorithm():
    """Fixture providing mocked algorithm."""
    algorithm = AsyncMock()
    return algorithm


@pytest.fixture
def mock_storage():
    """Fixture providing mocked storage."""
    storage = AsyncMock()
    return storage


@pytest.fixture
def rate_limiter_service(mock_algorithm, mock_storage):
    """Fixture providing RateLimiterService with mocked dependencies."""
    return RateLimiterService(
        algorithm=mock_algorithm,
        storage=mock_storage,
    )


class TestRateLimiterService:
    """Test RateLimiterService orchestrator."""

    @pytest.mark.asyncio
    async def test_is_allowed_with_configured_endpoint(
        self, rate_limiter_service, mock_algorithm
    ):
        """Test rate limit check for configured endpoint."""
        # Mock algorithm returns success
        mock_algorithm.is_allowed.return_value = (True, 0.0)

        allowed, retry_after, rule = await rate_limiter_service.is_allowed(
            endpoint="POST /api/v1/auth/login",
            identifier="192.168.1.1",
            cost=1,
        )

        assert allowed is True
        assert retry_after == 0.0
        assert rule is not None
        assert rule.scope == "ip"

        # Verify algorithm was called
        mock_algorithm.is_allowed.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_allowed_rate_limited(self, rate_limiter_service, mock_algorithm):
        """Test rate limit check when rate limited."""
        # Mock algorithm returns rate limited
        mock_algorithm.is_allowed.return_value = (False, 12.0)

        allowed, retry_after, rule = await rate_limiter_service.is_allowed(
            endpoint="POST /api/v1/auth/login",
            identifier="192.168.1.1",
            cost=1,
        )

        assert allowed is False
        assert retry_after == 12.0
        assert rule is not None

    @pytest.mark.asyncio
    async def test_is_allowed_with_unconfigured_endpoint(
        self, rate_limiter_service, mock_algorithm
    ):
        """Test rate limit check for unconfigured endpoint (should allow)."""
        allowed, retry_after, rule = await rate_limiter_service.is_allowed(
            endpoint="POST /api/v1/nonexistent",
            identifier="192.168.1.1",
            cost=1,
        )

        # Should allow (no rate limiting configured)
        assert allowed is True
        assert retry_after == 0.0
        assert rule is None

        # Algorithm should not be called
        mock_algorithm.is_allowed.assert_not_called()

    @pytest.mark.asyncio
    async def test_is_allowed_with_custom_cost(
        self, rate_limiter_service, mock_algorithm
    ):
        """Test rate limit check with custom token cost."""
        mock_algorithm.is_allowed.return_value = (True, 0.0)

        allowed, retry_after, rule = await rate_limiter_service.is_allowed(
            endpoint="schwab_api",
            identifier="user:123:schwab",
            cost=5,  # Expensive operation
        )

        assert allowed is True

        # Verify algorithm called with cost=5
        call_args = mock_algorithm.is_allowed.call_args
        assert call_args[1]["cost"] == 5

    @pytest.mark.asyncio
    async def test_build_key_with_ip_scope(self, rate_limiter_service):
        """Test key building for IP-scoped rate limit."""
        key = rate_limiter_service._build_key(
            endpoint="POST /api/v1/auth/login",
            identifier="192.168.1.1",
            scope="ip",
        )
        assert key == "ip:192.168.1.1:POST /api/v1/auth/login"

    @pytest.mark.asyncio
    async def test_build_key_with_user_scope(self, rate_limiter_service):
        """Test key building for user-scoped rate limit."""
        key = rate_limiter_service._build_key(
            endpoint="GET /api/v1/providers",
            identifier="user:123",
            scope="user",
        )
        assert key == "user:user:123:GET /api/v1/providers"

    @pytest.mark.asyncio
    async def test_build_key_with_user_provider_scope(self, rate_limiter_service):
        """Test key building for user-per-provider scoped rate limit."""
        key = rate_limiter_service._build_key(
            endpoint="schwab_api",
            identifier="user:123:schwab",
            scope="user_provider",
        )
        assert key == "user_provider:user:123:schwab:schwab_api"

    @pytest.mark.asyncio
    async def test_fail_open_on_algorithm_error(
        self, rate_limiter_service, mock_algorithm
    ):
        """Test fail-open behavior when algorithm fails."""
        # Mock algorithm raises exception
        mock_algorithm.is_allowed.side_effect = Exception("Algorithm failed")

        allowed, retry_after, rule = await rate_limiter_service.is_allowed(
            endpoint="POST /api/v1/auth/login",
            identifier="192.168.1.1",
            cost=1,
        )

        # Should fail-open (allow request)
        assert allowed is True
        assert retry_after == 0.0
        assert rule is None

    @pytest.mark.asyncio
    async def test_fail_open_on_config_error(
        self, rate_limiter_service, mock_algorithm
    ):
        """Test fail-open behavior when config lookup fails."""
        with patch(
            "src.rate_limiting.service.RateLimitConfig.get_rule"
        ) as mock_get_rule:
            # Mock config raises exception
            mock_get_rule.side_effect = Exception("Config error")

            allowed, retry_after, rule = await rate_limiter_service.is_allowed(
                endpoint="POST /api/v1/auth/login",
                identifier="192.168.1.1",
                cost=1,
            )

            # Should fail-open
            assert allowed is True
            assert retry_after == 0.0
            assert rule is None

    @pytest.mark.asyncio
    async def test_multiple_endpoints_independent(
        self, rate_limiter_service, mock_algorithm
    ):
        """Test that different endpoints are rate limited independently."""
        # First endpoint: success
        mock_algorithm.is_allowed.return_value = (True, 0.0)
        allowed1, _, rule1 = await rate_limiter_service.is_allowed(
            endpoint="POST /api/v1/auth/login",
            identifier="192.168.1.1",
            cost=1,
        )
        assert allowed1 is True
        assert rule1.max_tokens == 20  # Login limit

        # Second endpoint: different limits
        mock_algorithm.is_allowed.return_value = (True, 0.0)
        allowed2, _, rule2 = await rate_limiter_service.is_allowed(
            endpoint="POST /api/v1/auth/register",
            identifier="192.168.1.1",
            cost=1,
        )
        assert allowed2 is True
        assert rule2.max_tokens == 10  # Register limit (different)

    @pytest.mark.asyncio
    async def test_passes_correct_parameters_to_algorithm(
        self, rate_limiter_service, mock_algorithm, mock_storage
    ):
        """Test that service passes correct parameters to algorithm."""
        mock_algorithm.is_allowed.return_value = (True, 0.0)

        await rate_limiter_service.is_allowed(
            endpoint="POST /api/v1/auth/login",
            identifier="192.168.1.1",
            cost=1,
        )

        # Verify algorithm called with correct parameters
        call_args = mock_algorithm.is_allowed.call_args
        assert call_args[1]["storage"] == mock_storage
        assert call_args[1]["key"] == "ip:192.168.1.1:POST /api/v1/auth/login"
        assert call_args[1]["rule"].max_tokens == 20
        assert call_args[1]["cost"] == 1

    @pytest.mark.asyncio
    async def test_schwab_api_rate_limit(self, rate_limiter_service, mock_algorithm):
        """Test Schwab API rate limit configuration."""
        mock_algorithm.is_allowed.return_value = (True, 0.0)

        allowed, retry_after, rule = await rate_limiter_service.is_allowed(
            endpoint="schwab_api",
            identifier="user:123:schwab",
            cost=1,
        )

        assert allowed is True
        assert rule is not None
        assert rule.max_tokens == 100  # Schwab limit
        assert rule.refill_rate == 100.0  # 100 requests/min
        assert rule.scope == "user_provider"

    @pytest.mark.asyncio
    async def test_different_identifiers_independent(
        self, rate_limiter_service, mock_algorithm
    ):
        """Test that different identifiers are rate limited independently."""
        mock_algorithm.is_allowed.return_value = (True, 0.0)

        # First identifier
        await rate_limiter_service.is_allowed(
            endpoint="POST /api/v1/auth/login",
            identifier="192.168.1.1",
            cost=1,
        )

        # Second identifier (different IP)
        await rate_limiter_service.is_allowed(
            endpoint="POST /api/v1/auth/login",
            identifier="192.168.1.2",
            cost=1,
        )

        # Verify different keys were built
        calls = mock_algorithm.is_allowed.call_args_list
        key1 = calls[0][1]["key"]
        key2 = calls[1][1]["key"]
        assert key1 == "ip:192.168.1.1:POST /api/v1/auth/login"
        assert key2 == "ip:192.168.1.2:POST /api/v1/auth/login"
        assert key1 != key2
