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

from src.core.config import settings
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
        endpoint = f"{entry.method.value} {settings.api_v1_prefix}{entry.path}"

        # Map RateLimitPolicy to RateLimitRule
        rule = _create_rate_limit_rule(entry.rate_limit_policy)
        rules[endpoint] = rule

    return rules


def _rule(
    max_tokens: int,
    refill_rate: float,
    scope: RateLimitScope,
    *,
    enabled: bool = True,
) -> RateLimitRule:
    """Factory for rate limit rules with sensible defaults.

    Creates RateLimitRule with cost=1 (standard) and configurable enabled flag.
    Reduces boilerplate when defining rate limit policies.

    Args:
        max_tokens: Maximum tokens in bucket.
        refill_rate: Token refill rate per minute.
        scope: Rate limit scope (IP, USER, etc.).
        enabled: Whether rule is active (default: True).

    Returns:
        RateLimitRule instance.
    """
    return RateLimitRule(
        max_tokens=max_tokens,
        refill_rate=refill_rate,
        scope=scope,
        cost=1,
        enabled=enabled,
    )


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
    # Map policy to rule configuration using _rule() factory
    # Keep these in sync with src/infrastructure/rate_limit/config.py patterns
    mapping: dict[RateLimitPolicy, RateLimitRule] = {
        # Auth endpoints (IP-scoped, restrictive)
        RateLimitPolicy.AUTH_LOGIN: _rule(5, 5.0, RateLimitScope.IP),
        RateLimitPolicy.AUTH_REGISTER: _rule(3, 3.0, RateLimitScope.IP),
        RateLimitPolicy.AUTH_PASSWORD_RESET: _rule(3, 1.0, RateLimitScope.IP),
        RateLimitPolicy.AUTH_TOKEN_REFRESH: _rule(10, 10.0, RateLimitScope.USER),
        # Provider endpoints (moderate, user-scoped)
        RateLimitPolicy.PROVIDER_CONNECT: _rule(5, 5.0, RateLimitScope.USER),
        RateLimitPolicy.PROVIDER_SYNC: _rule(10, 5.0, RateLimitScope.USER_PROVIDER),
        # Standard API endpoints (generous, user-scoped)
        RateLimitPolicy.API_READ: _rule(100, 100.0, RateLimitScope.USER),
        RateLimitPolicy.API_WRITE: _rule(50, 50.0, RateLimitScope.USER),
        # Expensive operations (restrictive, user-scoped)
        RateLimitPolicy.EXPENSIVE_EXPORT: _rule(5, 1.0, RateLimitScope.USER),
        RateLimitPolicy.REPORT: _rule(10, 2.0, RateLimitScope.USER),
        # Global limits (emergency brake, disabled by default)
        RateLimitPolicy.GLOBAL: _rule(
            10000, 10000.0, RateLimitScope.GLOBAL, enabled=False
        ),
    }

    return mapping[policy]
