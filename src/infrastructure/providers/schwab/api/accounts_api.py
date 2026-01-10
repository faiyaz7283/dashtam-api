"""Schwab Accounts API client.

HTTP client for Schwab Trader API accounts endpoints.
Handles HTTP concerns only - returns raw JSON responses.

Endpoints:
    GET /trader/v1/accounts - Get all linked accounts with balances/positions
    GET /trader/v1/accounts/{accountNumber} - Get specific account

Reference:
    - Schwab Trader API: https://developer.schwab.com
    - docs/architecture/provider-integration-architecture.md
"""

from typing import Any

import httpx
import structlog

from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success
from src.domain.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

logger = structlog.get_logger(__name__)


class SchwabAccountsAPI:
    """HTTP client for Schwab Trader API accounts endpoints.

    Handles HTTP communication with Schwab's accounts API.
    Returns raw JSON responses - mapping to domain types is done by mappers.

    This class is responsible for:
    - HTTP request construction (headers, auth, params)
    - Response status code handling
    - Error translation to ProviderError types
    - Timeout and connection error handling

    Thread-safe: Uses httpx.AsyncClient per-request (no shared state).

    Attributes:
        base_url: Schwab Trader API base URL.
        timeout: HTTP request timeout in seconds.

    Example:
        >>> api = SchwabAccountsAPI(
        ...     base_url="https://api.schwabapi.com/trader/v1",
        ...     timeout=30.0,
        ... )
        >>> result = await api.get_accounts(access_token="...")
        >>> match result:
        ...     case Success(data):
        ...         print(f"Got {len(data)} accounts")
        ...     case Failure(error):
        ...         print(f"Error: {error.message}")
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 30.0,
    ) -> None:
        """Initialize Schwab Accounts API client.

        Args:
            base_url: Schwab Trader API base URL (e.g., "https://api.schwabapi.com/trader/v1").
            timeout: HTTP request timeout in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def get_accounts(
        self,
        access_token: str,
        *,
        include_positions: bool = False,
    ) -> Result[list[dict[str, Any]], ProviderError]:
        """Fetch all accounts for the authenticated user.

        Args:
            access_token: Valid Schwab access token (Bearer token).
            include_positions: Include position details in response.

        Returns:
            Success(list[dict]): List of account JSON objects from Schwab.
            Failure(ProviderAuthenticationError): If token is invalid/expired.
            Failure(ProviderRateLimitError): If rate limit exceeded.
            Failure(ProviderUnavailableError): If Schwab API is unreachable.
            Failure(ProviderInvalidResponseError): If response is malformed.

        Example:
            >>> result = await api.get_accounts(access_token)
            >>> match result:
            ...     case Success(accounts):
            ...         for account in accounts:
            ...             print(account["securitiesAccount"][`"accountNumber"`])
        """
        logger.debug(
            "schwab_accounts_api_get_accounts_started",
            include_positions=include_positions,
        )

        # Build query params
        params: dict[str, str] = {}
        if include_positions:
            params["fields"] = "positions"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/accounts",
                    headers=self._build_headers(access_token),
                    params=params if params else None,
                )

            return self._handle_response(response, "get_accounts")

        except httpx.TimeoutException as e:
            logger.warning(
                "schwab_accounts_api_timeout",
                operation="get_accounts",
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message="Schwab API request timed out",
                    provider_name="schwab",
                    is_transient=True,
                )
            )
        except httpx.RequestError as e:
            logger.warning(
                "schwab_accounts_api_connection_error",
                operation="get_accounts",
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Failed to connect to Schwab API: {e}",
                    provider_name="schwab",
                    is_transient=True,
                )
            )

    async def get_account(
        self,
        access_token: str,
        account_number: str,
        *,
        include_positions: bool = False,
    ) -> Result[dict[str, Any], ProviderError]:
        """Fetch a specific account by account number.

        Args:
            access_token: Valid Schwab access token (Bearer token).
            account_number: Schwab account number to fetch.
            include_positions: Include position details in response.

        Returns:
            Success(dict): Single account JSON object from Schwab.
            Failure(ProviderAuthenticationError): If token is invalid/expired.
            Failure(ProviderRateLimitError): If rate limit exceeded.
            Failure(ProviderUnavailableError): If Schwab API is unreachable.
            Failure(ProviderInvalidResponseError): If response is malformed.

        Example:
            >>> result = await api.get_account(access_token, "12345678")
            >>> match result:
            ...     case Success(account):
            ...         print(account["securitiesAccount"][`"accountName"`])
        """
        logger.debug(
            "schwab_accounts_api_get_account_started",
            account_number_masked=f"****{account_number[-4:]}"
            if len(account_number) >= 4
            else "****",
            include_positions=include_positions,
        )

        # Build query params
        params: dict[str, str] = {}
        if include_positions:
            params["fields"] = "positions"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/accounts/{account_number}",
                    headers=self._build_headers(access_token),
                    params=params if params else None,
                )

            # Single account response handling
            return self._handle_single_response(response, "get_account")

        except httpx.TimeoutException as e:
            logger.warning(
                "schwab_accounts_api_timeout",
                operation="get_account",
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message="Schwab API request timed out",
                    provider_name="schwab",
                    is_transient=True,
                )
            )
        except httpx.RequestError as e:
            logger.warning(
                "schwab_accounts_api_connection_error",
                operation="get_account",
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Failed to connect to Schwab API: {e}",
                    provider_name="schwab",
                    is_transient=True,
                )
            )

    def _build_headers(self, access_token: str) -> dict[str, str]:
        """Build HTTP headers for Schwab API requests.

        Args:
            access_token: Bearer token for authentication.

        Returns:
            Headers dict with Authorization and Accept.
        """
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    def _handle_response(
        self,
        response: httpx.Response,
        operation: str,
    ) -> Result[list[dict[str, Any]], ProviderError]:
        """Handle Schwab API response for list endpoints.

        Args:
            response: HTTP response from Schwab.
            operation: Operation name for logging.

        Returns:
            Success(list[dict]) or Failure(ProviderError).
        """
        # Check for errors first
        error_result = self._check_error_response(response, operation)
        if error_result is not None:
            return error_result

        # Parse JSON
        try:
            data = response.json()
        except ValueError as e:
            logger.error(
                "schwab_accounts_api_invalid_json",
                operation=operation,
                error=str(e),
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message="Invalid JSON response from Schwab",
                    provider_name="schwab",
                    response_body=response.text[:500],
                )
            )

        # Ensure we have a list
        if not isinstance(data, list):
            logger.warning(
                "schwab_accounts_api_unexpected_format",
                operation=operation,
                data_type=type(data).__name__,
            )
            # Some endpoints return single object, wrap in list
            data = [data] if data else []

        logger.debug(
            "schwab_accounts_api_succeeded",
            operation=operation,
            count=len(data),
        )

        return Success(value=data)

    def _handle_single_response(
        self,
        response: httpx.Response,
        operation: str,
    ) -> Result[dict[str, Any], ProviderError]:
        """Handle Schwab API response for single-item endpoints.

        Args:
            response: HTTP response from Schwab.
            operation: Operation name for logging.

        Returns:
            Success(dict) or Failure(ProviderError).
        """
        # Check for errors first
        error_result = self._check_error_response(response, operation)
        if error_result is not None:
            return error_result

        # Parse JSON
        try:
            data = response.json()
        except ValueError as e:
            logger.error(
                "schwab_accounts_api_invalid_json",
                operation=operation,
                error=str(e),
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message="Invalid JSON response from Schwab",
                    provider_name="schwab",
                    response_body=response.text[:500],
                )
            )

        if not isinstance(data, dict):
            logger.warning(
                "schwab_accounts_api_unexpected_format",
                operation=operation,
                data_type=type(data).__name__,
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message="Expected object response from Schwab",
                    provider_name="schwab",
                    response_body=response.text[:500],
                )
            )

        logger.debug("schwab_accounts_api_succeeded", operation=operation)

        return Success(value=data)

    def _check_error_response(
        self,
        response: httpx.Response,
        operation: str,
    ) -> Failure[ProviderError] | None:
        """Check for error status codes and return appropriate error.

        Args:
            response: HTTP response to check.
            operation: Operation name for logging.

        Returns:
            Failure result if error detected, None if response is OK.
        """
        # Rate limiting
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            retry_seconds = int(retry_after) if retry_after else None
            logger.warning(
                "schwab_accounts_api_rate_limited",
                operation=operation,
                retry_after=retry_seconds,
            )
            return Failure(
                error=ProviderRateLimitError(
                    code=ErrorCode.PROVIDER_RATE_LIMITED,
                    message="Schwab API rate limit exceeded",
                    provider_name="schwab",
                    retry_after=retry_seconds,
                )
            )

        # Authentication errors
        if response.status_code == 401:
            logger.warning("schwab_accounts_api_auth_failed", operation=operation)
            return Failure(
                error=ProviderAuthenticationError(
                    code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
                    message="Schwab access token is invalid or expired",
                    provider_name="schwab",
                    is_token_expired=True,
                )
            )

        # Forbidden (authorization)
        if response.status_code == 403:
            logger.warning("schwab_accounts_api_forbidden", operation=operation)
            return Failure(
                error=ProviderAuthenticationError(
                    code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
                    message="Access denied to Schwab resource",
                    provider_name="schwab",
                    is_token_expired=False,
                )
            )

        # Not found
        if response.status_code == 404:
            logger.warning("schwab_accounts_api_not_found", operation=operation)
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message="Schwab resource not found",
                    provider_name="schwab",
                    response_body=response.text[:500],
                )
            )

        # Server errors
        if response.status_code >= 500:
            logger.warning(
                "schwab_accounts_api_server_error",
                operation=operation,
                status_code=response.status_code,
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Schwab API server error: {response.status_code}",
                    provider_name="schwab",
                    is_transient=True,
                )
            )

        # Success
        if response.status_code == 200:
            return None

        # Unexpected status
        logger.warning(
            "schwab_accounts_api_unexpected_status",
            operation=operation,
            status_code=response.status_code,
        )
        return Failure(
            error=ProviderInvalidResponseError(
                code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                message=f"Unexpected response from Schwab: {response.status_code}",
                provider_name="schwab",
                response_body=response.text[:500],
            )
        )
