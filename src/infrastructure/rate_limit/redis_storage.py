"""Redis-backed storage for rate limiting using atomic Lua scripts.

This module implements the low-level token bucket operations against Redis using
an atomic Lua script (EVALSHA). It is intentionally focused on storage concerns
(key shaping is done by the higher-level adapter).

Fail-open policy:
    All public methods return Success on infrastructure failures with conservative
    defaults that ALLOW requests. Actual system errors (e.g., admin reset failure)
    are returned as Failure(RateLimitError).

Note:
    This is a storage component used by the higher-level adapter that implements
    RateLimitProtocol. It is not exposed directly to the presentation layer.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from time import time
from typing import Any

from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success
from src.domain.errors import RateLimitError
from src.domain.value_objects.rate_limit_rule import RateLimitRule


@dataclass(slots=True)
class _LuaRefs:
    """Holds compiled Lua script SHA references."""

    token_bucket_sha: str | None = None


class RedisStorage:
    """Redis storage for rate limiting with atomic Lua script.

    This class loads the token bucket Lua script once and executes it via
    EVALSHA for atomic check/consume operations.

    Args:
        redis_client: An async Redis client (redis.asyncio.Redis compatible).

    Attributes:
        redis: The Redis client instance.
        _lua: Cached Lua script SHAs.

    """

    def __init__(self, *, redis_client: Any) -> None:
        self.redis = redis_client
        self._lua = _LuaRefs()
        self._script_lock = asyncio.Lock()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    async def check_and_consume(
        self,
        *,
        key_base: str,
        rule: RateLimitRule,
        cost: int = 1,
        now_ts: float | None = None,
    ) -> Result[tuple[bool, float, int], RateLimitError]:
        """Atomically check and optionally consume tokens.

        Uses Lua script to ensure check-and-consume is a single atomic operation.

        Args:
            key_base: Base key for bucket (no suffix; storage adds ':tokens'/' :time').
            rule: Rate limit rule containing capacity/refill.
            cost: Tokens to consume for this request.
            now_ts: Override current timestamp in seconds (for testing). Defaults to time().

        Returns:
            Result with tuple: (allowed, retry_after_seconds, remaining_tokens)

        Fail-open:
            On Redis errors, returns Success(True, 0.0, rule.max_tokens).
        """
        try:
            sha = await self._ensure_token_bucket_script()
            now = now_ts if now_ts is not None else time()
            resp = await self.redis.evalsha(
                sha,
                1,
                key_base,
                int(rule.max_tokens),
                float(rule.refill_rate),
                int(max(0, cost)),
                float(now),
            )
            # Expect resp: [allowed(0/1), retry_after(float), remaining(int)]
            allowed = bool(resp[0])
            retry_after = float(resp[1])
            remaining = int(resp[2])
            return Success(value=(allowed, retry_after, remaining))
        except Exception:  # Fail-open
            return Success(value=(True, 0.0, rule.max_tokens))

    async def get_remaining(
        self,
        *,
        key_base: str,
        rule: RateLimitRule,
        now_ts: float | None = None,
    ) -> Result[int, RateLimitError]:
        """Get remaining tokens without consuming any.

        Implementation detail: calls Lua with cost=0 to avoid consumption.

        Fail-open:
            On Redis errors, returns Success(rule.max_tokens).
        """
        result = await self.check_and_consume(
            key_base=key_base, rule=rule, cost=0, now_ts=now_ts
        )
        match result:
            case Success(value=(_, _, remaining)):
                return Success(value=remaining)
            case _:
                # Fail-open: return max tokens on any error
                return Success(value=rule.max_tokens)

    async def reset(
        self,
        *,
        key_base: str,
        rule: RateLimitRule,
        now_ts: float | None = None,
    ) -> Result[None, RateLimitError]:
        """Reset the bucket to full capacity.

        Unlike check operations, reset should report real errors to callers.
        """
        try:
            now = now_ts if now_ts is not None else time()
            ttl = rule.ttl_seconds
            pipe = self.redis.pipeline(transaction=True)
            pipe.setex(f"{key_base}:tokens", ttl, int(rule.max_tokens))
            pipe.setex(f"{key_base}:time", ttl, float(now))
            await pipe.execute()
            return Success(value=None)
        except Exception as exc:
            return Failure(
                error=RateLimitError(
                    code=ErrorCode.RATE_LIMIT_RESET_FAILED,
                    message=f"Failed to reset rate limit for '{key_base}': {exc}",
                    details={"key_base": key_base},
                )
            )

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    async def _ensure_token_bucket_script(self) -> str:
        """Load token bucket Lua script into Redis and cache the SHA.

        Returns:
            str: Script SHA.
        """
        if self._lua.token_bucket_sha:
            return self._lua.token_bucket_sha
        async with self._script_lock:
            if self._lua.token_bucket_sha:
                return self._lua.token_bucket_sha
            script = await _read_lua_script("lua_scripts/token_bucket.lua")
            sha: str = await self.redis.script_load(script)
            self._lua.token_bucket_sha = sha
            return sha


def _read_lua_script_sync(path: Path) -> str:
    """Synchronous helper to read Lua script (called via run_in_executor)."""
    return path.read_text(encoding="utf-8")


async def _read_lua_script(rel_path: str) -> str:
    """Read Lua script file relative to this module.

    Uses run_in_executor to avoid blocking the event loop on file IO.

    Args:
        rel_path: Relative path from this module's directory.

    Returns:
        Script contents as string.
    """
    base_dir = Path(__file__).parent
    full_path = base_dir / rel_path
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_read_lua_script_sync, full_path))
