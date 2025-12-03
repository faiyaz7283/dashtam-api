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


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderError(InfrastructureError):
    """Base financial provider API error.

    Used for provider-specific errors from Schwab, Plaid, Yodlee, etc.
    Subclassed for specific error types.

    Attributes:
        code: Domain ErrorCode.
        message: Human-readable message.
        infrastructure_code: Provider-specific error code.
        provider_name: Name of the provider (schwab, plaid, etc.).
        details: Additional context (API error code, response).
    """

    provider_name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderAuthenticationError(ProviderError):
    """Provider authentication/authorization failure.

    Raised when:
    - OAuth authorization code is invalid or expired
    - Access token is invalid or expired
    - Refresh token is invalid or expired
    - User has revoked provider access

    Recovery: User must re-authenticate via OAuth flow.

    Attributes:
        code: Domain ErrorCode (typically PROVIDER_AUTHENTICATION_FAILED).
        message: Human-readable message.
        provider_name: Name of the provider.
        is_token_expired: Whether the error is due to token expiration.
    """

    is_token_expired: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderUnavailableError(ProviderError):
    """Provider API is unavailable.

    Raised when:
    - Provider API returns 5xx errors
    - Connection timeout occurs
    - DNS resolution fails
    - SSL/TLS handshake fails

    Recovery: Retry with exponential backoff.

    Attributes:
        code: Domain ErrorCode (typically PROVIDER_UNAVAILABLE).
        message: Human-readable message.
        provider_name: Name of the provider.
        is_transient: Whether the error is likely transient (True = retry).
        retry_after: Suggested retry delay in seconds (from provider).
    """

    is_transient: bool = True
    retry_after: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderRateLimitError(ProviderError):
    """Provider rate limit exceeded.

    Raised when provider returns 429 Too Many Requests.

    Recovery: Wait for retry_after seconds before retrying.

    Attributes:
        code: Domain ErrorCode (typically PROVIDER_RATE_LIMITED).
        message: Human-readable message.
        provider_name: Name of the provider.
        retry_after: Seconds to wait before retrying (from Retry-After header).
    """

    retry_after: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderInvalidResponseError(ProviderError):
    """Provider returned invalid/unexpected response.

    Raised when:
    - Response JSON is malformed
    - Required fields are missing
    - Response doesn't match expected schema

    Recovery: Log for investigation, may need code update.

    Attributes:
        code: Domain ErrorCode (typically PROVIDER_CREDENTIAL_INVALID).
        message: Human-readable message.
        provider_name: Name of the provider.
        response_body: Raw response body for debugging.
    """

    response_body: str | None = None
