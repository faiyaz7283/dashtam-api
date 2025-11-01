"""Rate Limiter service orchestrator.

This module provides the main RateLimiterService class that orchestrates
Rate Limiter by combining configuration, algorithms, and storage backends.
It follows the Facade pattern, providing a simple interface to the complex
Rate Limiter subsystem.

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
       - Rate Limiter not single point of failure

Usage:
    ```python
    from src.rate_limiter.service import RateLimiterService
    from src.rate_limiter.algorithms import TokenBucketAlgorithm
    from src.rate_limiter.storage import RedisRateLimitStorage
    from src.rate_limiter.config import RateLimitRule, RateLimitStrategy, RateLimitStorage

    # Define application-specific rules
    rules = {
        "POST /api/v1/auth/login": RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=20,
            refill_rate=5.0,
            scope="ip",
            enabled=True,
        ),
    }

    algorithm = TokenBucketAlgorithm()
    storage = RedisRateLimitStorage(redis_client)
    rate_limiter = RateLimiterService(algorithm, storage, rules)

    allowed, retry_after = await rate_limiter.is_allowed(
        endpoint="POST /api/v1/auth/login",
        identifier="192.168.1.1",
        cost=1
    )
    ```
"""

import logging
import time
from typing import Optional

from src.rate_limiter.algorithms.base import RateLimitAlgorithm
from src.rate_limiter.config import RateLimitRule
from src.rate_limiter.storage.base import RateLimitStorage

logger = logging.getLogger(__name__)


class RateLimiterService:
    """Rate Limiter service orchestrator.

    This service combines configuration, algorithms, and storage backends
    to provide a simple interface for Rate Limiter. It follows the Facade
    pattern, hiding the complexity of the Rate Limiter subsystem.

    SOLID: Dependency Inversion Principle
        This class depends on abstractions (RateLimitAlgorithm, RateLimitStorage)
        not concrete implementations. This enables:
        - Testing with mocks
        - Swapping implementations without code changes
        - Adding new algorithms/storage backends via extension

    Fail-Open Strategy:
        If any component fails (algorithm, storage, config), this service
        allows the request to proceed. This ensures Rate Limiter doesn't
        become a single point of failure.

    Thread Safety:
        - This class is thread-safe (no shared mutable state)
        - Algorithm and storage backends must also be thread-safe
        - Safe for concurrent use across multiple requests

    Examples:
        Basic usage with injected rules:
        ```python
        rules = {
            "POST /api/v1/auth/login": RateLimitRule(
                strategy=RateLimitStrategy.TOKEN_BUCKET,
                storage=RateLimitStorage.REDIS,
                max_tokens=20,
                refill_rate=5.0,
                scope="ip",
                enabled=True,
            ),
        }

        rate_limiter = RateLimiterService(
            algorithm=TokenBucketAlgorithm(),
            storage=RedisRateLimitStorage(redis_client),
            rules=rules
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
        rules: dict[str, RateLimitRule],
    ):
        """Initialize Rate Limiter service.

        Args:
            algorithm: Rate Limiter algorithm implementation (e.g., TokenBucketAlgorithm).
            storage: Storage backend for rate limit state (e.g., RedisRateLimitStorage).
            rules: Mapping of endpoint identifiers to rate limit rules.
                   Application-specific rules injected from application layer.

        Note:
            These dependencies are injected to enable:
            - Testing with mocks
            - Swapping implementations at runtime
            - Following Dependency Inversion Principle
            - Generic component (no application-specific configuration)
        """
        self.algorithm = algorithm
        self.storage = storage
        self.rules = rules

    async def is_allowed(
        self,
        endpoint: str,
        identifier: str,
        cost: int = 1,
    ) -> tuple[bool, float, Optional[RateLimitRule]]:
        """Check if request is allowed under Rate Limiter rules.

        This is the main entry point for Rate Limiter. It:
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
            IP-based Rate Limiter (login endpoint):
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

            User-based Rate Limiter (provider endpoints):
            ```python
            allowed, retry_after, rule = await rate_limiter.is_allowed(
                endpoint="GET /api/v1/providers",
                identifier=f\"user:{user_id}\"
            )
            ```

            User-per-provider Rate Limiter (API calls):
            ```python
            allowed, retry_after, rule = await rate_limiter.is_allowed(
                endpoint=\"schwab_api\",
                identifier=f\"user:{user_id}:schwab\",
                cost=5  # Expensive operation
            )
            ```
        """
        # Start timing for performance monitoring
        start_time = time.perf_counter()

        try:
            # Step 1: Look up rate limit rule from injected rules
            rule = self.rules.get(endpoint)
            if rule is None or not rule.enabled:
                # No Rate Limiter configured for this endpoint
                logger.debug(
                    "Rate limit: No rule configured",
                    extra={
                        "endpoint": endpoint,
                        "identifier": identifier,
                        "rule_configured": False,
                    },
                )
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

            # Calculate execution time
            execution_time_ms = (time.perf_counter() - start_time) * 1000

            # Calculate window from refill rate (tokens/min -> seconds to fill bucket)
            window_seconds = int((rule.max_tokens / rule.refill_rate) * 60)

            if allowed:
                # Rate limit check passed (HIT)
                logger.info(
                    "Rate limit: Request allowed",
                    extra={
                        "endpoint": endpoint,
                        "identifier": identifier,
                        "rule_endpoint": endpoint,  # endpoint serves as rule identifier
                        "cost": cost,
                        "limit": rule.max_tokens,
                        "window_seconds": window_seconds,
                        "execution_time_ms": f"{execution_time_ms:.2f}",
                        "result": "allowed",
                    },
                )
            else:
                # Rate limit check failed (MISS)
                logger.warning(
                    "Rate limit: Request blocked",
                    extra={
                        "endpoint": endpoint,
                        "identifier": identifier,
                        "rule_endpoint": endpoint,  # endpoint serves as rule identifier
                        "cost": cost,
                        "limit": rule.max_tokens,
                        "window_seconds": window_seconds,
                        "retry_after": f"{retry_after:.2f}",
                        "execution_time_ms": f"{execution_time_ms:.2f}",
                        "result": "blocked",
                    },
                )

            return allowed, retry_after, rule

        except Exception as e:
            # Calculate execution time even for failures
            execution_time_ms = (time.perf_counter() - start_time) * 1000

            # Fail-open: Allow request if any error occurs
            logger.error(
                "Rate limit: Service failure (fail-open)",
                extra={
                    "endpoint": endpoint,
                    "identifier": identifier,
                    "cost": cost,
                    "error": str(e),
                    "execution_time_ms": f"{execution_time_ms:.2f}",
                    "result": "fail_open",
                },
                exc_info=True,
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
