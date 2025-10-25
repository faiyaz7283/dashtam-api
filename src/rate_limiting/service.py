"""Rate limiter service orchestrator.

This module provides the main RateLimiterService class that orchestrates
rate limiting by combining configuration, algorithms, and storage backends.
It follows the Facade pattern, providing a simple interface to the complex
rate limiting subsystem.

SOLID Principles:
    - S: Single responsibility (orchestration only, no algorithm/storage logic)
    - O: Open for extension (can add new algorithms/storage via injection)
    - L: N/A (no inheritance)
    - I: Minimal interface (only is_allowed method)
    - D: Depends on abstractions (RateLimitAlgorithm, RateLimitStorage)

Key Design Decisions:
    1. Dependency Injection
       - Algorithm and storage injected via constructor
       - Enables testing with mocks
       - Allows swapping implementations without code changes

    2. No HTTP/FastAPI dependencies
       - Takes generic parameters (endpoint, identifier)
       - Returns simple tuple (allowed, retry_after)
       - Middleware layer handles HTTP-specific logic

    3. Fail-open strategy
       - If algorithm/storage fails, allow request
       - Log errors for monitoring
       - Rate limiting not single point of failure

Usage:
    ```python
    from src.rate_limiting.service import RateLimiterService
    from src.rate_limiting.algorithms import TokenBucketAlgorithm
    from src.rate_limiting.storage import RedisRateLimitStorage

    algorithm = TokenBucketAlgorithm()
    storage = RedisRateLimitStorage(redis_client)
    rate_limiter = RateLimiterService(algorithm, storage)

    allowed, retry_after = await rate_limiter.is_allowed(
        endpoint="POST /api/v1/auth/login",
        identifier="192.168.1.1",
        cost=1
    )
    ```
"""

import logging
from typing import Optional

from src.rate_limiting.algorithms.base import RateLimitAlgorithm
from src.rate_limiting.config import RateLimitConfig, RateLimitRule
from src.rate_limiting.storage.base import RateLimitStorage

logger = logging.getLogger(__name__)


class RateLimiterService:
    """Rate limiter service orchestrator.

    This service combines configuration, algorithms, and storage backends
    to provide a simple interface for rate limiting. It follows the Facade
    pattern, hiding the complexity of the rate limiting subsystem.

    SOLID: Dependency Inversion Principle
        This class depends on abstractions (RateLimitAlgorithm, RateLimitStorage)
        not concrete implementations. This enables:
        - Testing with mocks
        - Swapping implementations without code changes
        - Adding new algorithms/storage backends via extension

    Fail-Open Strategy:
        If any component fails (algorithm, storage, config), this service
        allows the request to proceed. This ensures rate limiting doesn't
        become a single point of failure.

    Thread Safety:
        - This class is thread-safe (no shared mutable state)
        - Algorithm and storage backends must also be thread-safe
        - Safe for concurrent use across multiple requests

    Examples:
        Basic usage:
        ```python
        rate_limiter = RateLimiterService(
            algorithm=TokenBucketAlgorithm(),
            storage=RedisRateLimitStorage(redis_client)
        )

        allowed, retry_after = await rate_limiter.is_allowed(
            endpoint="POST /api/v1/auth/login",
            identifier="192.168.1.1"
        )
        if not allowed:
            raise HTTPException(
                status_code=429,
                headers={"Retry-After": str(int(retry_after))},
                detail="Rate limit exceeded"
            )
        ```

        With custom cost:
        ```python
        allowed, retry_after = await rate_limiter.is_allowed(
            endpoint="schwab_api",
            identifier="user:123:schwab",
            cost=5  # Expensive operation
        )
        ```
    """

    def __init__(
        self,
        algorithm: RateLimitAlgorithm,
        storage: RateLimitStorage,
    ):
        """Initialize rate limiter service.

        Args:
            algorithm: Rate limiting algorithm implementation (e.g., TokenBucketAlgorithm).
            storage: Storage backend for rate limit state (e.g., RedisRateLimitStorage).

        Note:
            These dependencies are injected to enable:
            - Testing with mocks
            - Swapping implementations at runtime
            - Following Dependency Inversion Principle
        """
        self.algorithm = algorithm
        self.storage = storage

    async def is_allowed(
        self,
        endpoint: str,
        identifier: str,
        cost: int = 1,
    ) -> tuple[bool, float, Optional[RateLimitRule]]:
        """Check if request is allowed under rate limiting rules.

        This is the main entry point for rate limiting. It:
        1. Looks up rate limit rule for endpoint
        2. Builds unique key from endpoint and identifier
        3. Delegates to algorithm for rate limit check
        4. Returns result with rule metadata

        Args:
            endpoint: Endpoint identifier (e.g., "POST /api/v1/auth/login" or "schwab_api").
            identifier: Unique identifier for rate limit bucket. Depends on rule scope:
                - scope="ip": IP address (e.g., "192.168.1.1")
                - scope="user": User ID (e.g., "user:123")
                - scope="user_provider": User ID + provider (e.g., "user:123:schwab")
                - scope="global": Endpoint only (e.g., "global")
            cost: Number of tokens to consume (default: 1). Some operations
                may cost more than 1 token.

        Returns:
            Tuple of (is_allowed, retry_after_seconds, rule):
                - is_allowed: True if request allowed, False if rate limited.
                - retry_after_seconds: If rate limited, seconds until next token.
                  If allowed, this is 0.0.
                - rule: Rate limit rule that was applied (None if no rule configured).

        Raises:
            No exceptions are raised. All errors are caught and logged,
            with fail-open behavior (return True, 0.0, None).

        Examples:
            IP-based rate limiting (login endpoint):
            ```python
            allowed, retry_after, rule = await rate_limiter.is_allowed(
                endpoint="POST /api/v1/auth/login",
                identifier="192.168.1.1"
            )
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    headers={"Retry-After": str(int(retry_after))},
                    detail=f\"Rate limit exceeded. Try again in {int(retry_after)} seconds.\"
                )
            ```

            User-based rate limiting (provider endpoints):
            ```python
            allowed, retry_after, rule = await rate_limiter.is_allowed(
                endpoint="GET /api/v1/providers",
                identifier=f\"user:{user_id}\"
            )
            ```

            User-per-provider rate limiting (API calls):
            ```python
            allowed, retry_after, rule = await rate_limiter.is_allowed(
                endpoint=\"schwab_api\",
                identifier=f\"user:{user_id}:schwab\",
                cost=5  # Expensive operation
            )
            ```
        """
        try:
            # Step 1: Look up rate limit rule
            rule = RateLimitConfig.get_rule(endpoint)
            if rule is None or not rule.enabled:
                # No rate limiting configured for this endpoint
                logger.debug(f"No rate limit rule for endpoint={endpoint}")
                return True, 0.0, None

            # Step 2: Build unique key
            key = self._build_key(endpoint, identifier, rule.scope)

            # Step 3: Check rate limit via algorithm
            allowed, retry_after = await self.algorithm.is_allowed(
                storage=self.storage,
                key=key,
                rule=rule,
                cost=cost,
            )

            if allowed:
                logger.info(
                    f"Rate limit check passed: endpoint={endpoint}, "
                    f"identifier={identifier}, cost={cost}"
                )
            else:
                logger.warning(
                    f"Rate limit exceeded: endpoint={endpoint}, "
                    f"identifier={identifier}, retry_after={retry_after:.2f}s"
                )

            return allowed, retry_after, rule

        except Exception as e:
            # Fail-open: Allow request if any error occurs
            logger.error(
                f"Rate limiter service failed for endpoint={endpoint}, "
                f"identifier={identifier}: {e}. Failing open (allowing request)."
            )
            return True, 0.0, None

    def _build_key(self, endpoint: str, identifier: str, scope: str) -> str:
        """Build unique Redis key for rate limit bucket.

        The key format depends on the scope:
        - scope="ip": "ip:{identifier}:{endpoint}"
        - scope="user": "user:{identifier}:{endpoint}"
        - scope="user_provider": "user_provider:{identifier}:{endpoint}"
        - scope="global": "global:{endpoint}"

        Args:
            endpoint: Endpoint identifier.
            identifier: Unique identifier for rate limit bucket.
            scope: Scope type (ip, user, user_provider, global).

        Returns:
            Unique key for this rate limit bucket.

        Examples:
            >>> _build_key("POST /api/v1/auth/login", "192.168.1.1", "ip")
            "ip:192.168.1.1:POST /api/v1/auth/login"

            >>> _build_key("schwab_api", "user:123:schwab", "user_provider")
            "user_provider:user:123:schwab:schwab_api"
        """
        # Format: {scope}:{identifier}:{endpoint}
        return f"{scope}:{identifier}:{endpoint}"
