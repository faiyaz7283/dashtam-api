"""Unit tests for Dashtam application rate limit configuration.

Tests the application-specific rate limit rules defined in src.config.rate_limits.
This tests Dashtam's configuration, NOT the generic rate_limiter package.

Tests:
- Configuration completeness (all critical endpoints covered)
- Rule correctness (proper limits, scopes, strategies)
- Security requirements (stricter limits for sensitive endpoints)
"""


from src.config.rate_limits import (
    RATE_LIMIT_RULES,
    get_rate_limit_rule,
    has_rate_limit,
    get_all_rate_limit_rules,
    get_enabled_rate_limit_rules,
)
from src.rate_limiter.config import (
    RateLimitRule,
    RateLimitStrategy,
    RateLimitStorage,
)


class TestRateLimitConfiguration:
    """Test Dashtam application rate limit configuration."""

    def test_config_has_rules(self):
        """Test that config has rate limit rules defined."""
        assert len(RATE_LIMIT_RULES) > 0

    def test_config_auth_endpoints_exist(self):
        """Test that authentication endpoints are configured."""
        assert "POST /api/v1/auth/login" in RATE_LIMIT_RULES
        assert "POST /api/v1/auth/register" in RATE_LIMIT_RULES
        assert "POST /api/v1/auth/password-resets" in RATE_LIMIT_RULES
        assert "POST /api/v1/auth/verification/resend" in RATE_LIMIT_RULES

    def test_config_token_rotation_endpoints_exist(self):
        """Test that token rotation endpoints are configured."""
        assert "POST /api/v1/auth/tokens/rotate/user" in RATE_LIMIT_RULES
        assert "POST /api/v1/auth/tokens/rotate/global" in RATE_LIMIT_RULES
        assert "POST /api/v1/auth/tokens/rotate/provider" in RATE_LIMIT_RULES

    def test_config_provider_endpoints_exist(self):
        """Test that provider endpoints are configured."""
        assert "POST /api/v1/providers" in RATE_LIMIT_RULES
        assert "GET /api/v1/providers" in RATE_LIMIT_RULES
        assert "GET /api/v1/providers/{provider_id}" in RATE_LIMIT_RULES
        assert "PATCH /api/v1/providers/{provider_id}" in RATE_LIMIT_RULES
        assert "DELETE /api/v1/providers/{provider_id}" in RATE_LIMIT_RULES

    def test_config_schwab_api_exists(self):
        """Test that Schwab API rate limit is configured."""
        assert "schwab_api" in RATE_LIMIT_RULES

    def test_get_rate_limit_rule_existing_endpoint(self):
        """Test getting rule for existing endpoint."""
        rule = get_rate_limit_rule("POST /api/v1/auth/login")
        assert rule is not None
        assert rule.strategy == RateLimitStrategy.TOKEN_BUCKET
        assert rule.storage == RateLimitStorage.REDIS
        assert rule.scope == "ip"

    def test_get_rate_limit_rule_nonexistent_endpoint(self):
        """Test getting rule for nonexistent endpoint returns None."""
        rule = get_rate_limit_rule("POST /api/v1/nonexistent")
        assert rule is None

    def test_has_rate_limit_existing_enabled(self):
        """Test has_rate_limit returns True for existing enabled endpoint."""
        assert has_rate_limit("POST /api/v1/auth/login") is True

    def test_has_rate_limit_nonexistent(self):
        """Test has_rate_limit returns False for nonexistent endpoint."""
        assert has_rate_limit("POST /api/v1/nonexistent") is False

    def test_get_all_rate_limit_rules(self):
        """Test getting all rules returns copy of RATE_LIMIT_RULES dict."""
        all_rules = get_all_rate_limit_rules()
        assert len(all_rules) == len(RATE_LIMIT_RULES)
        assert all_rules is not RATE_LIMIT_RULES  # Should be a copy

    def test_get_enabled_rate_limit_rules(self):
        """Test getting only enabled rules."""
        enabled_rules = get_enabled_rate_limit_rules()
        # All rules should be enabled in current config
        assert len(enabled_rules) == len(RATE_LIMIT_RULES)
        # Verify all returned rules are enabled
        for rule in enabled_rules.values():
            assert rule.enabled is True

    def test_login_rule_configuration(self):
        """Test login endpoint has correct configuration."""
        rule = get_rate_limit_rule("POST /api/v1/auth/login")
        assert rule.max_tokens == 20
        assert rule.refill_rate == 5.0
        assert rule.scope == "ip"
        assert rule.enabled is True

    def test_register_rule_configuration(self):
        """Test register endpoint has correct configuration."""
        rule = get_rate_limit_rule("POST /api/v1/auth/register")
        assert rule.max_tokens == 10
        assert rule.refill_rate == 2.0
        assert rule.scope == "ip"
        assert rule.enabled is True

    def test_password_reset_rule_configuration(self):
        """Test password reset endpoint has correct configuration."""
        rule = get_rate_limit_rule("POST /api/v1/auth/password-resets")
        assert rule.max_tokens == 5
        assert rule.refill_rate == 0.2  # 1 token every 5 minutes
        assert rule.scope == "ip"
        assert rule.enabled is True

    def test_token_rotation_user_rule_configuration(self):
        """Test user token rotation endpoint has correct configuration."""
        rule = get_rate_limit_rule("POST /api/v1/auth/tokens/rotate/user")
        assert rule.max_tokens == 5
        assert rule.refill_rate == 0.33  # 5 per 15 minutes
        assert rule.scope == "user"
        assert rule.enabled is True

    def test_token_rotation_global_rule_configuration(self):
        """Test global token rotation endpoint has correct configuration."""
        rule = get_rate_limit_rule("POST /api/v1/auth/tokens/rotate/global")
        assert rule.max_tokens == 1
        assert rule.refill_rate == 0.0007  # 1 per day
        assert rule.scope == "global"
        assert rule.enabled is True

    def test_token_rotation_provider_rule_configuration(self):
        """Test provider token rotation endpoint has correct configuration."""
        rule = get_rate_limit_rule("POST /api/v1/auth/tokens/rotate/provider")
        assert rule.max_tokens == 5
        assert rule.refill_rate == 1.0  # 1 per minute
        assert rule.scope == "user_provider"
        assert rule.enabled is True

    def test_schwab_api_rule_configuration(self):
        """Test Schwab API has correct configuration matching their limits."""
        rule = get_rate_limit_rule("schwab_api")
        assert rule.max_tokens == 100
        assert rule.refill_rate == 100.0  # Matches Schwab's 100 requests/min
        assert rule.scope == "user_provider"
        assert rule.enabled is True

    def test_all_rules_are_valid_pydantic_models(self):
        """Test that all configured rules are valid Pydantic models."""
        for endpoint, rule in RATE_LIMIT_RULES.items():
            # Should not raise any exceptions
            assert isinstance(rule, RateLimitRule)
            assert rule.max_tokens > 0
            assert rule.refill_rate > 0
            assert rule.cost > 0
            assert rule.scope in ["ip", "user", "user_provider", "global"]
