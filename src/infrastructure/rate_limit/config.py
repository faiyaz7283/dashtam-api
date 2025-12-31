"""Rate limit rules configuration (Generated from Registry).

IMPORTANT: This module is now a thin proxy to registry-generated rules.
Rate limit rules are automatically generated from the Route Metadata Registry.

Two-Tier Configuration Pattern:
    Rate limits use a two-tier configuration similar to CSS classes:

    Tier 1 - Policy Assignment (registry.py):
        Assigns a rate limit policy to each endpoint.
        Example: "Login endpoint should use AUTH_LOGIN policy"

        To change: Update rate_limit_policy in RouteMetadata
        Effect: Changes policy for ONE specific endpoint

    Tier 2 - Policy Implementation (derivations.py):
        Defines the actual limits for each policy category.
        Example: "AUTH_LOGIN policy = 5 attempts per minute"

        To change: Update RateLimitRule in _create_rate_limit_rule()
        Effect: Changes limits for ALL endpoints using that policy

Examples:
    # Make login endpoint more generous (Tier 1 - one endpoint)
    RouteMetadata(
        path="/sessions",
        rate_limit_policy=RateLimitPolicy.API_READ,  # Change policy
    )

    # Increase AUTH_LOGIN limits globally (Tier 2 - all AUTH_LOGIN endpoints)
    RateLimitPolicy.AUTH_LOGIN: RateLimitRule(
        max_tokens=10,  # Change from 5 to 10
    )

DO NOT add hand-written rules here - they will be ignored.

Usage:
    from src.infrastructure.rate_limit.config import RATE_LIMIT_RULES

    # Lookup rule for endpoint
    rule = RATE_LIMIT_RULES.get("POST /api/v1/sessions")

Reference:
    - src/infrastructure/rate_limit/from_registry.py (actual implementation)
    - src/presentation/routers/api/v1/routes/registry.py (Tier 1: policy assignment)
    - src/presentation/routers/api/v1/routes/derivations.py (Tier 2: policy implementation)
"""

# =============================================================================
# DEPRECATED: Hand-written rules (replaced by registry-generated rules)
# =============================================================================
# All rate limit rules are now automatically generated from the Route Metadata
# Registry. The hand-written rules below have been removed.
#
# To modify rate limits:
#     1. Update RateLimitPolicy in ROUTE_REGISTRY
#     2. Or update policy mapping in derivations.py
#
# DO NOT add rules here - use the registry instead.

# Import registry-generated rules
from src.infrastructure.rate_limit.from_registry import (
    RATE_LIMIT_RULES,
    get_rule_for_endpoint,
)

# Re-export for backward compatibility
__all__ = ["RATE_LIMIT_RULES", "get_rule_for_endpoint"]
