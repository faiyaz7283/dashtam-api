"""Rate limit rules configuration (Single Source of Truth).

This module defines rate limit rules for all endpoints. Rules are centralized
here to ensure consistency and easy maintenance.

Rule Design Principles:
- Auth endpoints: Restrictive (5/min IP-scoped) - Prevent credential stuffing
- API endpoints: Generous (100/min user-scoped) - Normal API usage
- Expensive operations: Moderate (10/min user-scoped) - Prevent abuse
- Global limits: Very restrictive - Emergency brake

Usage:
    from src.infrastructure.rate_limit.config import RATE_LIMIT_RULES

    # Lookup rule for endpoint
    rule = RATE_LIMIT_RULES.get("POST /api/v1/sessions")
"""

from src.domain.enums import RateLimitScope
from src.domain.value_objects.rate_limit_rule import RateLimitRule


# =============================================================================
# Authentication Endpoints (Restrictive - IP-scoped)
# =============================================================================
# These endpoints are high-value targets for credential stuffing attacks.
# IP-scoped limits prevent brute force from single sources.

AUTH_LOGIN_RULE = RateLimitRule(
    max_tokens=5,
    refill_rate=5.0,  # 1 token every 12 seconds
    scope=RateLimitScope.IP,
    cost=1,
    enabled=True,
)
"""Login endpoint: 5 attempts per minute per IP.

Rationale:
- Legitimate users rarely need >5 login attempts per minute
- Prevents credential stuffing (one IP, many accounts)
- 12-second refill allows retry after typos
"""

AUTH_REGISTER_RULE = RateLimitRule(
    max_tokens=3,
    refill_rate=3.0,  # 1 token every 20 seconds
    scope=RateLimitScope.IP,
    cost=1,
    enabled=True,
)
"""Registration endpoint: 3 attempts per minute per IP.

Rationale:
- Legitimate users register once
- More restrictive than login (fewer legitimate retries)
- Prevents mass account creation attacks
"""

AUTH_PASSWORD_RESET_RULE = RateLimitRule(
    max_tokens=3,
    refill_rate=1.0,  # 1 token per minute
    scope=RateLimitScope.IP,
    cost=1,
    enabled=True,
)
"""Password reset endpoint: 3 attempts, 1 refill per minute per IP.

Rationale:
- Highly sensitive operation
- Abuse can lead to email flooding
- Low legitimate need (user forgets password once)
"""

AUTH_TOKEN_REFRESH_RULE = RateLimitRule(
    max_tokens=10,
    refill_rate=10.0,  # 1 token every 6 seconds
    scope=RateLimitScope.USER,
    cost=1,
    enabled=True,
)
"""Token refresh: 10 per minute per user.

Rationale:
- Legitimate apps refresh tokens periodically
- User-scoped (requires valid token)
- More generous than login (automated, not manual)
"""


# =============================================================================
# Provider Endpoints (Moderate - User-scoped)
# =============================================================================
# Provider operations are resource-intensive (external API calls, OAuth flows).

PROVIDER_CONNECT_RULE = RateLimitRule(
    max_tokens=5,
    refill_rate=5.0,
    scope=RateLimitScope.USER,
    cost=1,
    enabled=True,
)
"""Provider connect: 5 per minute per user.

Rationale:
- OAuth flow is resource-intensive
- User shouldn't need many connect attempts
- Prevents abuse of OAuth flow
"""

PROVIDER_SYNC_RULE = RateLimitRule(
    max_tokens=10,
    refill_rate=5.0,
    scope=RateLimitScope.USER_PROVIDER,
    cost=1,
    enabled=True,
)
"""Provider sync: 10 per minute per user-provider.

Rationale:
- Sync triggers external API calls
- Per user-provider to allow multiple providers
- Burst of 10 allows initial data load
"""


# =============================================================================
# API Endpoints (Generous - User-scoped)
# =============================================================================
# Standard API endpoints with reasonable limits for legitimate usage.

API_READ_RULE = RateLimitRule(
    max_tokens=100,
    refill_rate=100.0,  # ~1.67 tokens per second
    scope=RateLimitScope.USER,
    cost=1,
    enabled=True,
)
"""API read operations: 100 per minute per user.

Rationale:
- Read operations are cheap
- Allows responsive UIs with many requests
- Prevents runaway scripts
"""

API_WRITE_RULE = RateLimitRule(
    max_tokens=50,
    refill_rate=50.0,
    scope=RateLimitScope.USER,
    cost=1,
    enabled=True,
)
"""API write operations: 50 per minute per user.

Rationale:
- Write operations are more expensive
- Still generous for legitimate use
- Prevents bulk data manipulation
"""


# =============================================================================
# Expensive Operations (Restrictive - User-scoped)
# =============================================================================
# Operations that consume significant resources (CPU, memory, external APIs).

EXPORT_RULE = RateLimitRule(
    max_tokens=5,
    refill_rate=1.0,  # 1 token per minute
    scope=RateLimitScope.USER,
    cost=1,
    enabled=True,
)
"""Data export: 5 burst, 1 per minute per user.

Rationale:
- Exports are expensive (large data queries)
- Allow small burst for retry, but slow refill
- Prevents abuse of expensive operations
"""

REPORT_RULE = RateLimitRule(
    max_tokens=10,
    refill_rate=2.0,  # 1 token every 30 seconds
    scope=RateLimitScope.USER,
    cost=1,
    enabled=True,
)
"""Report generation: 10 burst, 2 per minute per user.

Rationale:
- Reports require computation
- Moderate limits for legitimate analytics use
- Prevents denial of service via report generation
"""


# =============================================================================
# Global Limits (Emergency Brake - Global scope)
# =============================================================================
# These limits apply to ALL users. Use for emergency protection.

GLOBAL_API_RULE = RateLimitRule(
    max_tokens=10000,
    refill_rate=10000.0,
    scope=RateLimitScope.GLOBAL,
    cost=1,
    enabled=False,  # Disabled by default - enable in emergencies
)
"""Global API limit: 10k per minute (emergency brake).

Rationale:
- Emergency protection against DDoS
- Disabled by default (enable if under attack)
- Global scope means ALL users share this limit
"""


# =============================================================================
# RATE_LIMIT_RULES - Single Source of Truth
# =============================================================================
# Mapping of endpoint patterns to rules.
# Endpoint format: "{METHOD} {PATH}" (e.g., "POST /api/v1/sessions")

RATE_LIMIT_RULES: dict[str, RateLimitRule] = {
    # Authentication endpoints
    "POST /api/v1/sessions": AUTH_LOGIN_RULE,
    "DELETE /api/v1/sessions": AUTH_TOKEN_REFRESH_RULE,  # Logout
    "POST /api/v1/users": AUTH_REGISTER_RULE,
    "POST /api/v1/auth/password-reset": AUTH_PASSWORD_RESET_RULE,
    "POST /api/v1/auth/password-reset/confirm": AUTH_PASSWORD_RESET_RULE,
    "POST /api/v1/auth/refresh": AUTH_TOKEN_REFRESH_RULE,
    # Provider endpoints
    "POST /api/v1/providers": PROVIDER_CONNECT_RULE,
    "DELETE /api/v1/providers/{provider_id}": PROVIDER_CONNECT_RULE,
    "POST /api/v1/providers/{provider_id}/sync": PROVIDER_SYNC_RULE,
    # Account endpoints (read-heavy)
    "GET /api/v1/accounts": API_READ_RULE,
    "GET /api/v1/accounts/{account_id}": API_READ_RULE,
    "GET /api/v1/accounts/{account_id}/transactions": API_READ_RULE,
    "GET /api/v1/accounts/{account_id}/balance": API_READ_RULE,
    # Transaction endpoints
    "GET /api/v1/transactions": API_READ_RULE,
    "GET /api/v1/transactions/{transaction_id}": API_READ_RULE,
    # Export endpoints (expensive)
    "POST /api/v1/exports/transactions": EXPORT_RULE,
    "POST /api/v1/exports/accounts": EXPORT_RULE,
    # Report endpoints
    "POST /api/v1/reports/spending": REPORT_RULE,
    "POST /api/v1/reports/income": REPORT_RULE,
    # User profile endpoints
    "GET /api/v1/users/me": API_READ_RULE,
    "PATCH /api/v1/users/me": API_WRITE_RULE,
    "PUT /api/v1/users/me/password": AUTH_PASSWORD_RESET_RULE,  # Sensitive
}
"""Endpoint to rate limit rule mapping.

Add new endpoints here as they're created. The endpoint format must match
exactly what the middleware/dependency receives (typically from FastAPI's
request.scope["path"] and request.method).

Note:
    Path parameters like {account_id} are kept in the key for documentation.
    The actual matching may use prefix matching or regex depending on
    middleware implementation.
"""


def get_rule_for_endpoint(endpoint: str) -> RateLimitRule | None:
    """Get rate limit rule for endpoint.

    Supports exact match and path parameter patterns.

    Args:
        endpoint: Endpoint string (e.g., "GET /api/v1/accounts/123").

    Returns:
        RateLimitRule if found, None otherwise.
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
