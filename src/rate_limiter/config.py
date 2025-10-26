"""Rate limiting configuration module.

This module provides the single source of truth (SSOT) for all rate limiting
configuration in the Dashtam application. It defines strategies, storage backends,
and per-endpoint rate limit rules.

SOLID Principles:
    - S: Single responsibility (configuration only, no logic)
    - O: Open for extension (add new strategies/storage types via enums)
    - L: N/A (no inheritance relationships)
    - I: N/A (no interfaces)
    - D: Depended upon by service/middleware (not vice versa)

Key Design Decisions:
    1. All configuration in code (not environment variables)
       - Type-safe with Pydantic validation
       - Version controlled with code changes
       - Compile-time checking (no runtime config errors)

    2. Per-endpoint flexibility
       - Each endpoint can specify its own strategy (token bucket, sliding window, etc.)
       - Each endpoint can specify its own storage (Redis, PostgreSQL, memory)
       - Supports different limits for different operations

    3. Immutable rules (frozen Pydantic models)
       - Prevents accidental modification at runtime
       - Thread-safe by design

Usage:
    ```python
    from src.rate_limiter.config import RateLimitConfig, RateLimitStrategy

    # Get rule for specific endpoint
    rule = RateLimitConfig.get_rule("POST /api/v1/auth/login")

    # Check if endpoint has rate limiting
    if rule.enabled:
        # Apply rate limiting
        ...
    ```
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class RateLimitStrategy(str, Enum):
    """Rate limiting algorithm strategies.

    Attributes:
        TOKEN_BUCKET: Allows bursts, smooth traffic. Best for financial APIs.
        SLIDING_WINDOW: Prevents timing attacks, consistent enforcement.
        FIXED_WINDOW: Simple, edge-case burst vulnerability.
    """

    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


class RateLimitStorage(str, Enum):
    """Storage backend for rate limit state.

    Attributes:
        REDIS: High-performance in-memory storage (production default).
        POSTGRES: Persistent storage, good for audit requirements.
        MEMORY: Local in-process storage (testing/development only).
    """

    REDIS = "redis"
    POSTGRES = "postgres"
    MEMORY = "memory"


class RateLimitRule(BaseModel):
    """Configuration for a single rate limit rule.

    This defines how rate limiting is applied to a specific endpoint or operation.

    Attributes:
        strategy: Algorithm to use (token bucket, sliding window, etc.).
        storage: Storage backend for rate limit state.
        max_tokens: Maximum capacity (tokens in bucket, requests in window).
        refill_rate: Rate of token/request replenishment (per minute).
        scope: Identifier type for rate limit key (ip, user, user_provider, global).
        enabled: Whether this rule is active.
        cost: Number of tokens consumed per request (default: 1).

    Examples:
        Login endpoint (IP-based, 20 requests/min):
        ```python
        RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=20,
            refill_rate=5.0,  # 5 tokens/min = 12 seconds per token
            scope="ip",
            enabled=True
        )
        ```

        Provider API call (user-per-provider, 100 requests/min):
        ```python
        RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=100,
            refill_rate=100.0,  # Match Schwab's actual API limits
            scope="user_provider",
            enabled=True
        )
        ```
    """

    model_config = ConfigDict(frozen=True)  # Immutable for thread safety

    strategy: RateLimitStrategy = Field(
        ..., description="Rate limiting algorithm to use"
    )
    storage: RateLimitStorage = Field(..., description="Storage backend for state")
    max_tokens: int = Field(..., gt=0, description="Maximum tokens/requests allowed")
    refill_rate: float = Field(
        ..., gt=0, description="Token/request refill rate per minute"
    )
    scope: str = Field(
        ...,
        description="Identifier type: 'ip', 'user', 'user_provider', 'global'",
    )
    enabled: bool = Field(True, description="Whether rate limiting is active")
    cost: int = Field(1, gt=0, description="Number of tokens consumed per request")


class RateLimitConfig:
    """Central configuration for all rate limiting rules.

    This class provides a registry of rate limit rules for all API endpoints.
    Each endpoint can have its own strategy, storage backend, and limits.

    SOLID Principles:
        - S: Single responsibility (configuration storage only)
        - O: Open for extension (add new rules to RULES dict)
        - D: Other components depend on this (not vice versa)

    Design Notes:
        - Class methods (not instance methods) since this is a configuration registry
        - No state mutation after initial definition
        - Type-safe lookups with Optional return type

    Usage:
        ```python
        # Get rule for specific endpoint
        rule = RateLimitConfig.get_rule("POST /api/v1/auth/login")
        if rule and rule.enabled:
            # Apply rate limiting
            ...

        # Check if endpoint has rate limiting
        if RateLimitConfig.has_rule("GET /api/v1/providers"):
            # Endpoint is rate limited
            ...
        ```
    """

    # =========================================================================
    # Rate Limit Rules Registry
    # =========================================================================

    RULES: dict[str, RateLimitRule] = {
        # =====================================================================
        # Authentication Endpoints (IP-based rate limiting)
        # =====================================================================
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
        "POST /api/v1/auth/password-resets": RateLimitRule(
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
        # =====================================================================
        # Provider Management Endpoints (User-based rate limiting)
        # =====================================================================
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
        # =====================================================================
        # Provider OAuth Flow Endpoints (IP-based during OAuth, user after)
        # =====================================================================
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
        # =====================================================================
        # Provider API Calls (User-per-provider rate limiting)
        # =====================================================================
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

    @classmethod
    def get_rule(cls, endpoint: str) -> Optional[RateLimitRule]:
        """Get rate limit rule for a specific endpoint.

        Args:
            endpoint: Endpoint identifier (e.g., "POST /api/v1/auth/login" or "schwab_api").

        Returns:
            RateLimitRule if configured, None otherwise.

        Examples:
            ```python
            rule = RateLimitConfig.get_rule("POST /api/v1/auth/login")
            if rule and rule.enabled:
                # Apply rate limiting
                is_allowed, retry_after = rate_limiter.check(endpoint, ip_address)
            ```
        """
        return cls.RULES.get(endpoint)

    @classmethod
    def has_rule(cls, endpoint: str) -> bool:
        """Check if endpoint has a rate limit rule configured.

        Args:
            endpoint: Endpoint identifier.

        Returns:
            True if rule exists and is enabled, False otherwise.

        Examples:
            ```python
            if RateLimitConfig.has_rule("POST /api/v1/auth/login"):
                # This endpoint is rate limited
                ...
            ```
        """
        rule = cls.get_rule(endpoint)
        return rule is not None and rule.enabled

    @classmethod
    def get_all_rules(cls) -> dict[str, RateLimitRule]:
        """Get all configured rate limit rules.

        Returns:
            Dictionary mapping endpoint identifiers to their rules.

        Note:
            This includes both enabled and disabled rules.
            Use `has_rule()` to check if a rule is enabled.
        """
        return cls.RULES.copy()

    @classmethod
    def get_enabled_rules(cls) -> dict[str, RateLimitRule]:
        """Get only enabled rate limit rules.

        Returns:
            Dictionary mapping endpoint identifiers to enabled rules only.

        Examples:
            ```python
            # List all rate-limited endpoints
            for endpoint, rule in RateLimitConfig.get_enabled_rules().items():
                print(f"{endpoint}: {rule.max_tokens} tokens @ {rule.refill_rate}/min")
            ```
        """
        return {endpoint: rule for endpoint, rule in cls.RULES.items() if rule.enabled}
