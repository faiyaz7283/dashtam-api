"""Unit tests for RateLimitScope enum and config path matching.

Tests scope enum values and the RATE_LIMIT_RULES configuration.
"""

from src.domain.enums import RateLimitScope
from src.infrastructure.rate_limit.config import (
    RATE_LIMIT_RULES,
    get_rule_for_endpoint,
)


class TestRateLimitScope:
    """Tests for RateLimitScope enum."""

    def test_scope_values(self) -> None:
        """Should have expected scope values."""
        assert RateLimitScope.IP.value == "ip"
        assert RateLimitScope.USER.value == "user"
        assert RateLimitScope.USER_PROVIDER.value == "user_provider"
        assert RateLimitScope.GLOBAL.value == "global"

    def test_all_scopes_exist(self) -> None:
        """Should have exactly 4 scopes."""
        scopes = list(RateLimitScope)
        assert len(scopes) == 4

    def test_scope_is_string_enum(self) -> None:
        """Should be a string enum for easy serialization."""
        for scope in RateLimitScope:
            assert isinstance(scope.value, str)


class TestRateLimitRulesConfig:
    """Tests for RATE_LIMIT_RULES configuration."""

    def test_rules_exist(self) -> None:
        """Should have configured rules."""
        assert len(RATE_LIMIT_RULES) > 0

    def test_login_endpoint_rule(self) -> None:
        """Should have restrictive rule for login endpoint."""
        rule = RATE_LIMIT_RULES.get("POST /api/v1/sessions")
        assert rule is not None
        assert rule.scope == RateLimitScope.IP
        assert rule.max_tokens <= 10  # Restrictive
        assert rule.enabled is True

    def test_register_endpoint_rule(self) -> None:
        """Should have restrictive rule for registration endpoint."""
        rule = RATE_LIMIT_RULES.get("POST /api/v1/users")
        assert rule is not None
        assert rule.scope == RateLimitScope.IP
        assert rule.max_tokens <= 5  # Very restrictive
        assert rule.enabled is True

    def test_all_rules_valid(self) -> None:
        """All configured rules should be valid."""
        for endpoint, rule in RATE_LIMIT_RULES.items():
            assert rule.max_tokens > 0
            assert rule.refill_rate > 0
            assert rule.cost > 0
            assert isinstance(rule.scope, RateLimitScope)


class TestGetRuleForEndpoint:
    """Tests for get_rule_for_endpoint function."""

    def test_exact_match(self) -> None:
        """Should find rule by exact endpoint match."""
        rule = get_rule_for_endpoint("POST /api/v1/sessions")
        assert rule is not None
        assert rule.scope == RateLimitScope.IP

    def test_path_parameter_match(self) -> None:
        """Should match endpoints with path parameters."""
        # Exact endpoint with parameter placeholder in config
        rule = get_rule_for_endpoint("GET /api/v1/accounts/123")
        assert rule is not None
        assert rule.scope == RateLimitScope.USER

    def test_path_parameter_match_uuid(self) -> None:
        """Should match endpoints with UUID path parameters."""
        rule = get_rule_for_endpoint(
            "GET /api/v1/accounts/550e8400-e29b-41d4-a716-446655440000"
        )
        assert rule is not None

    def test_no_match_returns_none(self) -> None:
        """Should return None for unconfigured endpoints."""
        rule = get_rule_for_endpoint("GET /api/v1/unknown-endpoint")
        assert rule is None

    def test_method_matters(self) -> None:
        """Different HTTP methods should match different rules."""
        # POST /api/v1/sessions has a rule
        post_rule = get_rule_for_endpoint("POST /api/v1/sessions")
        assert post_rule is not None

        # GET /api/v1/sessions may not have a rule (or different rule)
        get_rule = get_rule_for_endpoint("GET /api/v1/sessions")
        # Either None or different rule
        assert get_rule is None or get_rule != post_rule

    def test_nested_path_parameter(self) -> None:
        """Should match nested path parameters."""
        # /api/v1/accounts/{account_id}/transactions
        rule = get_rule_for_endpoint("GET /api/v1/accounts/123/transactions")
        assert rule is not None

    def test_provider_sync_endpoint(self) -> None:
        """Should match provider sync endpoint with USER_PROVIDER scope."""
        rule = get_rule_for_endpoint("POST /api/v1/providers/123/sync")
        assert rule is not None
        assert rule.scope == RateLimitScope.USER_PROVIDER

    def test_empty_endpoint_returns_none(self) -> None:
        """Should handle empty endpoint gracefully."""
        rule = get_rule_for_endpoint("")
        assert rule is None

    def test_malformed_endpoint_returns_none(self) -> None:
        """Should handle malformed endpoint gracefully."""
        rule = get_rule_for_endpoint("invalid")
        assert rule is None
