"""Token bucket adapter implementing RateLimitProtocol.

This adapter integrates RedisStorage with the domain protocol, providing:
- Key construction based on scope (IP, USER, USER_PROVIDER, GLOBAL)
- Rule lookup from centralized configuration
- Domain event publishing (Attempted, Succeeded, Failed)
- Structured logging
- Fail-open semantics at all layers

Architecture:
    Domain Protocol <- TokenBucketAdapter -> RedisStorage -> Redis

Usage:
    from src.core.container import get_rate_limit
    from src.domain.protocols import RateLimitProtocol

    rate_limit: RateLimitProtocol = get_rate_limit()
    result = await rate_limit.is_allowed(
        endpoint="POST /api/v1/sessions",
        identifier="192.168.1.1",
    )
"""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING
from uuid import uuid4

from src.core.result import Failure, Result, Success
from src.domain.enums import RateLimitScope
from src.domain.errors import RateLimitError
from src.domain.events.rate_limit_events import (
    RateLimitCheckAllowed,
    RateLimitCheckAttempted,
    RateLimitCheckDenied,
)
from src.domain.value_objects.rate_limit_rule import RateLimitResult, RateLimitRule

if TYPE_CHECKING:
    from src.domain.protocols.event_bus_protocol import EventBusProtocol
    from src.domain.protocols.logger_protocol import LoggerProtocol
    from src.infrastructure.rate_limit.redis_storage import RedisStorage


class TokenBucketAdapter:
    """Token bucket rate limiter implementing RateLimitProtocol.

    This adapter coordinates between:
    - RedisStorage: Low-level atomic token bucket operations
    - Rules configuration: Endpoint -> RateLimitRule mapping
    - EventBus: Domain event publishing
    - Logger: Structured logging

    Fail-Open Design:
        All public methods return Success with allowed=True if any error occurs.
        Rate limit failures should NEVER cause denial-of-service.

    Args:
        storage: RedisStorage instance for atomic token bucket operations.
        rules: Mapping of endpoint to RateLimitRule configuration.
        event_bus: EventBus for domain event publishing.
        logger: Structured logger for observability.
    """

    def __init__(
        self,
        *,
        storage: RedisStorage,
        rules: dict[str, RateLimitRule],
        event_bus: EventBusProtocol,
        logger: LoggerProtocol,
    ) -> None:
        self._storage = storage
        self._rules = rules
        self._event_bus = event_bus
        self._logger = logger

    # -------------------------------------------------------------------------
    # RateLimitProtocol implementation
    # -------------------------------------------------------------------------
    async def is_allowed(
        self,
        *,
        endpoint: str,
        identifier: str,
        cost: int = 0,
    ) -> Result[RateLimitResult, RateLimitError]:
        """Check if request is allowed and consume tokens if so.

        Implements the main rate limiting logic with fail-open semantics.

        Args:
            endpoint: The endpoint being accessed (e.g., "POST /api/v1/sessions").
            identifier: The identifier to rate limit (IP address, user ID, etc.).
            cost: Number of tokens to consume. Default 1.

        Returns:
            Result[RateLimitResult, RateLimitError]:
                - Success(RateLimitResult) with rate limit decision
                - Failure only for severe errors (should be rare)

        Fail-Open:
            On any error, returns Success(RateLimitResult(allowed=True, ...)).
        """
        start_time = perf_counter()

        # Lookup rule for endpoint
        rule = self._rules.get(endpoint)
        if rule is None:
            # No rule configured - allow request (fail-open)
            self._logger.debug(
                "Rate limit rule not found",
                endpoint=endpoint,
                identifier=identifier,
            )
            return Success(
                value=RateLimitResult(
                    allowed=True,
                    retry_after=0.0,
                    remaining=0,
                    limit=0,
                    reset_seconds=0,
                )
            )

        # Check if rule is disabled
        if not rule.enabled:
            return Success(
                value=RateLimitResult(
                    allowed=True,
                    retry_after=0.0,
                    remaining=rule.max_tokens,
                    limit=rule.max_tokens,
                    reset_seconds=0,
                )
            )

        # Construct Redis key based on scope
        key_base = self._build_key(
            endpoint=endpoint, identifier=identifier, scope=rule.scope
        )

        # Publish ATTEMPTED event
        await self._publish_attempted(
            endpoint=endpoint,
            identifier=identifier,
            scope=rule.scope,
            cost=cost,
        )

        # Check and consume tokens
        effective_cost = cost if cost > 0 else rule.cost
        result = await self._storage.check_and_consume(
            key_base=key_base,
            rule=rule,
            cost=effective_cost,
        )

        elapsed_ms = (perf_counter() - start_time) * 1000

        match result:
            case Success(value=(allowed, retry_after, remaining)):
                rate_result = RateLimitResult(
                    allowed=allowed,
                    retry_after=retry_after,
                    remaining=remaining,
                    limit=rule.max_tokens,
                    reset_seconds=rule.ttl_seconds,
                )

                if allowed:
                    await self._publish_allowed(
                        endpoint=endpoint,
                        identifier=identifier,
                        scope=rule.scope,
                        remaining_tokens=remaining,
                        execution_time_ms=elapsed_ms,
                    )
                else:
                    await self._publish_denied(
                        endpoint=endpoint,
                        identifier=identifier,
                        scope=rule.scope,
                        retry_after=retry_after,
                        execution_time_ms=elapsed_ms,
                    )

                return Success(value=rate_result)

            case _:
                # Fail-open on any unexpected result
                self._logger.warning(
                    "Rate limit storage error - allowing request",
                    endpoint=endpoint,
                    identifier=identifier,
                )
                return Success(
                    value=RateLimitResult(
                        allowed=True,
                        retry_after=0.0,
                        remaining=rule.max_tokens,
                        limit=rule.max_tokens,
                        reset_seconds=rule.ttl_seconds,
                    )
                )

    async def get_remaining(
        self,
        *,
        endpoint: str,
        identifier: str,
    ) -> Result[int, RateLimitError]:
        """Get remaining tokens without consuming any.

        Args:
            endpoint: The endpoint to check.
            identifier: The identifier to check.

        Returns:
            Result[int, RateLimitError]: Remaining tokens or max if error.
        """
        rule = self._rules.get(endpoint)
        if rule is None or not rule.enabled:
            return Success(value=0)

        key_base = self._build_key(
            endpoint=endpoint, identifier=identifier, scope=rule.scope
        )
        return await self._storage.get_remaining(key_base=key_base, rule=rule)

    async def reset(
        self,
        *,
        endpoint: str,
        identifier: str,
    ) -> Result[None, RateLimitError]:
        """Reset rate limit bucket to full capacity.

        Unlike is_allowed, this method does NOT fail-open.
        Admin operations should know if they succeeded or failed.

        Args:
            endpoint: The endpoint to reset.
            identifier: The identifier to reset.

        Returns:
            Result[None, RateLimitError]: Success or failure.
        """
        rule = self._rules.get(endpoint)
        if rule is None:
            # No rule configured - nothing to reset (success)
            return Success(value=None)

        key_base = self._build_key(
            endpoint=endpoint, identifier=identifier, scope=rule.scope
        )
        result = await self._storage.reset(key_base=key_base, rule=rule)

        match result:
            case Success():
                self._logger.info(
                    "Rate limit reset",
                    endpoint=endpoint,
                    identifier=identifier,
                )
            case Failure(error=err):
                self._logger.error(
                    "Rate limit reset failed",
                    endpoint=endpoint,
                    identifier=identifier,
                    error_message=str(err),
                )

        return result

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------
    def _build_key(
        self,
        *,
        endpoint: str,
        identifier: str,
        scope: RateLimitScope,
    ) -> str:
        """Build Redis key based on scope.

        Key format: rate_limit:{scope_prefix}:{identifier}:{endpoint}

        Args:
            endpoint: The endpoint being accessed.
            identifier: The identifier to rate limit.
            scope: Rate limit scope (determines key format).

        Returns:
            str: Redis key for the bucket.
        """
        match scope:
            case RateLimitScope.IP:
                return f"rate_limit:ip:{identifier}:{endpoint}"
            case RateLimitScope.USER:
                return f"rate_limit:user:{identifier}:{endpoint}"
            case RateLimitScope.USER_PROVIDER:
                return f"rate_limit:user_provider:{identifier}:{endpoint}"
            case RateLimitScope.GLOBAL:
                return f"rate_limit:global:{endpoint}"

    async def _publish_attempted(
        self,
        *,
        endpoint: str,
        identifier: str,
        scope: RateLimitScope,
        cost: int,
    ) -> None:
        """Publish RateLimitCheckAttempted event."""
        try:
            await self._event_bus.publish(
                RateLimitCheckAttempted(
                    event_id=uuid4(),
                    endpoint=endpoint,
                    identifier=identifier,
                    scope=scope.value,
                    cost=cost,
                )
            )
        except Exception as exc:
            # Fail-open: log but don't block
            self._logger.warning(
                "Failed to publish RateLimitCheckAttempted event",
                error=str(exc),
            )

    async def _publish_allowed(
        self,
        *,
        endpoint: str,
        identifier: str,
        scope: RateLimitScope,
        remaining_tokens: int,
        execution_time_ms: float,
    ) -> None:
        """Publish RateLimitCheckAllowed event."""
        try:
            await self._event_bus.publish(
                RateLimitCheckAllowed(
                    event_id=uuid4(),
                    endpoint=endpoint,
                    identifier=identifier,
                    scope=scope.value,
                    remaining_tokens=remaining_tokens,
                    execution_time_ms=execution_time_ms,
                )
            )
        except Exception as exc:
            # Fail-open: log but don't block
            self._logger.warning(
                "Failed to publish RateLimitCheckAllowed event",
                error=str(exc),
            )

    async def _publish_denied(
        self,
        *,
        endpoint: str,
        identifier: str,
        scope: RateLimitScope,
        retry_after: float,
        execution_time_ms: float,
    ) -> None:
        """Publish RateLimitCheckDenied event."""
        try:
            await self._event_bus.publish(
                RateLimitCheckDenied(
                    event_id=uuid4(),
                    endpoint=endpoint,
                    identifier=identifier,
                    scope=scope.value,
                    retry_after=retry_after,
                    execution_time_ms=execution_time_ms,
                )
            )
        except Exception as exc:
            # Fail-open: log but don't block
            self._logger.warning(
                "Failed to publish RateLimitCheckDenied event",
                error=str(exc),
            )
