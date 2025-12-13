"""Rate Limit error types.

Used when rate limiting operations fail (Redis errors, Lua script failures, etc.).
Domain-specific error for Rate Limit system (F1.2).

Usage:
    from src.domain.errors import RateLimitError
    from src.core.enums import ErrorCode
    from src.core.result import Failure

    return Failure(RateLimitError(
        code=ErrorCode.RATE_LIMIT_CHECK_FAILED,
        message="Failed to check rate limit: Redis connection lost"
    ))
"""

from dataclasses import dataclass

from src.core.errors import DomainError


@dataclass(frozen=True, slots=True, kw_only=True)
class RateLimitError(DomainError):
    """Rate limit system failure.

    Used when rate limiting operations fail (Redis connection loss,
    Lua script errors, invalid configuration, etc.).

    Note that rate limit DENIED is NOT an error - it's a successful
    operation that returns allowed=False. This error class is for
    actual system failures.

    Attributes:
        code: ErrorCode enum (RATE_LIMIT_CHECK_FAILED, etc.).
        message: Human-readable message.
        details: Additional context (endpoint, identifier, etc.).

    Design:
        Rate limit follows fail-open design. On errors, implementations
        should return Success(allowed=True) rather than Failure with
        this error type. This error type is primarily for:
        - Configuration errors (rule not found)
        - Reset operation failures (admin needs to know if reset worked)
        - Severe errors that prevent any reasonable default
    """

    pass  # Inherits all fields from DomainError
