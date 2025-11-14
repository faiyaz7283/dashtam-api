"""Infrastructure errors package.

Exports all infrastructure-level error classes for convenient importing.

Usage:
    from src.infrastructure.errors import DatabaseError, CacheError
"""

from src.infrastructure.errors.infrastructure_error import (
    CacheError,
    DatabaseError,
    ExternalServiceError,
    InfrastructureError,
    ProviderError,
)

__all__ = [
    "InfrastructureError",
    "DatabaseError",
    "CacheError",
    "ExternalServiceError",
    "ProviderError",
]
