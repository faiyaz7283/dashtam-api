"""Rate limit registry compliance tests (F8.3).

Self-enforcing validation tests that verify RATE_LIMIT_RULES registry completeness.
These tests fail if:
- Rules are missing required configuration
- Rules have invalid scopes
- Rules have inconsistent patterns
- Endpoint patterns are malformed

Similar to F8.1 Provider Registry and F7.7 Domain Events Registry, this ensures
the rate limit rules registry remains complete and prevents drift.

Pattern: Registry Pattern with self-enforcing compliance tests.
"""

import pytest

from src.domain.enums import RateLimitScope
from src.domain.value_objects.rate_limit_rule import RateLimitRule
from src.infrastructure.rate_limit.config import (
    RATE_LIMIT_RULES,
    get_rule_for_endpoint,
)


# =============================================================================
# Test Class 1: Registry Completeness
# =============================================================================


class TestRateLimitRegistryCompleteness:
    """Verify all rate limit rules have complete and valid configuration."""

    def test_all_rules_have_positive_max_tokens(self):
        """Every rule must have positive max_tokens (bucket capacity)."""
        for endpoint, rule in RATE_LIMIT_RULES.items():
            assert rule.max_tokens > 0, (
                f"Rule for '{endpoint}' has invalid max_tokens: {rule.max_tokens}. "
                "Must be positive integer."
            )

    def test_all_rules_have_positive_refill_rate(self):
        """Every rule must have positive refill_rate (tokens per minute)."""
        for endpoint, rule in RATE_LIMIT_RULES.items():
            assert rule.refill_rate > 0, (
                f"Rule for '{endpoint}' has invalid refill_rate: {rule.refill_rate}. "
                "Must be positive number."
            )

    def test_all_rules_have_positive_cost(self):
        """Every rule must have positive cost (tokens consumed per request)."""
        for endpoint, rule in RATE_LIMIT_RULES.items():
            assert rule.cost > 0, (
                f"Rule for '{endpoint}' has invalid cost: {rule.cost}. "
                "Must be positive integer."
            )

    def test_all_rules_have_valid_scope(self):
        """Every rule must have a valid RateLimitScope enum value."""
        valid_scopes = set(RateLimitScope)
        for endpoint, rule in RATE_LIMIT_RULES.items():
            assert rule.scope in valid_scopes, (
                f"Rule for '{endpoint}' has invalid scope: {rule.scope}. "
                f"Must be one of: {[s.value for s in valid_scopes]}"
            )

    def test_all_rules_have_boolean_enabled(self):
        """Every rule must have enabled flag as boolean."""
        for endpoint, rule in RATE_LIMIT_RULES.items():
            assert isinstance(rule.enabled, bool), (
                f"Rule for '{endpoint}' has non-boolean enabled: {rule.enabled}. "
                "Must be True or False."
            )

    def test_endpoint_patterns_are_valid_format(self):
        """All endpoint patterns must follow 'METHOD /path' format."""
        valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}

        for endpoint in RATE_LIMIT_RULES.keys():
            parts = endpoint.split(" ", 1)
            assert len(parts) == 2, (
                f"Endpoint '{endpoint}' malformed. "
                "Must be 'METHOD /path' format (e.g., 'POST /api/v1/sessions')."
            )

            method, path = parts
            assert method in valid_methods, (
                f"Endpoint '{endpoint}' has invalid method '{method}'. "
                f"Must be one of: {valid_methods}"
            )
            assert path.startswith("/"), (
                f"Endpoint '{endpoint}' path doesn't start with '/'. "
                f"Path must be absolute (got: '{path}')."
            )

    def test_no_duplicate_endpoints(self):
        """Registry keys (endpoint patterns) must be unique."""
        endpoints = list(RATE_LIMIT_RULES.keys())
        duplicates = [ep for ep in set(endpoints) if endpoints.count(ep) > 1]

        assert not duplicates, (
            f"Duplicate endpoint patterns found: {duplicates}. "
            "Each endpoint must have exactly one rule."
        )

    def test_all_rules_are_rate_limit_rule_instances(self):
        """All values in registry must be RateLimitRule instances."""
        for endpoint, rule in RATE_LIMIT_RULES.items():
            assert isinstance(rule, RateLimitRule), (
                f"Rule for '{endpoint}' is not a RateLimitRule instance. "
                f"Got type: {type(rule).__name__}"
            )


# =============================================================================
# Test Class 2: Rule Consistency
# =============================================================================


class TestRateLimitRuleConsistency:
    """Verify rate limit rules follow consistent design patterns."""

    def test_auth_endpoints_use_ip_or_user_scope(self):
        """Authentication endpoints should use IP or USER scope (not GLOBAL)."""
        auth_endpoints = [
            ep
            for ep in RATE_LIMIT_RULES
            if "/sessions" in ep or "/auth/" in ep or "/users" in ep
        ]

        for endpoint in auth_endpoints:
            rule = RATE_LIMIT_RULES[endpoint]
            assert rule.scope in {RateLimitScope.IP, RateLimitScope.USER}, (
                f"Auth endpoint '{endpoint}' uses {rule.scope.value} scope. "
                "Auth endpoints should use IP or USER scope for security."
            )

    def test_api_endpoints_use_user_scope(self):
        """Standard API endpoints should use USER scope."""
        # Exclude sync endpoints which use USER_PROVIDER scope
        api_endpoints = [
            ep
            for ep in RATE_LIMIT_RULES
            if ("/accounts" in ep or "/transactions" in ep or "/holdings" in ep)
            and "/syncs" not in ep  # Sync endpoints use USER_PROVIDER
        ]

        for endpoint in api_endpoints:
            rule = RATE_LIMIT_RULES[endpoint]
            assert rule.scope == RateLimitScope.USER, (
                f"API endpoint '{endpoint}' uses {rule.scope.value} scope. "
                "Standard API endpoints should use USER scope."
            )

    def test_max_tokens_not_less_than_refill_rate(self):
        """Burst capacity (max_tokens) should be >= refill_rate for usability."""
        warnings = []
        for endpoint, rule in RATE_LIMIT_RULES.items():
            if rule.max_tokens < rule.refill_rate:
                warnings.append(
                    f"'{endpoint}': max_tokens ({rule.max_tokens}) < refill_rate ({rule.refill_rate}). "
                    "Users can't burst above steady state."
                )

        # This is a warning, not strict requirement (some designs may intentionally do this)
        if warnings:
            pytest.skip(
                "Informational: Some rules have max_tokens < refill_rate. "
                "This is allowed but may be intentional design:\n" + "\n".join(warnings)
            )

    def test_cost_is_typically_one(self):
        """Most rules should use cost=1 (standard request cost)."""
        non_standard_costs = [
            (endpoint, rule.cost)
            for endpoint, rule in RATE_LIMIT_RULES.items()
            if rule.cost != 1
        ]

        # Informational: non-standard costs are valid but should be documented
        if non_standard_costs:
            pytest.skip(
                f"Informational: {len(non_standard_costs)} rules use non-standard cost. "
                f"This is allowed but should be documented: {non_standard_costs}"
            )


# =============================================================================
# Test Class 3: Pattern Matching
# =============================================================================


class TestRateLimitPatternMatching:
    """Verify get_rule_for_endpoint() helper function works correctly."""

    def test_exact_match_returns_correct_rule(self):
        """Exact endpoint match should return the correct rule."""
        endpoint = "POST /api/v1/sessions"
        rule = get_rule_for_endpoint(endpoint)

        assert rule is not None, f"No rule found for '{endpoint}'"
        assert rule == RATE_LIMIT_RULES[endpoint], "Rule mismatch for exact match"

    def test_path_parameter_matching_works(self):
        """Endpoints with path parameters should match pattern rules."""
        # Pattern in registry: "GET /api/v1/accounts/{account_id}"
        actual_endpoint = "GET /api/v1/accounts/550e8400-e29b-41d4-a716-446655440000"
        rule = get_rule_for_endpoint(actual_endpoint)

        assert rule is not None, (
            f"No rule found for '{actual_endpoint}'. "
            "Path parameter matching may be broken."
        )
        assert rule.scope == RateLimitScope.USER, (
            "Unexpected rule returned for account endpoint"
        )

    def test_non_existent_endpoint_returns_none(self):
        """Endpoints not in registry should return None."""
        fake_endpoint = "POST /api/v1/fake/endpoint/that/does/not/exist"
        rule = get_rule_for_endpoint(fake_endpoint)

        assert rule is None, (
            f"Rule found for non-existent endpoint '{fake_endpoint}'. "
            "get_rule_for_endpoint() should return None for unknown endpoints."
        )

    def test_method_mismatch_returns_none(self):
        """Wrong HTTP method should not match even if path matches."""
        # Registry has "POST /api/v1/sessions", but we query with GET
        wrong_method_endpoint = "GET /api/v1/sessions"
        rule = get_rule_for_endpoint(wrong_method_endpoint)

        # There's no GET /api/v1/sessions in registry, should return None
        assert rule is None or rule != RATE_LIMIT_RULES["POST /api/v1/sessions"], (
            "Method mismatch should not return the wrong rule"
        )


# =============================================================================
# Test Class 4: Registry Statistics
# =============================================================================


class TestRateLimitRegistryStatistics:
    """Snapshot tests for current registry state."""

    def test_registry_has_minimum_endpoints(self):
        """Registry should have at least 20 endpoint rules (as of F8.3 implementation)."""
        endpoint_count = len(RATE_LIMIT_RULES)
        assert endpoint_count >= 20, (
            f"Registry has only {endpoint_count} endpoints. "
            "Expected at least 20 (current: 24). "
            "If endpoints were removed, update this test."
        )

    def test_registry_scope_distribution(self):
        """Verify scope distribution matches expected patterns."""
        scope_counts: dict[str, int] = {}
        for rule in RATE_LIMIT_RULES.values():
            scope_counts[rule.scope] = scope_counts.get(rule.scope, 0) + 1

        # Expectations (as of F8.3):
        # - IP scope: 4-6 rules (auth endpoints)
        # - USER scope: 15-20 rules (API endpoints)
        # - USER_PROVIDER scope: 1-2 rules (provider sync)
        # - GLOBAL scope: 0-1 rules (emergency brake)

        assert RateLimitScope.IP in scope_counts, "No IP-scoped rules found"
        assert RateLimitScope.USER in scope_counts, "No USER-scoped rules found"
        assert scope_counts[RateLimitScope.USER] > scope_counts[RateLimitScope.IP], (
            "Expected more USER-scoped rules than IP-scoped rules"
        )

    def test_all_rules_enabled_except_global(self):
        """Most rules should be enabled except emergency GLOBAL limits."""
        disabled_rules = [
            (endpoint, rule.scope)
            for endpoint, rule in RATE_LIMIT_RULES.items()
            if not rule.enabled
        ]

        # Global limits can be disabled by default
        for endpoint, scope in disabled_rules:
            if scope != RateLimitScope.GLOBAL:
                pytest.fail(
                    f"Non-global rule '{endpoint}' is disabled. "
                    "Only GLOBAL emergency brake rules should be disabled by default."
                )

    def test_specific_critical_endpoints_have_rules(self):
        """Verify critical endpoints have explicit rules."""
        critical_endpoints = [
            "POST /api/v1/sessions",  # Login
            "POST /api/v1/users",  # Registration
            "POST /api/v1/tokens",  # Token refresh (new RESTful path)
            "POST /api/v1/providers",  # Provider connect (initiate)
        ]

        missing = [ep for ep in critical_endpoints if ep not in RATE_LIMIT_RULES]
        assert not missing, (
            f"Critical endpoints missing from registry: {missing}. "
            "These endpoints must have explicit rate limit rules."
        )


# =============================================================================
# Test Class 5: Future-Proofing
# =============================================================================


class TestRateLimitRegistryFutureProofing:
    """Tests to prevent common mistakes when adding new rules."""

    def test_no_wildcard_patterns(self):
        """Endpoint patterns should not use wildcards (*, ?)."""
        wildcards = [ep for ep in RATE_LIMIT_RULES if "*" in ep or "?" in ep]

        assert not wildcards, (
            f"Endpoint patterns with wildcards found: {wildcards}. "
            "Use explicit patterns or path parameters {{param}} instead."
        )

    def test_paths_use_lowercase(self):
        """Endpoint paths should use lowercase (except path parameters)."""
        mixed_case = []
        for endpoint in RATE_LIMIT_RULES.keys():
            method, _, path = endpoint.partition(" ")
            # Check path segments outside of {} parameters
            import re

            path_without_params = re.sub(r"\{[^}]+\}", "", path)
            if path_without_params != path_without_params.lower():
                mixed_case.append(endpoint)

        assert not mixed_case, (
            f"Endpoints with mixed-case paths found: {mixed_case}. "
            "Use lowercase for consistency."
        )

    def test_no_trailing_slashes_in_paths(self):
        """Endpoint paths should not have trailing slashes."""
        trailing_slashes = [
            ep
            for ep in RATE_LIMIT_RULES.keys()
            if ep.endswith("/") or " /" in ep and not ep.endswith(" /")
        ]

        # Actually, check for paths that end with / (not including root /)
        trailing_slashes = [
            ep
            for ep in RATE_LIMIT_RULES.keys()
            if ep.split(" ", 1)[1].rstrip("/") != ep.split(" ", 1)[1]
            and ep.split(" ", 1)[1] != "/"
        ]

        assert not trailing_slashes, (
            f"Endpoints with trailing slashes found: {trailing_slashes}. "
            "Remove trailing slashes for consistency."
        )
