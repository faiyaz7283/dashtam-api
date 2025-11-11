"""Infrastructure layer error types.

Following our error handling architecture:
- Infrastructure errors are mapped to domain errors
- Used with Result types for error propagation
- No exceptions raised to domain layer
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.core.errors import DashtamError


class InfrastructureErrorCode(Enum):
    """Infrastructure-specific error codes."""

    # Database errors
    DATABASE_CONNECTION_FAILED = "database_connection_failed"
    DATABASE_TIMEOUT = "database_timeout"
    DATABASE_CONSTRAINT_VIOLATION = "database_constraint_violation"
    DATABASE_CONFLICT = "database_conflict"
    DATABASE_DATA_ERROR = "database_data_error"
    DATABASE_ERROR = "database_error"
    DATABASE_UNKNOWN_ERROR = "database_unknown_error"

    # External service errors
    EXTERNAL_SERVICE_UNAVAILABLE = "external_service_unavailable"
    EXTERNAL_SERVICE_TIMEOUT = "external_service_timeout"
    EXTERNAL_SERVICE_ERROR = "external_service_error"

    # Provider errors
    PROVIDER_CONNECTION_FAILED = "provider_connection_failed"
    PROVIDER_AUTH_REQUIRED = "provider_auth_required"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"


@dataclass(frozen=True, slots=True, kw_only=True)
class InfrastructureError(DashtamError):
    """Base class for infrastructure layer errors.

    Attributes:
        message: Human-readable error message
        code: Infrastructure error code as string
        details: Additional error context (optional)
    """

    details: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DatabaseError(InfrastructureError):
    """Database-specific errors.

    Used to wrap SQLAlchemy exceptions and provide
    consistent error handling across repositories.

    Attributes:
        message: Human-readable error message
        code: Database error code
        details: Additional context (e.g., constraint name, original error)
    """

    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class ExternalServiceError(InfrastructureError):
    """External service integration errors.

    Used for non-provider external services like
    email, SMS, payment gateways, etc.

    Attributes:
        message: Human-readable error message
        code: Service error code
        service_name: Name of the external service
        details: Additional context (e.g., status code, response)
    """

    service_name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderError(InfrastructureError):
    """Financial provider API errors.

    Used for provider-specific errors from
    Schwab, Plaid, Yodlee, etc.

    Attributes:
        message: Human-readable error message
        code: Provider error code
        provider_name: Name of the provider (schwab, plaid, etc.)
        details: Additional context (e.g., API error code, response)
    """

    provider_name: str
