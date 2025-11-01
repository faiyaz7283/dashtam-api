"""Dashtam-specific rate limit configuration.

This module defines rate limit rules for all Dashtam API endpoints.
It uses the generic rate limiter component from src/rate_limiter.

Architecture:
    - src/rate_limiter/: Generic, reusable rate limiter component
    - src/config/rate_limits.py: Application-specific endpoint rules (THIS FILE)

The separation allows the rate_limiter package to be extracted as a
standalone library without any Dashtam-specific dependencies.

Usage:
    ```python
    from src.config.rate_limits import RATE_LIMIT_RULES

    # Get rule for specific endpoint
    rule = RATE_LIMIT_RULES.get("POST /api/v1/auth/login")
    if rule and rule.enabled:
        # Apply rate limiting
        ...
    ```
"""

from src.rate_limiter.config import (
    RateLimitRule,
    RateLimitStrategy,
    RateLimitStorage,
)

# =============================================================================
# Dashtam API Endpoint Rate Limit Rules
# =============================================================================
#
# This dictionary defines rate limits for all Dashtam API endpoints.
# Each key is an endpoint identifier (HTTP method + path or provider name).
# Each value is a RateLimitRule specifying strategy, limits, and scope.
#
# Design Principles:
#   1. Security-sensitive endpoints have stricter limits (login, password reset)
#   2. IP-based scoping for unauthenticated endpoints (prevent account cycling)
#   3. User-based scoping for authenticated endpoints (per-user fairness)
#   4. Provider API limits match external API quotas (prevent violations)
#
# =============================================================================

RATE_LIMIT_RULES: dict[str, RateLimitRule] = {
    # =========================================================================
    # Authentication Endpoints (IP-based Rate Limiting)
    # =========================================================================
    # These endpoints are vulnerable to brute force attacks and must be
    # aggressively rate limited. IP-based scoping prevents attackers from
    # cycling through multiple accounts.
    "POST /api/v1/auth/login": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=20,  # Allow 20 immediate attempts (account for typos)
        refill_rate=5.0,  # 5 tokens/min = 12 seconds per token
        scope="ip",
        enabled=True,
    ),
    "POST /api/v1/auth/register": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=10,  # Prevent mass account creation
        refill_rate=2.0,  # 2 tokens/min = 30 seconds per token
        scope="ip",
        enabled=True,
    ),
    "POST /api/v1/password-resets/": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=5,  # Very restrictive (sensitive operation)
        refill_rate=0.2,  # 1 token every 5 minutes
        scope="ip",
        enabled=True,
    ),
    "POST /api/v1/auth/verification/resend": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=3,  # Prevent email spam
        refill_rate=0.1,  # 1 token every 10 minutes
        scope="ip",
        enabled=True,
    ),
    # =========================================================================
    # Token Management Endpoints (RESTful - SECURITY CRITICAL)
    # =========================================================================
    # Token revocation is security-sensitive. Aggressive rate limiting prevents
    # DoS attacks via revocation spam and brute force enumeration.
    #
    # RESTful design: DELETE /users/{id}/tokens (revoke all user tokens)
    #                 DELETE /tokens (revoke all tokens - nuclear option)
    #                 GET /security/config (view security configuration)
    "DELETE /api/v1/users/{user_id}/tokens": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=5,  # Allow 5 immediate revocations
        refill_rate=0.33,  # 1 token every 3 minutes (5 per 15 minutes)
        scope="user",
        enabled=True,
    ),
    "DELETE /api/v1/tokens": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=1,  # Single token (one revocation per window)
        refill_rate=0.0007,  # 1 token per day (1/1440 minutes)
        scope="global",
        enabled=True,
    ),
    "GET /api/v1/security/config": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=10,  # Read-only, less restrictive
        refill_rate=1.0,  # 10 per 10 minutes
        scope="user",
        enabled=True,
    ),
    # =========================================================================
    # Provider Management Endpoints (User-based Rate Limiting)
    # =========================================================================
    # Authenticated users managing their own provider connections.
    # More generous limits since authenticated users are less likely to abuse.
    "POST /api/v1/providers": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=100,  # Burst capacity for normal usage
        refill_rate=100.0,  # 100 tokens/min = 1 per second
        scope="user",
        enabled=True,
    ),
    "GET /api/v1/providers": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=100,
        refill_rate=100.0,
        scope="user",
        enabled=True,
    ),
    "GET /api/v1/providers/{provider_id}": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=100,
        refill_rate=100.0,
        scope="user",
        enabled=True,
    ),
    "PATCH /api/v1/providers/{provider_id}": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=50,  # Lower limit for write operations
        refill_rate=50.0,
        scope="user",
        enabled=True,
    ),
    "DELETE /api/v1/providers/{provider_id}": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=20,  # Very restrictive (destructive operation)
        refill_rate=20.0,
        scope="user",
        enabled=True,
    ),
    # =========================================================================
    # Provider OAuth Flow Endpoints (IP-based during OAuth, user after)
    # =========================================================================
    "POST /api/v1/providers/{provider_id}/authorization": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=50,
        refill_rate=50.0,
        scope="user",  # User-based (authenticated)
        enabled=True,
    ),
    "GET /api/v1/providers/{provider_id}/authorization/callback": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=20,
        refill_rate=10.0,
        scope="ip",  # IP-based (callback before full auth)
        enabled=True,
    ),
    # =========================================================================
    # Provider API Calls (User-per-provider Rate Limiting)
    # =========================================================================
    # These limits MUST match the actual provider's API limits to prevent
    # quota violations. Scope is "user_provider" to track per user per provider.
    #
    # Charles Schwab: 100 requests/min per user per app
    # https://developer.schwab.com/products/trader-api--individual/details/specifications/Retail%20Trader%20API%20Production
    "schwab_api": RateLimitRule(
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        storage=RateLimitStorage.REDIS,
        max_tokens=100,  # Match Schwab's limit exactly
        refill_rate=100.0,  # 100 tokens/min = 1 per second
        scope="user_provider",
        enabled=True,
    ),
    # Future providers (examples, not yet implemented):
    # "plaid_api": RateLimitRule(
    #     strategy=RateLimitStrategy.TOKEN_BUCKET,
    #     storage=RateLimitStorage.REDIS,
    #     max_tokens=500,  # Plaid: 500 requests/min
    #     refill_rate=500.0,
    #     scope="user_provider",
    #     enabled=True,
    # ),
    # "chase_api": RateLimitRule(
    #     strategy=RateLimitStrategy.TOKEN_BUCKET,
    #     storage=RateLimitStorage.REDIS,
    #     max_tokens=60,  # Chase: 60 requests/min
    #     refill_rate=60.0,
    #     scope="user_provider",
    #     enabled=True,
    # ),
}


def get_rate_limit_rule(endpoint: str) -> RateLimitRule | None:
    """Get rate limit rule for a specific endpoint.

    Args:
        endpoint: Endpoint identifier (e.g., "POST /api/v1/auth/login" or "schwab_api").

    Returns:
        RateLimitRule if configured, None otherwise.

    Examples:
        ```python
        rule = get_rate_limit_rule("POST /api/v1/auth/login")
        if rule and rule.enabled:
            # Apply rate limiting
            is_allowed, retry_after = rate_limiter.check(endpoint, ip_address)
        ```
    """
    return RATE_LIMIT_RULES.get(endpoint)


def has_rate_limit(endpoint: str) -> bool:
    """Check if endpoint has a rate limit rule configured.

    Args:
        endpoint: Endpoint identifier.

    Returns:
        True if rule exists and is enabled, False otherwise.

    Examples:
        ```python
        if has_rate_limit("POST /api/v1/auth/login"):
            # This endpoint is rate limited
            ...
        ```
    """
    rule = get_rate_limit_rule(endpoint)
    return rule is not None and rule.enabled


def get_all_rate_limit_rules() -> dict[str, RateLimitRule]:
    """Get all configured rate limit rules.

    Returns:
        Dictionary mapping endpoint identifiers to their rules.

    Note:
        This includes both enabled and disabled rules.
        Use `has_rate_limit()` to check if a rule is enabled.
    """
    return RATE_LIMIT_RULES.copy()


def get_enabled_rate_limit_rules() -> dict[str, RateLimitRule]:
    """Get only enabled rate limit rules.

    Returns:
        Dictionary mapping endpoint identifiers to enabled rules only.

    Examples:
        ```python
        # List all rate-limited endpoints
        for endpoint, rule in get_enabled_rate_limit_rules().items():
            print(f"{endpoint}: {rule.max_tokens} tokens @ {rule.refill_rate}/min")
        ```
    """
    return {
        endpoint: rule for endpoint, rule in RATE_LIMIT_RULES.items() if rule.enabled
    }
