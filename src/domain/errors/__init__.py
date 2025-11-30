"""Domain errors package.

Exports all domain-level error classes for convenient importing.

Usage:
    from src.domain.errors import AuditError, SecretsError, AuthenticationError
"""

from src.domain.errors.account_error import AccountError
from src.domain.errors.audit_error import AuditError
from src.domain.errors.authentication_error import AuthenticationError
from src.domain.errors.provider_connection_error import ProviderConnectionError
from src.domain.errors.rate_limit_error import RateLimitError
from src.domain.errors.secrets_error import SecretsError
from src.domain.errors.transaction_error import TransactionError

__all__ = [
    "AccountError",
    "AuditError",
    "AuthenticationError",
    "ProviderConnectionError",
    "RateLimitError",
    "SecretsError",
    "TransactionError",
]
