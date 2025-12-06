"""Common error classes used across all domains and layers.

These are generic errors that don't belong to any specific domain.
They are used throughout the application for common failure scenarios.

Error Types:
- ValidationError: Input validation failures
- NotFoundError: Resource not found
- ConflictError: Resource conflicts (duplicates, state conflicts)
- AuthenticationError: Authentication failures
- AuthorizationError: Authorization failures (no permission)

Usage:
    from src.core.errors import ValidationError, NotFoundError
    from src.core.enums import ErrorCode
    from src.core.result import Failure

    return Failure(ValidationError(
        code=ErrorCode.INVALID_EMAIL,
        message="Invalid email format",
        field="email"
    ))
"""

from dataclasses import dataclass

from src.core.errors.domain_error import DomainError


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationError(DomainError):
    """Input validation failure.

    Attributes:
        code: ErrorCode enum.
        message: Human-readable message.
        field: Field name that failed validation.
        details: Additional context.
    """

    field: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class NotFoundError(DomainError):
    """Resource not found.

    Attributes:
        code: ErrorCode enum.
        message: Human-readable message.
        resource_type: Type of resource (User, Account, etc.).
        resource_id: ID of the resource that was not found.
        details: Additional context.
    """

    resource_type: str
    resource_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ConflictError(DomainError):
    """Resource conflict (duplicate, state conflict).

    Attributes:
        code: ErrorCode enum.
        message: Human-readable message.
        resource_type: Type of resource in conflict.
        conflicting_field: Field that has conflict (email, account_id, etc.).
        details: Additional context.
    """

    resource_type: str
    conflicting_field: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthenticationError(DomainError):
    """Authentication failure (invalid credentials, token expired).

    Attributes:
        code: ErrorCode enum.
        message: Human-readable message.
        details: Additional context.
    """

    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthorizationError(DomainError):
    """Authorization failure (no permission).

    Attributes:
        code: ErrorCode enum.
        message: Human-readable message.
        required_permission: Permission that was required.
        details: Additional context.
    """

    required_permission: str | None = None
