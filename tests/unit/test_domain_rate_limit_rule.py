"""Unit tests for RateLimitRule and RateLimitResult value objects.

Tests validation, immutability, and computed properties.
"""

import pytest

from src.domain.enums import RateLimitScope
from src.domain.value_objects.rate_limit_rule import RateLimitResult, RateLimitRule


class TestRateLimitRule:
    """Tests for RateLimitRule value object."""

    def test_create_valid_rule(self) -> None:
        """Should create rule with valid parameters."""
        rule = RateLimitRule(
            max_tokens=5,
            refill_rate=5.0,
            scope=RateLimitScope.IP,
            cost=1,
            enabled=True,
        )

        assert rule.max_tokens == 5
        assert rule.refill_rate == 5.0
        assert rule.scope == RateLimitScope.IP
        assert rule.cost == 1
        assert rule.enabled is True

    def test_create_rule_with_defaults(self) -> None:
        """Should use default values for optional fields."""
        rule = RateLimitRule(
            max_tokens=10,
            refill_rate=10.0,
            scope=RateLimitScope.USER,
        )

        assert rule.cost == 1  # Default
        assert rule.enabled is True  # Default

    def test_create_rule_disabled(self) -> None:
        """Should create disabled rule."""
        rule = RateLimitRule(
            max_tokens=5,
            refill_rate=5.0,
            scope=RateLimitScope.IP,
            enabled=False,
        )

        assert rule.enabled is False

    def test_invalid_max_tokens_zero(self) -> None:
        """Should reject max_tokens <= 0."""
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            RateLimitRule(
                max_tokens=0,
                refill_rate=5.0,
                scope=RateLimitScope.IP,
            )

    def test_invalid_max_tokens_negative(self) -> None:
        """Should reject negative max_tokens."""
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            RateLimitRule(
                max_tokens=-5,
                refill_rate=5.0,
                scope=RateLimitScope.IP,
            )

    def test_invalid_refill_rate_zero(self) -> None:
        """Should reject refill_rate <= 0."""
        with pytest.raises(ValueError, match="refill_rate must be positive"):
            RateLimitRule(
                max_tokens=5,
                refill_rate=0.0,
                scope=RateLimitScope.IP,
            )

    def test_invalid_refill_rate_negative(self) -> None:
        """Should reject negative refill_rate."""
        with pytest.raises(ValueError, match="refill_rate must be positive"):
            RateLimitRule(
                max_tokens=5,
                refill_rate=-1.0,
                scope=RateLimitScope.IP,
            )

    def test_invalid_cost_zero(self) -> None:
        """Should reject cost <= 0."""
        with pytest.raises(ValueError, match="cost must be positive"):
            RateLimitRule(
                max_tokens=5,
                refill_rate=5.0,
                scope=RateLimitScope.IP,
                cost=0,
            )

    def test_invalid_cost_negative(self) -> None:
        """Should reject negative cost."""
        with pytest.raises(ValueError, match="cost must be positive"):
            RateLimitRule(
                max_tokens=5,
                refill_rate=5.0,
                scope=RateLimitScope.IP,
                cost=-1,
            )

    def test_immutability(self) -> None:
        """Should be immutable (frozen dataclass)."""
        rule = RateLimitRule(
            max_tokens=5,
            refill_rate=5.0,
            scope=RateLimitScope.IP,
        )

        with pytest.raises(AttributeError):
            rule.max_tokens = 10  # type: ignore[misc]

    def test_seconds_per_token_property(self) -> None:
        """Should calculate seconds between token refills."""
        # 5 tokens per minute = 1 token every 12 seconds
        rule = RateLimitRule(
            max_tokens=5,
            refill_rate=5.0,
            scope=RateLimitScope.IP,
        )
        assert rule.seconds_per_token == 12.0

        # 60 tokens per minute = 1 token per second
        rule2 = RateLimitRule(
            max_tokens=60,
            refill_rate=60.0,
            scope=RateLimitScope.USER,
        )
        assert rule2.seconds_per_token == 1.0

    def test_ttl_seconds_property(self) -> None:
        """Should calculate TTL as time to full refill + 60s buffer."""
        # 5 tokens at 5/min = 60 seconds to refill + 60 buffer = 120
        rule = RateLimitRule(
            max_tokens=5,
            refill_rate=5.0,
            scope=RateLimitScope.IP,
        )
        assert rule.ttl_seconds == 120

        # 100 tokens at 100/min = 60 seconds to refill + 60 buffer = 120
        rule2 = RateLimitRule(
            max_tokens=100,
            refill_rate=100.0,
            scope=RateLimitScope.USER,
        )
        assert rule2.ttl_seconds == 120

    def test_all_scopes(self) -> None:
        """Should accept all valid scopes."""
        for scope in RateLimitScope:
            rule = RateLimitRule(
                max_tokens=5,
                refill_rate=5.0,
                scope=scope,
            )
            assert rule.scope == scope


class TestRateLimitResult:
    """Tests for RateLimitResult value object."""

    def test_create_allowed_result(self) -> None:
        """Should create result for allowed request."""
        result = RateLimitResult(
            allowed=True,
            retry_after=0.0,
            remaining=4,
            limit=5,
            reset_seconds=60,
        )

        assert result.allowed is True
        assert result.retry_after == 0.0
        assert result.remaining == 4
        assert result.limit == 5
        assert result.reset_seconds == 60

    def test_create_denied_result(self) -> None:
        """Should create result for denied request."""
        result = RateLimitResult(
            allowed=False,
            retry_after=12.5,
            remaining=0,
            limit=5,
            reset_seconds=60,
        )

        assert result.allowed is False
        assert result.retry_after == 12.5
        assert result.remaining == 0

    def test_default_values(self) -> None:
        """Should use sensible defaults."""
        result = RateLimitResult(allowed=True)

        assert result.retry_after == 0.0
        assert result.remaining == 0
        assert result.limit == 0
        assert result.reset_seconds == 0

    def test_immutability(self) -> None:
        """Should be immutable (frozen dataclass)."""
        result = RateLimitResult(allowed=True, remaining=5)

        with pytest.raises(AttributeError):
            result.allowed = False  # type: ignore[misc]
