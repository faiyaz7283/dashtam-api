"""Rate limiting algorithms package.

This package contains all rate limiting algorithm implementations following
the Strategy Pattern. Each algorithm implements the RateLimitAlgorithm interface
and can be swapped without changing the rate limiter service.

Available Algorithms:
    - TokenBucketAlgorithm: Token bucket with refill (best for financial APIs)
    - SlidingWindowAlgorithm: Sliding window counter (coming in future phase)
    - FixedWindowAlgorithm: Fixed window counter (coming in future phase)

Usage:
    ```python
    from src.rate_limiter.algorithms import RateLimitAlgorithm, TokenBucketAlgorithm

    algorithm = TokenBucketAlgorithm()
    allowed, retry_after = await algorithm.is_allowed(storage, key, rule, cost)
    ```
"""

from src.rate_limiter.algorithms.base import RateLimitAlgorithm
from src.rate_limiter.algorithms.token_bucket import TokenBucketAlgorithm

__all__ = [
    "RateLimitAlgorithm",
    "TokenBucketAlgorithm",
]
