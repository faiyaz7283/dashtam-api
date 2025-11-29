"""Rate Limit domain events.

Pattern: 3 events per workflow (ATTEMPTED -> ALLOWED/DENIED)
- *Attempted: Rate limit check initiated (before check)
- *Allowed: Request allowed (rate limit check passed)
- *Denied: Request denied due to rate limit exceeded

Handlers:
- LoggingEventHandler: ALL 3 events (structured logging)
- AuditEventHandler: ALL 3 events (compliance)
- AlertEventHandler: DENIED only (future - ops alerts)
"""

from dataclasses import dataclass

from src.domain.events.base_event import DomainEvent


# ═══════════════════════════════════════════════════════════════
# Rate Limit Check (Workflow)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class RateLimitCheckAttempted(DomainEvent):
    """Rate limit check initiated.

    Emitted before rate limit check to record the attempt.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record RATE_LIMIT_CHECK_ATTEMPTED

    Attributes:
        endpoint: The endpoint being rate limited.
        identifier: The identifier being rate limited (IP, user_id, etc.).
        scope: Rate limit scope type (ip, user, user_provider, global).
        cost: Number of tokens being requested.
    """

    endpoint: str
    identifier: str
    scope: str
    cost: int


@dataclass(frozen=True, kw_only=True)
class RateLimitCheckAllowed(DomainEvent):
    """Request allowed after rate limit check.

    Emitted when request passes rate limit check (tokens available).

    Triggers:
    - LoggingEventHandler: Log allowed (DEBUG level)
    - AuditEventHandler: Record RATE_LIMIT_CHECK_ALLOWED

    Attributes:
        endpoint: The endpoint being rate limited.
        identifier: The identifier being rate limited.
        scope: Rate limit scope type.
        remaining_tokens: Tokens remaining after this request.
        execution_time_ms: Time taken to check rate limit.
    """

    endpoint: str
    identifier: str
    scope: str
    remaining_tokens: int
    execution_time_ms: float


@dataclass(frozen=True, kw_only=True)
class RateLimitCheckDenied(DomainEvent):
    """Request denied due to rate limit exceeded.

    Emitted when request is blocked due to insufficient tokens.
    This is a security-relevant event for compliance and monitoring.

    Triggers:
    - LoggingEventHandler: Log denial (WARNING level)
    - AuditEventHandler: Record RATE_LIMIT_CHECK_DENIED
    - AlertEventHandler: (future) Trigger ops alerts if threshold exceeded

    Attributes:
        endpoint: The endpoint being rate limited.
        identifier: The identifier being rate limited.
        scope: Rate limit scope type.
        retry_after: Seconds until request can be retried.
        execution_time_ms: Time taken to check rate limit.
    """

    endpoint: str
    identifier: str
    scope: str
    retry_after: float
    execution_time_ms: float
