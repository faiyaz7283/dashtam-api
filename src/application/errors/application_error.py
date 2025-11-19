"""Application layer error types.

This module defines application-level errors that wrap domain errors and add
application-specific context (CQRS command/query execution failures).

Exports:
    ApplicationErrorCode: Application-level error code enum
    ApplicationError: Application layer error dataclass
"""

from dataclasses import dataclass
from enum import Enum

from src.core.errors.domain_error import DomainError


class ApplicationErrorCode(Enum):
    """Application-level error codes.

    These codes represent failures at the application layer (command/query handlers),
    typically wrapping domain errors with additional context.

    Examples:
        >>> error = ApplicationError(
        ...     code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
        ...     message="User creation failed",
        ... )
    """

    COMMAND_VALIDATION_FAILED = "command_validation_failed"
    COMMAND_EXECUTION_FAILED = "command_execution_failed"
    QUERY_FAILED = "query_failed"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


@dataclass(frozen=True, slots=True, kw_only=True)
class ApplicationError:
    """Application layer error.

    Wraps domain errors with application-specific context. Used by command and
    query handlers to provide structured error information to the presentation layer.

    Attributes:
        code: Application error code (from ApplicationErrorCode enum)
        message: Human-readable error message
        domain_error: Original domain error (if error originated from domain layer)
        details: Additional context as key-value pairs

    Examples:
        >>> # Command validation failure
        >>> error = ApplicationError(
        ...     code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
        ...     message="User creation failed: validation error",
        ...     domain_error=validation_error,
        ...     details={"field": "email"},
        ... )
        >>>
        >>> # Query failure (no domain error)
        >>> error = ApplicationError(
        ...     code=ApplicationErrorCode.QUERY_FAILED,
        ...     message="User not found",
        ...     details={"user_id": "123e4567-e89b-12d3-a456-426614174000"},
        ... )
    """

    code: ApplicationErrorCode
    message: str
    domain_error: DomainError | None = None
    details: dict[str, str] | None = None
