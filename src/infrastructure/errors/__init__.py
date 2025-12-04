"""Infrastructure errors package.

Exports infrastructure-level error classes for convenient importing.

Usage:
    from src.infrastructure.errors import DatabaseError, CacheError

Note:
    Provider errors (ProviderError, ProviderAuthenticationError, etc.) are
    defined in src.domain.errors because they are part of the ProviderProtocol
    contract. Import them from domain:
        from src.domain.errors import ProviderError, ProviderAuthenticationError
"""

from src.infrastructure.errors.infrastructure_error import (
    CacheError,
    DatabaseError,
    ExternalServiceError,
    InfrastructureError,
)

__all__ = [
    "InfrastructureError",
    "DatabaseError",
    "CacheError",
    "ExternalServiceError",
]
