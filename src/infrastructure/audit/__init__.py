"""Audit infrastructure implementations.

This module contains concrete implementations of audit protocols
for different database backends.
"""

from src.infrastructure.audit.postgres_adapter import PostgresAuditAdapter

__all__ = ["PostgresAuditAdapter"]
