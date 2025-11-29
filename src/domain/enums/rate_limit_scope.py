"""Rate Limit enumeration types.

Defines scoping strategies for rate limit rules. Each scope determines how
rate limit keys are constructed and how limits are applied.

Architectural Decision:
    Following centralized enum pattern (see docs/architecture/directory-structure.md).
    All domain enums live in src/domain/enums/ for discoverability.

Usage:
    from src.domain.enums import RateLimitScope

    rule = RateLimitRule(
        max_tokens=5,
        refill_rate=5.0,
        scope=RateLimitScope.IP,
        cost=1,
        enabled=True,
    )
"""

from enum import Enum


class RateLimitScope(str, Enum):
    """Scope types for rate limit rules.

    Determines how rate limit keys are constructed and how limits are
    applied to different types of identifiers.

    String Enum:
        Inherits from str for easy serialization and database storage.
        Values are snake_case strings for consistency.

    Key Formats:
        IP: rate_limit:ip:{address}:{endpoint}
        USER: rate_limit:user:{user_id}:{endpoint}
        USER_PROVIDER: rate_limit:user_provider:{user_id}:{provider}:{endpoint}
        GLOBAL: rate_limit:global:{endpoint}

    Usage Examples:
        - IP scope for unauthenticated endpoints (login, register)
        - USER scope for authenticated API endpoints
        - USER_PROVIDER scope for provider-specific operations (sync, refresh)
        - GLOBAL scope for system-wide limits (rare)
    """

    IP = "ip"
    """Rate limit by client IP address.

    Use for unauthenticated endpoints where user identity is unknown.
    Key format: rate_limit:ip:{ip_address}:{endpoint}

    Examples:
        - POST /api/v1/sessions (login)
        - POST /api/v1/users (registration)
        - POST /api/v1/password-reset-tokens

    Security:
        Protects against brute force attacks from single IP.
        Should handle X-Forwarded-For properly in production.
    """

    USER = "user"
    """Rate limit by authenticated user ID.

    Use for authenticated API endpoints where user identity is known.
    Key format: rate_limit:user:{user_id}:{endpoint}

    Examples:
        - GET /api/v1/accounts
        - GET /api/v1/transactions
        - PATCH /api/v1/users/me

    Note:
        More generous limits than IP scope (trusted users).
        Prevents single user from monopolizing resources.
    """

    USER_PROVIDER = "user_provider"
    """Rate limit by user + provider combination.

    Use for provider-specific operations where each provider has its own limits.
    Key format: rate_limit:user_provider:{user_id}:{provider_name}:{endpoint}

    Examples:
        - POST /api/v1/providers/{provider_id}/syncs
        - POST /api/v1/providers/{provider_id}/token-refreshes

    Note:
        Prevents excessive calls to third-party provider APIs.
        Respects provider-specific rate limits (e.g., Schwab: 120/min).
    """

    GLOBAL = "global"
    """Rate limit globally across all users.

    Use sparingly for system-wide limits that apply to all requests.
    Key format: rate_limit:global:{endpoint}

    Examples:
        - System health check endpoints
        - Public status endpoints

    Warning:
        Use rarely - shared limit means one user can exhaust limit for all.
        Consider USER scope with generous limits instead.
    """
