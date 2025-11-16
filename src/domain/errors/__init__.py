"""Domain errors package.

Exports all domain-level error classes for convenient importing.

Usage:
    from src.domain.errors import AuditError, SecretsError
"""

from src.domain.errors.audit_error import AuditError
from src.domain.errors.secrets_error import SecretsError

__all__ = ["AuditError", "SecretsError"]
