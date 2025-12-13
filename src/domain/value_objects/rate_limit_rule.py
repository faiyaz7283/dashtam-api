"""Rate limit rule value object.

Immutable configuration for a single rate limit rule. Defines the parameters
for token bucket algorithm: capacity, refill rate, scope, and cost.

Usage:
    from src.domain.value_objects import RateLimitRule
    from src.domain.enums import RateLimitScope

    rule = RateLimitRule(
        max_tokens=5,
        refill_rate=5.0,
        scope=RateLimitScope.IP,
        cost=1,
        enabled=True,
    )
"""

from dataclasses import dataclass

from src.domain.enums.rate_limit_scope import RateLimitScope


@dataclass(frozen=True, slots=True, kw_only=True)
class RateLimitRule:
    """Rate limit rule configuration (value object).

    Immutable configuration for token bucket rate limiting. Each rule defines
    how many tokens (requests) are allowed and how quickly they refill.

    Token Bucket Algorithm:
        - Bucket starts full (max_tokens)
        - Each request consumes `cost` tokens
        - Tokens refill at `refill_rate` per minute
        - If not enough tokens, request is denied with retry_after

    Attributes:
        max_tokens: Maximum tokens in bucket (burst capacity).
            Higher = more burst tolerance. Typical: 5-100.
        refill_rate: Tokens added per minute.
            5.0 = 1 token every 12 seconds. Typical: 5-100.
        scope: How to scope rate limits (IP, USER, USER_PROVIDER, GLOBAL).
            Determines key construction for Redis storage.
        cost: Tokens consumed per request.
            Default 1. Use higher for expensive operations.
        enabled: Whether this rule is active.
            Allows disabling rules without removing them.

    Example:
        # Restrictive: 5 requests per minute, IP-scoped (login)
        login_rule = RateLimitRule(
            max_tokens=5,
            refill_rate=5.0,
            scope=RateLimitScope.IP,
            cost=1,
            enabled=True,
        )

        # Generous: 100 requests per minute, user-scoped (API)
        api_rule = RateLimitRule(
            max_tokens=100,
            refill_rate=100.0,
            scope=RateLimitScope.USER,
            cost=1,
            enabled=True,
        )

        # Expensive operation: costs 5 tokens
        export_rule = RateLimitRule(
            max_tokens=10,
            refill_rate=10.0,
            scope=RateLimitScope.USER,
            cost=5,
            enabled=True,
        )

    Raises:
        ValueError: If max_tokens <= 0 or refill_rate <= 0 or cost <= 0.
    """

    max_tokens: int
    """Maximum tokens in bucket (burst capacity).

    The bucket starts full and refills up to this maximum.
    Higher values allow more burst traffic before rate limiting kicks in.

    Typical values:
        - 3-5 for auth endpoints (restrictive)
        - 50-100 for API endpoints (generous)
        - 10-20 for expensive operations
    """

    refill_rate: float
    """Tokens added per minute.

    Controls how quickly the bucket refills. Formula:
        time_between_tokens = 60 / refill_rate seconds

    Examples:
        - 5.0 = 1 token every 12 seconds
        - 60.0 = 1 token per second
        - 100.0 = ~1.67 tokens per second
    """

    scope: RateLimitScope
    """How to scope rate limits.

    Determines the Redis key format:
        - IP: rate_limit:ip:{address}:{endpoint}
        - USER: rate_limit:user:{user_id}:{endpoint}
        - USER_PROVIDER: rate_limit:user_provider:{user_id}:{provider}:{endpoint}
        - GLOBAL: rate_limit:global:{endpoint}
    """

    cost: int = 1
    """Tokens consumed per request.

    Default is 1. Use higher values for expensive operations
    (report generation, data exports, bulk operations).
    """

    enabled: bool = True
    """Whether this rule is active.

    Allows temporarily disabling rules without removing configuration.
    Disabled rules always allow requests (bypass rate limiting).
    """

    def __post_init__(self) -> None:
        """Validate rule configuration after initialization.

        Raises:
            ValueError: If any numeric field is invalid.
        """
        if self.max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {self.max_tokens}")
        if self.refill_rate <= 0:
            raise ValueError(f"refill_rate must be positive, got {self.refill_rate}")
        if self.cost <= 0:
            raise ValueError(f"cost must be positive, got {self.cost}")

    @property
    def seconds_per_token(self) -> float:
        """Calculate seconds between token refills.

        Returns:
            float: Seconds between each token refill.

        Example:
            rule = RateLimitRule(max_tokens=5, refill_rate=5.0, ...)
            rule.seconds_per_token  # 12.0 (one token every 12 seconds)
        """
        return 60.0 / self.refill_rate

    @property
    def ttl_seconds(self) -> int:
        """Calculate Redis key TTL (time to full refill + buffer).

        Returns:
            int: Recommended TTL for Redis keys in seconds.

        Note:
            Includes 60-second buffer to handle clock skew and ensure
            keys don't expire during active rate limiting.
        """
        return int((self.max_tokens / self.refill_rate) * 60) + 60


@dataclass(frozen=True, slots=True, kw_only=True)
class RateLimitResult:
    """Result of a rate limit check.

    Returned by RateLimiterProtocol.is_allowed() to indicate whether
    a request is allowed and provide metadata for response headers.

    Attributes:
        allowed: Whether the request is allowed.
        retry_after: Seconds until retry allowed (0 if allowed).
        remaining: Tokens remaining in bucket.
        limit: Maximum tokens (bucket capacity).
        reset_seconds: Seconds until bucket fully refills.
    """

    allowed: bool
    """Whether the request is allowed."""

    retry_after: float = 0.0
    """Seconds until retry allowed.

    Only meaningful when allowed=False. Used for Retry-After header.
    """

    remaining: int = 0
    """Tokens remaining in bucket.

    Used for X-RateLimit-Remaining header.
    """

    limit: int = 0
    """Maximum tokens (bucket capacity).

    Used for X-RateLimit-Limit header.
    """

    reset_seconds: int = 0
    """Seconds until bucket fully refills.

    Used for X-RateLimit-Reset header.
    """
