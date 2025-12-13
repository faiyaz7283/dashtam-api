"""Rate limit infrastructure adapters.

This package provides infrastructure implementations for rate limiting,
following the hexagonal architecture pattern where infrastructure implements
domain ports.

Exports:
    RedisStorage: Redis-backed token bucket storage with atomic Lua scripts.
    TokenBucketAdapter: Token bucket adapter implementing RateLimitProtocol.
    RATE_LIMIT_RULES: Endpoint to rate limit rule mapping (SSOT).
    get_rule_for_endpoint: Helper to lookup rules with path parameter support.
"""

from src.infrastructure.rate_limit.config import (
    RATE_LIMIT_RULES,
    get_rule_for_endpoint,
)
from src.infrastructure.rate_limit.redis_storage import RedisStorage
from src.infrastructure.rate_limit.token_bucket_adapter import TokenBucketAdapter

__all__ = [
    "RATE_LIMIT_RULES",
    "RedisStorage",
    "TokenBucketAdapter",
    "get_rule_for_endpoint",
]
