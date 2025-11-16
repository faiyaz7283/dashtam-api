"""Core errors package.

Exports all core-level error classes for convenient importing.

Usage:
    from src.core.errors import DomainError, ValidationError, NotFoundError
"""

from src.core.errors.common_errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from src.core.errors.domain_error import DomainError

__all__ = [
    "DomainError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "AuthenticationError",
    "AuthorizationError",
]
