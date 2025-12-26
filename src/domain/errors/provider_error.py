"""Provider error types for domain protocol contracts.

These errors are part of the ProviderProtocol contract - they define
the failure cases that provider implementations can return.

Architecture:
- Domain layer errors (part of protocol contract)
- Inherit from DomainError (core layer)
- Used in Result types (railway-oriented programming)
- Infrastructure provider implementations return these errors

Usage:
    from src.domain.errors import ProviderError, ProviderAuthenticationError
    from src.core.result import Result, Success, Failure

    async def fetch_accounts(
        self, access_token: str
    ) -> Result[list[Account], ProviderError]:
        if not valid_token:
            return Failure(ProviderAuthenticationError(...))
        return Success(accounts)

Reference:
    - docs/architecture/provider-domain-model.md
    - docs/architecture/error-handling-architecture.md
"""

from dataclasses import dataclass
from typing import Any

from src.core.errors import DomainError


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderError(DomainError):
    """Base financial provider API error.

    Used for provider-specific errors from Schwab, Chase, Yodlee, etc.
    Subclassed for specific error types.

    Attributes:
        code: Domain ErrorCode.
        message: Human-readable message.
        provider_name: Name of the provider (schwab, chase, etc.).
        details: Additional context (API error code, response).
    """

    provider_name: str
    details: dict[str, Any] | None = None


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
