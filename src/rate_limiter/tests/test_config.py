"""Unit tests for Rate Limiter configuration module.

Tests the configuration SSOT (Single Source of Truth) including:
- RateLimitStrategy enum
- RateLimitStorage enum
- RateLimitRule Pydantic model
- RateLimitConfig class methods

SOLID Principles Tested:
    - S: Configuration has single responsibility (no logic, just data)
    - O: Can add new strategies/storage without modifying existing code
    - D: Other components depend on this configuration
"""

import pytest
from pydantic import ValidationError

from src.rate_limiter.config import (
    RateLimitConfig,
    RateLimitRule,
    RateLimitStorage,
    RateLimitStrategy,
)


class TestRateLimitStrategy:
    """Test RateLimitStrategy enum."""

    def test_strategy_enum_values(self):
        """Test all strategy enum values are defined correctly."""
        assert RateLimitStrategy.TOKEN_BUCKET == "token_bucket"
        assert RateLimitStrategy.SLIDING_WINDOW == "sliding_window"
        assert RateLimitStrategy.FIXED_WINDOW == "fixed_window"

    def test_strategy_enum_members(self):
        """Test strategy enum has all expected members."""
        strategies = list(RateLimitStrategy)
        assert len(strategies) == 3
        assert RateLimitStrategy.TOKEN_BUCKET in strategies
        assert RateLimitStrategy.SLIDING_WINDOW in strategies
        assert RateLimitStrategy.FIXED_WINDOW in strategies


class TestRateLimitStorageEnum:
    """Test RateLimitStorage enum."""

    def test_storage_enum_values(self):
        """Test all storage enum values are defined correctly."""
        assert RateLimitStorage.REDIS == "redis"
        assert RateLimitStorage.POSTGRES == "postgres"
        assert RateLimitStorage.MEMORY == "memory"

    def test_storage_enum_members(self):
        """Test storage enum has all expected members."""
        storages = list(RateLimitStorage)
        assert len(storages) == 3
        assert RateLimitStorage.REDIS in storages
        assert RateLimitStorage.POSTGRES in storages
        assert RateLimitStorage.MEMORY in storages


class TestRateLimitRule:
    """Test RateLimitRule Pydantic model."""

    def test_create_valid_rule(self):
        """Test creating a valid rate limit rule."""
        rule = RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=20,
            refill_rate=5.0,
            scope="ip",
            enabled=True,
            cost=1,
        )
        assert rule.strategy == RateLimitStrategy.TOKEN_BUCKET
        assert rule.storage == RateLimitStorage.REDIS
        assert rule.max_tokens == 20
        assert rule.refill_rate == 5.0
        assert rule.scope == "ip"
        assert rule.enabled is True
        assert rule.cost == 1

    def test_rule_with_defaults(self):
        """Test rule creation with default values."""
        rule = RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=20,
            refill_rate=5.0,
            scope="ip",
        )
        # Default values
        assert rule.enabled is True
        assert rule.cost == 1

    def test_rule_is_frozen(self):
        """Test that RateLimitRule is immutable (frozen)."""
        rule = RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=20,
            refill_rate=5.0,
            scope="ip",
        )
        # Try to modify frozen model (should raise ValidationError)
        with pytest.raises(ValidationError):
            rule.max_tokens = 30

    def test_rule_validation_max_tokens_positive(self):
        """Test that max_tokens must be positive."""
        with pytest.raises(ValidationError):
            RateLimitRule(
                strategy=RateLimitStrategy.TOKEN_BUCKET,
                storage=RateLimitStorage.REDIS,
                max_tokens=0,  # Invalid: must be > 0
                refill_rate=5.0,
                scope="ip",
            )

    def test_rule_validation_refill_rate_positive(self):
        """Test that refill_rate must be positive."""
        with pytest.raises(ValidationError):
            RateLimitRule(
                strategy=RateLimitStrategy.TOKEN_BUCKET,
                storage=RateLimitStorage.REDIS,
                max_tokens=20,
                refill_rate=0.0,  # Invalid: must be > 0
                scope="ip",
            )

    def test_rule_validation_cost_positive(self):
        """Test that cost must be positive."""
        with pytest.raises(ValidationError):
            RateLimitRule(
                strategy=RateLimitStrategy.TOKEN_BUCKET,
                storage=RateLimitStorage.REDIS,
                max_tokens=20,
                refill_rate=5.0,
                scope="ip",
                cost=0,  # Invalid: must be > 0
            )


class TestRateLimitConfig:
    """Test RateLimitConfig class."""

    def test_config_has_rules(self):
        """Test that config has rate limit rules defined."""
        assert len(RateLimitConfig.RULES) > 0

    def test_config_auth_endpoints_exist(self):
        """Test that authentication endpoints are configured."""
        assert "POST /api/v1/auth/login" in RateLimitConfig.RULES
        assert "POST /api/v1/auth/register" in RateLimitConfig.RULES
        assert "POST /api/v1/auth/password-resets" in RateLimitConfig.RULES

    def test_config_provider_endpoints_exist(self):
        """Test that provider endpoints are configured."""
        assert "POST /api/v1/providers" in RateLimitConfig.RULES
        assert "GET /api/v1/providers" in RateLimitConfig.RULES
        assert "GET /api/v1/providers/{provider_id}" in RateLimitConfig.RULES

    def test_config_schwab_api_exists(self):
        """Test that Schwab API rate limit is configured."""
        assert "schwab_api" in RateLimitConfig.RULES

    def test_get_rule_existing_endpoint(self):
        """Test getting rule for existing endpoint."""
        rule = RateLimitConfig.get_rule("POST /api/v1/auth/login")
        assert rule is not None
        assert rule.strategy == RateLimitStrategy.TOKEN_BUCKET
        assert rule.storage == RateLimitStorage.REDIS
        assert rule.scope == "ip"

    def test_get_rule_nonexistent_endpoint(self):
        """Test getting rule for nonexistent endpoint returns None."""
        rule = RateLimitConfig.get_rule("POST /api/v1/nonexistent")
        assert rule is None

    def test_has_rule_existing_enabled(self):
        """Test has_rule returns True for existing enabled endpoint."""
        assert RateLimitConfig.has_rule("POST /api/v1/auth/login") is True

    def test_has_rule_nonexistent(self):
        """Test has_rule returns False for nonexistent endpoint."""
        assert RateLimitConfig.has_rule("POST /api/v1/nonexistent") is False

    def test_get_all_rules(self):
        """Test getting all rules returns copy of RULES dict."""
        all_rules = RateLimitConfig.get_all_rules()
        assert len(all_rules) == len(RateLimitConfig.RULES)
        assert all_rules is not RateLimitConfig.RULES  # Should be a copy

    def test_get_enabled_rules(self):
        """Test getting only enabled rules."""
        enabled_rules = RateLimitConfig.get_enabled_rules()
        # All rules should be enabled in current config
        assert len(enabled_rules) == len(RateLimitConfig.RULES)
        # Verify all returned rules are enabled
        for rule in enabled_rules.values():
            assert rule.enabled is True

    def test_login_rule_configuration(self):
        """Test login endpoint has correct configuration."""
        rule = RateLimitConfig.get_rule("POST /api/v1/auth/login")
        assert rule.max_tokens == 20
        assert rule.refill_rate == 5.0
        assert rule.scope == "ip"
        assert rule.enabled is True

    def test_register_rule_configuration(self):
        """Test register endpoint has correct configuration."""
        rule = RateLimitConfig.get_rule("POST /api/v1/auth/register")
        assert rule.max_tokens == 10
        assert rule.refill_rate == 2.0
        assert rule.scope == "ip"
        assert rule.enabled is True

    def test_password_reset_rule_configuration(self):
        """Test password reset endpoint has correct configuration."""
        rule = RateLimitConfig.get_rule("POST /api/v1/auth/password-resets")
        assert rule.max_tokens == 5
        assert rule.refill_rate == 0.2  # 1 token every 5 minutes
        assert rule.scope == "ip"
        assert rule.enabled is True

    def test_schwab_api_rule_configuration(self):
        """Test Schwab API has correct configuration matching their limits."""
        rule = RateLimitConfig.get_rule("schwab_api")
        assert rule.max_tokens == 100
        assert rule.refill_rate == 100.0  # Matches Schwab's 100 requests/min
        assert rule.scope == "user_provider"
        assert rule.enabled is True

    def test_all_rules_are_valid_pydantic_models(self):
        """Test that all configured rules are valid Pydantic models."""
        for endpoint, rule in RateLimitConfig.RULES.items():
            # Should not raise any exceptions
            assert isinstance(rule, RateLimitRule)
            assert rule.max_tokens > 0
            assert rule.refill_rate > 0
            assert rule.cost > 0
            assert rule.scope in ["ip", "user", "user_provider", "global"]
