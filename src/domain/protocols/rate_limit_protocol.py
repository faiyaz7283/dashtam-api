"""Rate Limit protocol (port) for token bucket rate limiting.

This protocol defines the contract for rate limiting systems. Infrastructure adapters
implement this protocol to provide concrete rate limiting implementations (Redis-backed
token bucket, in-memory for testing, etc.).

Following hexagonal architecture:
- Domain defines the PORT (this protocol)
- Infrastructure provides ADAPTERS (TokenBucketAdapter, etc.)
- Application layer uses the protocol (doesn't know about specific adapters)

Usage:
    from src.domain.protocols import RateLimitProtocol

    # Dependency injection via container
    rate_limit: RateLimitProtocol = Depends(get_rate_limit)

    # Check if request is allowed
    result = await rate_limit.is_allowed(
        endpoint="POST /api/v1/sessions",
        identifier="192.168.1.1",
    )
    if not result.value.allowed:
        raise HTTPException(429, headers={"Retry-After": str(result.value.retry_after)})
"""

from typing import Protocol

from src.core.result import Result
from src.domain.errors import RateLimitError
from src.domain.value_objects.rate_limit_rule import RateLimitResult


class RateLimitProtocol(Protocol):
    """Protocol for rate limiting systems.

    Defines the interface for token bucket rate limiting. All implementations
    must follow fail-open design - never block requests if rate limit fails.

    Implementations:
        - TokenBucketAdapter: Redis-backed token bucket (production)
        - InMemoryRateLimit: In-memory for unit tests (future)

    Fail-Open Design:
        All methods MUST return Success with allowed=True if any error occurs.
        Rate limit failures should NEVER cause denial-of-service.

    Error Handling:
        Methods return Result types (Success or Failure).
        Failure indicates a real error (not rate limiting) - should be rare.
        On infrastructure errors (Redis down), return Success(allowed=True).
    """

    async def is_allowed(
        self,
        *,
        endpoint: str,
        identifier: str,
        cost: int = 1,
    ) -> Result[RateLimitResult, RateLimitError]:
        """Check if request is allowed and consume tokens if so.

        This is the main rate limiting method. Atomically checks if enough tokens
        are available and consumes them if so.

        Args:
            endpoint: The endpoint being accessed (e.g., "POST /api/v1/sessions").
                Used as part of the rate limit key. Must match rule configuration.
            identifier: The identifier to rate limit (IP address, user ID, etc.).
                Format depends on scope configured for the endpoint.
            cost: Number of tokens to consume. Default 1.
                Use higher values for expensive operations.

        Returns:
            Result[RateLimitResult, RateLimitError]:
                - Success(RateLimitResult) with rate limit decision
                - Failure(RateLimitError) only for severe errors (should be rare)

            RateLimitResult contains:
                - allowed: bool - Whether request is allowed
                - retry_after: float - Seconds until retry allowed (if denied)
                - remaining: int - Tokens remaining in bucket
                - limit: int - Maximum tokens (bucket capacity)
                - reset_seconds: int - Seconds until bucket fully refills

        Fail-Open:
            On infrastructure errors (Redis connection, Lua script, etc.),
            MUST return Success(RateLimitResult(allowed=True, ...)).
            Never block requests due to rate limit failures.

        Example:
            result = await rate_limit.is_allowed(
                endpoint="POST /api/v1/sessions",
                identifier="192.168.1.1",
            )
            match result:
                case Success(value=rate_result):
                    if not rate_result.allowed:
                        # Return HTTP 429 with headers
                        raise HTTPException(
                            status_code=429,
                            headers={"Retry-After": str(rate_result.retry_after)},
                        )
                case Failure(error=e):
                    # Log error but allow request (fail-open)
                    logger.error("Rate limit error", error=str(e))
        """
        ...

    async def get_remaining(
        self,
        *,
        endpoint: str,
        identifier: str,
    ) -> Result[int, RateLimitError]:
        """Get remaining tokens without consuming any.

        Read-only check of current token count. Useful for adding
        X-RateLimit-Remaining header to all responses.

        Args:
            endpoint: The endpoint to check (e.g., "POST /api/v1/sessions").
            identifier: The identifier to check (IP address, user ID, etc.).

        Returns:
            Result[int, RateLimitError]:
                - Success(remaining_tokens) - Number of tokens remaining
                - Failure(RateLimitError) - Only for severe errors

        Fail-Open:
            On infrastructure errors, MUST return Success with max_tokens
            (assume bucket is full if we can't check).

        Example:
            result = await rate_limit.get_remaining(
                endpoint="GET /api/v1/accounts",
                identifier="user-123",
            )
            match result:
                case Success(value=remaining):
                    response.headers["X-RateLimit-Remaining"] = str(remaining)
        """
        ...

    async def reset(
        self,
        *,
        endpoint: str,
        identifier: str,
    ) -> Result[None, RateLimitError]:
        """Reset rate limit bucket to full capacity.

        Administrative operation to reset a rate limit. Useful for:
        - Customer support (unlock rate-limited user)
        - Testing (reset limits between tests)

        Args:
            endpoint: The endpoint to reset (e.g., "POST /api/v1/sessions").
            identifier: The identifier to reset (IP address, user ID, etc.).

        Returns:
            Result[None, RateLimitError]:
                - Success(None) - Bucket reset successfully
                - Failure(RateLimitError) - If reset failed

        Note:
            Unlike is_allowed and get_remaining, this method does NOT fail-open.
            Admin operations should know if they succeeded or failed.

        Example:
            # Customer support: unlock rate-limited user
            result = await rate_limit.reset(
                endpoint="POST /api/v1/sessions",
                identifier="192.168.1.1",
            )
            match result:
                case Success():
                    return {"message": "Rate limit reset"}
                case Failure(error=e):
                    raise HTTPException(500, detail=str(e))
        """
        ...
