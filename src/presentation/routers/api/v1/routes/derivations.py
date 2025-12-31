"""Derive runtime configurations from route metadata registry.

This module generates runtime configurations (auth dependencies, rate limit rules)
from the declarative Route Metadata Registry. This ensures consistency between
the registry and actual application behavior.

Two-Tier Rate Limit Configuration:
    This module implements Tier 2 - Policy Implementation.

    Tier 1 (registry.py): Assigns policies to endpoints
        Example: "Login endpoint uses AUTH_LOGIN policy"

    Tier 2 (this file): Defines what each policy means
        Example: "AUTH_LOGIN = 5 attempts/min per IP"

To Modify Rate Limits:
    Scenario 1: Change rate limit for ONE specific endpoint
        Where: registry.py
        What: Change the rate_limit_policy field
        Example: Make login more generous
            rate_limit_policy=RateLimitPolicy.API_READ

    Scenario 2: Change rate limit for ALL endpoints using a policy
        Where: This file (derivations.py)
        What: Update RateLimitRule in _create_rate_limit_rule()
        Example: Increase all AUTH_LOGIN endpoints from 5 to 10
            RateLimitPolicy.AUTH_LOGIN: RateLimitRule(max_tokens=10, ...)

Functions:
    build_rate_limit_rules: Generate rate limit rules dict from registry
    _create_rate_limit_rule: Map RateLimitPolicy enum to RateLimitRule (Tier 2)

Reference:
    - src/presentation/routers/api/v1/routes/registry.py (Tier 1: policy assignment)
    - src/infrastructure/rate_limit/config.py (public API for rules)
"""

from src.domain.enums import RateLimitScope
from src.domain.value_objects.rate_limit_rule import RateLimitRule
from src.presentation.routers.api.v1.routes.metadata import (
    RateLimitPolicy,
    RouteMetadata,
)


def build_rate_limit_rules(
    registry: list[RouteMetadata],
) -> dict[str, RateLimitRule]:
    """Build rate limit rules dict from route registry.

    Generates the RATE_LIMIT_RULES dict by iterating registry and mapping
    RateLimitPolicy enums to RateLimitRule objects. Endpoint keys use
    the format "{METHOD} {PATH}" (e.g., "POST /api/v1/sessions").

    Args:
        registry: List of route metadata entries from ROUTE_REGISTRY.

    Returns:
        Dict mapping endpoint strings to RateLimitRule objects.

    Example:
        >>> from src.presentation.routers.api.v1.routes.registry import ROUTE_REGISTRY
        >>> rules = build_rate_limit_rules(ROUTE_REGISTRY)
        >>> login_rule = rules["POST /api/v1/sessions"]
        >>> login_rule.max_tokens
        5
    """
    rules: dict[str, RateLimitRule] = {}

    for entry in registry:
        # Build endpoint key: "{METHOD} /api/v1{PATH}"
        # Note: Router adds /api/v1 prefix, so we must include it here
        endpoint = f"{entry.method.value} /api/v1{entry.path}"

        # Map RateLimitPolicy to RateLimitRule
        rule = _create_rate_limit_rule(entry.rate_limit_policy)
        rules[endpoint] = rule

    return rules


def _create_rate_limit_rule(policy: RateLimitPolicy) -> RateLimitRule:
    """Create RateLimitRule from RateLimitPolicy enum.

    Maps policy enums to concrete rate limit rules with specific
    max_tokens, refill_rate, and scope values.

    Args:
        policy: RateLimitPolicy enum value.

    Returns:
        RateLimitRule instance with policy-specific configuration.

    Example:
        >>> rule = _create_rate_limit_rule(RateLimitPolicy.AUTH_LOGIN)
        >>> rule.max_tokens
        5
        >>> rule.scope
        <RateLimitScope.IP: 'ip'>
    """
    # Map policy to rule configuration
    # Keep these in sync with src/infrastructure/rate_limit/config.py patterns
    mapping: dict[RateLimitPolicy, RateLimitRule] = {
        # Auth endpoints (IP-scoped, restrictive)
        RateLimitPolicy.AUTH_LOGIN: RateLimitRule(
            max_tokens=5,
            refill_rate=5.0,  # 1 token every 12 seconds
            scope=RateLimitScope.IP,
            cost=1,
            enabled=True,
        ),
        RateLimitPolicy.AUTH_REGISTER: RateLimitRule(
            max_tokens=3,
            refill_rate=3.0,  # 1 token every 20 seconds
            scope=RateLimitScope.IP,
            cost=1,
            enabled=True,
        ),
        RateLimitPolicy.AUTH_PASSWORD_RESET: RateLimitRule(
            max_tokens=3,
            refill_rate=1.0,  # 1 token per minute
            scope=RateLimitScope.IP,
            cost=1,
            enabled=True,
        ),
        RateLimitPolicy.AUTH_TOKEN_REFRESH: RateLimitRule(
            max_tokens=10,
            refill_rate=10.0,  # 1 token every 6 seconds
            scope=RateLimitScope.USER,
            cost=1,
            enabled=True,
        ),
        # Provider endpoints (moderate, user-scoped)
        RateLimitPolicy.PROVIDER_CONNECT: RateLimitRule(
            max_tokens=5,
            refill_rate=5.0,
            scope=RateLimitScope.USER,
            cost=1,
            enabled=True,
        ),
        RateLimitPolicy.PROVIDER_SYNC: RateLimitRule(
            max_tokens=10,
            refill_rate=5.0,
            scope=RateLimitScope.USER_PROVIDER,
            cost=1,
            enabled=True,
        ),
        # Standard API endpoints (generous, user-scoped)
        RateLimitPolicy.API_READ: RateLimitRule(
            max_tokens=100,
            refill_rate=100.0,  # ~1.67 tokens per second
            scope=RateLimitScope.USER,
            cost=1,
            enabled=True,
        ),
        RateLimitPolicy.API_WRITE: RateLimitRule(
            max_tokens=50,
            refill_rate=50.0,
            scope=RateLimitScope.USER,
            cost=1,
            enabled=True,
        ),
        # Expensive operations (restrictive, user-scoped)
        RateLimitPolicy.EXPENSIVE_EXPORT: RateLimitRule(
            max_tokens=5,
            refill_rate=1.0,  # 1 token per minute
            scope=RateLimitScope.USER,
            cost=1,
            enabled=True,
        ),
        RateLimitPolicy.REPORT: RateLimitRule(
            max_tokens=10,
            refill_rate=2.0,  # 1 token every 30 seconds
            scope=RateLimitScope.USER,
            cost=1,
            enabled=True,
        ),
        # Global limits (emergency brake, disabled by default)
        RateLimitPolicy.GLOBAL: RateLimitRule(
            max_tokens=10000,
            refill_rate=10000.0,
            scope=RateLimitScope.GLOBAL,
            cost=1,
            enabled=False,  # Enable only in emergencies
        ),
    }

    return mapping[policy]
