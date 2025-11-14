"""Base domain error class for Railway-Oriented Programming.

DomainError is the abstract base class for ALL application errors.
Domain errors represent business rule violations and validation failures.
They flow through the system as data (Result types), not exceptions.

Architecture:
- Base class for all error types (core, domain, infrastructure)
- Does NOT inherit from Exception (not raised, returned in Result)
- Uses dataclass inheritance (NOT Protocol/ABC)
- Type-safe with Result[T, DomainError]

Usage:
    from src.core.errors import DomainError
    from src.core.enums import ErrorCode
    
    @dataclass(frozen=True, slots=True, kw_only=True)
    class MyError(DomainError):
        pass  # Inherits code, message, details
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
