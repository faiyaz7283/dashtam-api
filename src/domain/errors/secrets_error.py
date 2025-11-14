"""Secrets management error types.

Used when secrets retrieval or parsing fails.
Domain-specific error for secrets management system.

Usage:
    from src.domain.errors import SecretsError
    from src.core.enums import ErrorCode
    from src.core.result import Failure
    
    return Failure(SecretsError(
        code=ErrorCode.SECRET_NOT_FOUND,
        message="Secret not found: database/password"
    ))
"""

from dataclasses import dataclass

from src.core.errors import DomainError


@dataclass(frozen=True, slots=True, kw_only=True)
class SecretsError(DomainError):
    """Secrets management failure.
    
    Used by secrets adapters when secret retrieval or parsing fails.

    Attributes:
        code: ErrorCode enum (SECRET_NOT_FOUND, SECRET_ACCESS_DENIED, etc.).
        message: Human-readable message.
        details: Additional context.
    """

    pass  # Inherits all fields from DomainError
