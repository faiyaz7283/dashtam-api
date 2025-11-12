"""Infrastructure layer error types.

Infrastructure errors represent failures in external systems (database, cache, providers).

Architecture:
- Infrastructure catches exceptions and maps to DomainError
- Infrastructure errors inherit from DomainError (not Exception)
- Uses InfrastructureErrorCode for internal error tracking
- Maps to domain ErrorCode when flowing to domain layer
- Used with Result types for error propagation
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.core.errors import DomainError


class InfrastructureErrorCode(Enum):
    """Infrastructure-specific error codes.

    These are internal codes for tracking infrastructure failures.
    They are mapped to domain ErrorCode when flowing to domain layer.
    """

    # Database errors
    DATABASE_CONNECTION_FAILED = "database_connection_failed"
    DATABASE_TIMEOUT = "database_timeout"
    DATABASE_CONSTRAINT_VIOLATION = "database_constraint_violation"
    DATABASE_CONFLICT = "database_conflict"
    DATABASE_DATA_ERROR = "database_data_error"
    DATABASE_ERROR = "database_error"
    DATABASE_UNKNOWN_ERROR = "database_unknown_error"

    # Cache errors
    CACHE_CONNECTION_ERROR = "cache_connection_error"
    CACHE_TIMEOUT = "cache_timeout"
    CACHE_GET_ERROR = "cache_get_error"
    CACHE_SET_ERROR = "cache_set_error"
    CACHE_DELETE_ERROR = "cache_delete_error"

    # External service errors
    EXTERNAL_SERVICE_UNAVAILABLE = "external_service_unavailable"
    EXTERNAL_SERVICE_TIMEOUT = "external_service_timeout"
    EXTERNAL_SERVICE_ERROR = "external_service_error"

    # Provider errors
    PROVIDER_CONNECTION_FAILED = "provider_connection_failed"
    PROVIDER_AUTH_REQUIRED = "provider_auth_required"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"


@dataclass(frozen=True, slots=True, kw_only=True)
class InfrastructureError(DomainError):
    """Base infrastructure error.

    Infrastructure errors still use domain ErrorCode enum (not InfrastructureErrorCode).
    The InfrastructureErrorCode is for internal infrastructure tracking only.

    Attributes:
        code: Domain ErrorCode (maps from InfrastructureErrorCode).
        message: Human-readable message.
        infrastructure_code: Original infrastructure error code.
        details: Additional context.
    """

    infrastructure_code: InfrastructureErrorCode | None = None
    details: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DatabaseError(InfrastructureError):
    """Database-specific errors.

    Wraps SQLAlchemy exceptions and provides consistent error handling.

    Attributes:
        code: Domain ErrorCode.
        message: Human-readable message.
        infrastructure_code: Database-specific error code.
        details: Additional context (constraint name, original error).
    """

    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class CacheError(InfrastructureError):
    """Cache-specific errors.

    Wraps Redis/cache exceptions and provides consistent error handling.

    Attributes:
        code: Domain ErrorCode.
        message: Human-readable message.
        infrastructure_code: Cache-specific error code.
        details: Additional context (key, operation, original error).
    """

    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class ExternalServiceError(InfrastructureError):
    """External service integration errors.

    Used for non-provider external services like email, SMS, payment gateways.

    Attributes:
        code: Domain ErrorCode.
        message: Human-readable message.
        infrastructure_code: Service-specific error code.
        service_name: Name of the external service.
        details: Additional context (status code, response).
    """

    service_name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderError(InfrastructureError):
    """Financial provider API errors.

    Used for provider-specific errors from Schwab, Plaid, Yodlee, etc.

    Attributes:
        code: Domain ErrorCode.
        message: Human-readable message.
        infrastructure_code: Provider-specific error code.
        provider_name: Name of the provider (schwab, plaid, etc.).
        details: Additional context (API error code, response).
    """

    provider_name: str
