"""Audit Backend Implementations for Rate Limiting.

This package contains concrete implementations of the AuditBackend interface.

Available Backends:
    - DatabaseAuditBackend: Logs violations to PostgreSQL (database.py)

Usage:
    >>> from src.rate_limiting.audit_backends.database import DatabaseAuditBackend
    >>> backend = DatabaseAuditBackend(db_session)
    >>> await backend.log_violation(...)
"""
