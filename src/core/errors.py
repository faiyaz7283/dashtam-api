"""Base error classes for domain-level error handling.

This module defines the error hierarchy for the application. All domain errors
should inherit from DashtamError to enable consistent error handling.

Error Hierarchy:
    DashtamError (base)
    ├── ValidationError (input validation failures)
    ├── NotFoundError (resource not found)
    ├── ConflictError (duplicate resource, state conflict)
    ├── AuthenticationError (authentication failures)
    └── AuthorizationError (permission denied)
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class DashtamError(Exception):
    """Base error class for all domain errors.

    Attributes:
        message: Human-readable error message.
        code: Machine-readable error code (optional).
    """

    message: str
    code: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationError(DashtamError):
    """Input validation failed.

    Attributes:
        message: Human-readable error message.
        code: Machine-readable error code (optional).
        field: Field name that failed validation (optional).
    """

    field: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class NotFoundError(DashtamError):
    """Requested resource was not found.

    Attributes:
        message: Human-readable error message.
        code: Machine-readable error code (optional).
        resource_type: Type of resource (e.g., "User", "Account").
        resource_id: ID of the resource that was not found.
    """

    resource_type: str
    resource_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ConflictError(DashtamError):
    """Resource already exists or state conflict.

    Attributes:
        message: Human-readable error message.
        code: Machine-readable error code (optional).
        resource_type: Type of resource in conflict.
    """

    resource_type: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthenticationError(DashtamError):
    """Authentication failed (invalid credentials, token expired).

    Attributes:
        message: Human-readable error message.
        code: Machine-readable error code (optional).
    """

    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthorizationError(DashtamError):
    """User does not have permission to perform action.

    Attributes:
        message: Human-readable error message.
        code: Machine-readable error code (optional).
        required_permission: Permission that was required (optional).
    """

    required_permission: str | None = None
