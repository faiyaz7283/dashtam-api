"""Base API client for provider HTTP communication.

This module provides a base class for provider API clients that handles:
- HTTP request execution with timeout/connection error handling
- Response status code interpretation
- JSON parsing with error handling
- Structured logging with provider context

Subclasses only need to:
1. Build authentication headers (Bearer token, API key, etc.)
2. Call the base methods for HTTP operations

This eliminates ~400 lines of duplicated code across provider API clients.

Architecture:
    - Infrastructure layer (adapter for external APIs)
    - Uses httpx for async HTTP
    - Returns Result types (no exceptions for business errors)

Reference:
    - docs/architecture/provider-integration-architecture.md
    - WARP.md Section 3 (Hexagonal Architecture)
"""

from typing import Any

import httpx
import structlog

from src.core.constants import PROVIDER_TIMEOUT_DEFAULT, RESPONSE_BODY_MAX_LENGTH
from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success
from src.domain.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)


class BaseProviderAPIClient:
    """Base class for provider API clients with shared HTTP handling.

    Provides common functionality for HTTP communication with external APIs:
    - Request execution with timeout/connection error handling
    - Response status code interpretation (401, 403, 404, 429, 5xx)
    - JSON parsing with type validation
    - Structured logging with provider context

    Subclasses must implement their own authentication header building.

    Attributes:
        _base_url: Provider API base URL (without trailing slash).
        _provider_name: Provider identifier for logging and error messages.
        _timeout: HTTP request timeout in seconds.
        _logger: Structured logger with provider context.

    Example:
        >>> class SchwabAccountsAPI(BaseProviderAPIClient):
        ...     def __init__(self, *, base_url: str, timeout: float = 30.0):
        ...         super().__init__(
        ...             base_url=base_url,
        ...             provider_name="schwab",
        ...             timeout=timeout,
        ...         )
        ...
        ...     async def get_accounts(self, access_token: str):
        ...         return await self._execute_and_parse_list(
        ...             method="GET",
        ...             path="/accounts",
        ...             headers={"Authorization": f"Bearer {access_token}"},
        ...             operation="get_accounts",
        ...         )
    """

    def __init__(
        self,
        *,
        base_url: str,
        provider_name: str,
        timeout: float = PROVIDER_TIMEOUT_DEFAULT,
    ) -> None:
        """Initialize base provider API client.

        Args:
            base_url: Provider API base URL (e.g., "https://api.schwabapi.com/trader/v1").
            provider_name: Provider identifier (e.g., "schwab", "alpaca").
            timeout: HTTP request timeout in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._provider_name = provider_name
        self._timeout = timeout
        self._logger = structlog.get_logger(f"{provider_name}_api")

    async def _execute_request(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
        operation: str,
    ) -> Result[httpx.Response, ProviderError]:
        """Execute HTTP request with error handling.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: URL path relative to base_url.
            headers: HTTP headers including authentication.
            params: Optional query parameters.
            json_data: Optional JSON body for POST/PUT requests.
            operation: Operation name for logging.

        Returns:
            Success(httpx.Response): Raw HTTP response on success.
            Failure(ProviderUnavailableError): On timeout or connection error.
        """
        url = f"{self._base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                )
            return Success(value=response)

        except httpx.TimeoutException as e:
            self._logger.warning(
                f"{self._provider_name}_api_timeout",
                operation=operation,
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"{self._provider_name.title()} API request timed out",
                    provider_name=self._provider_name,
                    is_transient=True,
                )
            )

        except httpx.RequestError as e:
            self._logger.warning(
                f"{self._provider_name}_api_connection_error",
                operation=operation,
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Failed to connect to {self._provider_name.title()} API: {e}",
                    provider_name=self._provider_name,
                    is_transient=True,
                )
            )

    def _check_error_response(
        self,
        response: httpx.Response,
        operation: str,
    ) -> Failure[ProviderError] | None:
        """Check HTTP response for errors and return appropriate ProviderError.

        Args:
            response: HTTP response to check.
            operation: Operation name for logging.

        Returns:
            Failure(ProviderError) if error detected, None if response is OK.
        """
        status = response.status_code

        # Success - no error
        if status == 200:
            return None

        # Rate limiting (429)
        if status == 429:
            retry_after = response.headers.get("Retry-After")
            retry_seconds = int(retry_after) if retry_after else None
            self._logger.warning(
                f"{self._provider_name}_api_rate_limited",
                operation=operation,
                retry_after=retry_seconds,
            )
            return Failure(
                error=ProviderRateLimitError(
                    code=ErrorCode.PROVIDER_RATE_LIMITED,
                    message=f"{self._provider_name.title()} API rate limit exceeded",
                    provider_name=self._provider_name,
                    retry_after=retry_seconds,
                )
            )

        # Authentication errors (401)
        if status == 401:
            self._logger.warning(
                f"{self._provider_name}_api_auth_failed",
                operation=operation,
            )
            return Failure(
                error=ProviderAuthenticationError(
                    code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
                    message=f"{self._provider_name.title()} access token is invalid or expired",
                    provider_name=self._provider_name,
                    is_token_expired=True,
                )
            )

        # Forbidden (403)
        if status == 403:
            self._logger.warning(
                f"{self._provider_name}_api_forbidden",
                operation=operation,
            )
            return Failure(
                error=ProviderAuthenticationError(
                    code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
                    message=f"Access denied to {self._provider_name.title()} resource",
                    provider_name=self._provider_name,
                    is_token_expired=False,
                )
            )

        # Not found (404)
        if status == 404:
            self._logger.warning(
                f"{self._provider_name}_api_not_found",
                operation=operation,
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message=f"{self._provider_name.title()} resource not found",
                    provider_name=self._provider_name,
                    response_body=response.text[:RESPONSE_BODY_MAX_LENGTH],
                )
            )

        # Server errors (5xx)
        if status >= 500:
            self._logger.warning(
                f"{self._provider_name}_api_server_error",
                operation=operation,
                status_code=status,
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"{self._provider_name.title()} API server error: {status}",
                    provider_name=self._provider_name,
                    is_transient=True,
                )
            )

        # Unexpected status
        self._logger.warning(
            f"{self._provider_name}_api_unexpected_status",
            operation=operation,
            status_code=status,
        )
        return Failure(
            error=ProviderInvalidResponseError(
                code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                message=f"Unexpected response from {self._provider_name.title()}: {status}",
                provider_name=self._provider_name,
                response_body=response.text[:RESPONSE_BODY_MAX_LENGTH],
            )
        )

    def _parse_json_object(
        self,
        response: httpx.Response,
        operation: str,
    ) -> Result[dict[str, Any], ProviderError]:
        """Parse response as JSON object with error handling.

        Args:
            response: HTTP response to parse.
            operation: Operation name for logging.

        Returns:
            Success(dict): Parsed JSON object.
            Failure(ProviderError): On HTTP error or invalid JSON.
        """
        # Check for HTTP errors first
        error_result = self._check_error_response(response, operation)
        if error_result is not None:
            return error_result

        # Parse JSON
        try:
            data = response.json()
        except ValueError as e:
            self._logger.error(
                f"{self._provider_name}_api_invalid_json",
                operation=operation,
                error=str(e),
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message=f"Invalid JSON response from {self._provider_name.title()}",
                    provider_name=self._provider_name,
                    response_body=response.text[:RESPONSE_BODY_MAX_LENGTH],
                )
            )

        # Validate type
        if not isinstance(data, dict):
            self._logger.warning(
                f"{self._provider_name}_api_unexpected_format",
                operation=operation,
                data_type=type(data).__name__,
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message=f"Expected object response from {self._provider_name.title()}",
                    provider_name=self._provider_name,
                    response_body=response.text[:RESPONSE_BODY_MAX_LENGTH],
                )
            )

        self._logger.debug(
            f"{self._provider_name}_api_succeeded",
            operation=operation,
        )
        return Success(value=data)

    def _parse_json_list(
        self,
        response: httpx.Response,
        operation: str,
    ) -> Result[list[dict[str, Any]], ProviderError]:
        """Parse response as JSON list with error handling.

        Args:
            response: HTTP response to parse.
            operation: Operation name for logging.

        Returns:
            Success(list[dict]): Parsed JSON list.
            Failure(ProviderError): On HTTP error or invalid JSON.
        """
        # Check for HTTP errors first
        error_result = self._check_error_response(response, operation)
        if error_result is not None:
            return error_result

        # Parse JSON
        try:
            data = response.json()
        except ValueError as e:
            self._logger.error(
                f"{self._provider_name}_api_invalid_json",
                operation=operation,
                error=str(e),
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message=f"Invalid JSON response from {self._provider_name.title()}",
                    provider_name=self._provider_name,
                    response_body=response.text[:RESPONSE_BODY_MAX_LENGTH],
                )
            )

        # Handle non-list responses (some APIs return single object)
        if not isinstance(data, list):
            self._logger.warning(
                f"{self._provider_name}_api_unexpected_format",
                operation=operation,
                data_type=type(data).__name__,
            )
            data = [data] if data else []

        self._logger.debug(
            f"{self._provider_name}_api_succeeded",
            operation=operation,
            count=len(data),
        )
        return Success(value=data)

    async def _execute_and_parse_object(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
        operation: str,
    ) -> Result[dict[str, Any], ProviderError]:
        """Execute request and parse response as JSON object.

        Combines _execute_request and _parse_json_object for convenience.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: URL path relative to base_url.
            headers: HTTP headers including authentication.
            params: Optional query parameters.
            json_data: Optional JSON body for POST/PUT requests.
            operation: Operation name for logging.

        Returns:
            Success(dict): Parsed JSON object.
            Failure(ProviderError): On any error.
        """
        result = await self._execute_request(
            method=method,
            path=path,
            headers=headers,
            params=params,
            json_data=json_data,
            operation=operation,
        )

        if isinstance(result, Failure):
            return result

        return self._parse_json_object(result.value, operation)

    async def _execute_and_parse_list(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
        operation: str,
    ) -> Result[list[dict[str, Any]], ProviderError]:
        """Execute request and parse response as JSON list.

        Combines _execute_request and _parse_json_list for convenience.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: URL path relative to base_url.
            headers: HTTP headers including authentication.
            params: Optional query parameters.
            json_data: Optional JSON body for POST/PUT requests.
            operation: Operation name for logging.

        Returns:
            Success(list[dict]): Parsed JSON list.
            Failure(ProviderError): On any error.
        """
        result = await self._execute_request(
            method=method,
            path=path,
            headers=headers,
            params=params,
            json_data=json_data,
            operation=operation,
        )

        if isinstance(result, Failure):
            return result

        return self._parse_json_list(result.value, operation)
