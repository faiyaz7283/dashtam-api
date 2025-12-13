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
from typing import Any

from src.core.errors import DomainError
from src.infrastructure.enums import InfrastructureErrorCode


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


# Note: Provider errors (ProviderError, ProviderAuthenticationError, etc.)
# are defined in src.domain.errors because they are part of the ProviderProtocol
# contract. Import them from domain:
#     from src.domain.errors import ProviderError, ProviderAuthenticationError
