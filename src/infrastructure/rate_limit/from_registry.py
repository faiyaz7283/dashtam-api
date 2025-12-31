"""Generated rate limit rules from Route Metadata Registry.

This module generates RATE_LIMIT_RULES from the declarative ROUTE_REGISTRY,
replacing hand-written rate limit configuration. Rules are automatically derived
from RateLimitPolicy enums in the registry.

Two-Tier Configuration Pattern:
    Rate limits use a two-tier system (similar to CSS classes):

    Tier 1 - Policy Assignment (registry.py):
        Each endpoint is assigned a policy category.
        Example: POST /api/v1/sessions → AUTH_LOGIN policy

    Tier 2 - Policy Implementation (derivations.py):
        Each policy category has concrete limits.
        Example: AUTH_LOGIN → 5 attempts/min per IP

    This file: Combines both tiers to generate the final rules dict.

To Modify Rate Limits:
    ONE endpoint: Update rate_limit_policy in registry.py
    ALL endpoints in a policy: Update RateLimitRule in derivations.py

Exports:
    RATE_LIMIT_RULES: Dict mapping endpoints to rate limit rules (auto-generated)
    get_rule_for_endpoint: Lookup function with path parameter matching

Usage:
    from src.infrastructure.rate_limit.from_registry import RATE_LIMIT_RULES

    # Lookup rule for endpoint
    rule = RATE_LIMIT_RULES.get("POST /api/v1/sessions")

Reference:
    - src/presentation/routers/api/v1/routes/registry.py (Tier 1: policy assignment)
    - src/presentation/routers/api/v1/routes/derivations.py (Tier 2: policy implementation)
"""

from src.domain.value_objects.rate_limit_rule import RateLimitRule
from src.presentation.routers.api.v1.routes.derivations import (
    build_rate_limit_rules,
)
from src.presentation.routers.api.v1.routes.registry import ROUTE_REGISTRY


# =============================================================================
# Generated Rate Limit Rules (Single Source of Truth)
# =============================================================================
# These rules are automatically generated from ROUTE_REGISTRY.
# DO NOT modify this dict manually - update the registry instead.

RATE_LIMIT_RULES: dict[str, RateLimitRule] = build_rate_limit_rules(ROUTE_REGISTRY)
"""Endpoint to rate limit rule mapping (generated from registry).

Generated at module import time from ROUTE_REGISTRY. Endpoint format is
"{METHOD} {PATH}" (e.g., "POST /api/v1/sessions").

To modify rate limits:
    1. Update the RateLimitPolicy in ROUTE_REGISTRY
    2. Or update the policy mapping in derivations.py

DO NOT modify this dict directly - it will be regenerated on next import.
"""


# =============================================================================
# Lookup Functions
# =============================================================================


def get_rule_for_endpoint(endpoint: str) -> RateLimitRule | None:
    """Get rate limit rule for endpoint.

    Supports exact match and path parameter patterns (e.g., /accounts/{id}).

    Args:
        endpoint: Endpoint string (e.g., "GET /api/v1/accounts/123").

    Returns:
        RateLimitRule if found, None otherwise.

    Example:
        >>> rule = get_rule_for_endpoint("GET /api/v1/accounts/abc-123")
        >>> rule.max_tokens
        100
    """
    # Try exact match first
    if endpoint in RATE_LIMIT_RULES:
        return RATE_LIMIT_RULES[endpoint]

    # Try pattern matching for path parameters
    method, _, path = endpoint.partition(" ")
    if not path:
        return None

    for pattern, rule in RATE_LIMIT_RULES.items():
        pattern_method, _, pattern_path = pattern.partition(" ")
        if method != pattern_method:
            continue

        # Check if paths match (handling {param} placeholders)
        if _paths_match(path, pattern_path):
            return rule

    return None


def _paths_match(actual: str, pattern: str) -> bool:
    """Check if actual path matches pattern with placeholders.

    Args:
        actual: Actual request path (e.g., "/api/v1/accounts/123").
        pattern: Pattern path (e.g., "/api/v1/accounts/{account_id}").

    Returns:
        True if paths match, False otherwise.

    Example:
        >>> _paths_match("/api/v1/accounts/123", "/api/v1/accounts/{id}")
        True
        >>> _paths_match("/api/v1/accounts", "/api/v1/accounts/{id}")
        False
    """
    actual_parts = actual.strip("/").split("/")
    pattern_parts = pattern.strip("/").split("/")

    if len(actual_parts) != len(pattern_parts):
        return False

    for actual_part, pattern_part in zip(actual_parts, pattern_parts, strict=True):
        if pattern_part.startswith("{") and pattern_part.endswith("}"):
            continue  # Placeholder matches anything
        if actual_part != pattern_part:
            return False

    return True
