"""Audit Backend Implementations for Rate Limiter.

This package contains concrete implementations of the AuditBackend interface.

Interface:
    - AuditBackend: Abstract base class (base.py)

Available Backends:
    - DatabaseAuditBackend: Logs violations to PostgreSQL (database.py)

Usage:
    >>> from src.rate_limiter.audit_backends.base import AuditBackend
    >>> from src.rate_limiter.audit_backends.database import DatabaseAuditBackend
    >>> backend: AuditBackend = DatabaseAuditBackend(db_session)
    >>> await backend.log_violation(...)
"""

from src.rate_limiter.audit_backends.base import AuditBackend
from src.rate_limiter.audit_backends.database import DatabaseAuditBackend

__all__ = ["AuditBackend", "DatabaseAuditBackend"]
