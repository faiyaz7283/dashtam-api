"""Infrastructure errors package.

Exports all infrastructure-level error classes for convenient importing.

Usage:
    from src.infrastructure.errors import DatabaseError, CacheError
    from src.infrastructure.errors import ProviderAuthenticationError
"""

from src.infrastructure.errors.infrastructure_error import (
    CacheError,
    DatabaseError,
    ExternalServiceError,
    InfrastructureError,
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

__all__ = [
    "InfrastructureError",
    "DatabaseError",
    "CacheError",
    "ExternalServiceError",
    # Provider errors
    "ProviderError",
    "ProviderAuthenticationError",
    "ProviderUnavailableError",
    "ProviderRateLimitError",
    "ProviderInvalidResponseError",
]
