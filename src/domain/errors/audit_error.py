"""Audit trail error types.

Used when audit trail recording or querying fails.
Domain-specific error for audit system (F0.9).

Usage:
    from src.domain.errors import AuditError
    from src.core.enums import ErrorCode
    from src.core.result import Failure
    
    return Failure(AuditError(
        code=ErrorCode.AUDIT_RECORD_FAILED,
        message="Failed to record audit entry: database connection lost"
    ))
"""

from dataclasses import dataclass

from src.core.errors import DomainError


@dataclass(frozen=True, slots=True, kw_only=True)
class AuditError(DomainError):
    """Audit system failure.
    
    Used when audit trail recording or querying fails (database error,
    connection loss, etc.).

    Attributes:
        code: ErrorCode enum (AUDIT_RECORD_FAILED, AUDIT_QUERY_FAILED).
        message: Human-readable message.
        details: Additional context.
    """

    pass  # Inherits all fields from DomainError
