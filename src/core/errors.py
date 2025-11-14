"""Domain-level error handling with Railway-Oriented Programming.

This module defines domain errors using Result types (NOT exceptions).
Domain errors represent business rule violations and validation failures.

Error Hierarchy:
    DomainError (base - does NOT inherit from Exception)
    ├── ValidationError (input validation failures)
    ├── NotFoundError (resource not found)
    ├── ConflictError (duplicate resource, state conflict)
    ├── AuthenticationError (authentication failures)
    └── AuthorizationError (permission denied)

All domain functions return Result[T, DomainError] instead of raising exceptions.
"""

from dataclasses import dataclass

from src.core.enums import ErrorCode


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainError:
    """Base domain error (does NOT inherit from Exception).

    Domain errors represent business rule violations and validation failures.
    They flow through the system as data (Result types), not exceptions.

    Attributes:
        code: Machine-readable error code (enum).
        message: Human-readable error message.
        details: Optional context for debugging.
    """

    code: ErrorCode
    message: str
    details: dict[str, str] | None = None

    def __str__(self) -> str:
        """String representation of error."""
        return f"{self.code.value}: {self.message}"


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


@dataclass(frozen=True, slots=True, kw_only=True)
class SecretsError(DomainError):
    """Secrets management failure.

    Used by secrets adapters when secret retrieval or parsing fails.

    Attributes:
        code: ErrorCode enum (SECRET_NOT_FOUND, SECRET_ACCESS_DENIED, etc.).
        message: Human-readable message.
        details: Additional context.
    """

    pass
