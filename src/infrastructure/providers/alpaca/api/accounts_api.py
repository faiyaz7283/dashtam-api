"""Alpaca Accounts API client.

HTTP client for Alpaca Trading API account and positions endpoints.
Uses API Key authentication headers.

Endpoints:
    GET /v2/account - Get account information
    GET /v2/positions - Get all open positions

Reference:
    - https://docs.alpaca.markets/docs/trading-api
    - https://docs.alpaca.markets/reference/getaccount-1
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


class AlpacaAccountsAPI:
    """HTTP client for Alpaca Trading API account and positions endpoints.

    Uses API Key authentication (not OAuth Bearer tokens).
    Returns raw JSON responses - mapping to domain types is done by mappers.

    Attributes:
        base_url: Alpaca Trading API base URL (paper or live).
        timeout: HTTP request timeout in seconds.

    Example:
        >>> api = AlpacaAccountsAPI(
        ...     base_url="https://paper-api.alpaca.markets",
        ...     timeout=30.0,
        ... )
        >>> result = await api.get_account(api_key="...", api_secret="...")
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 30.0,
    ) -> None:
        """Initialize Alpaca Accounts API client.

        Args:
            base_url: Alpaca Trading API base URL.
            timeout: HTTP request timeout in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def get_account(
        self,
        api_key: str,
        api_secret: str,
    ) -> Result[dict[str, Any], ProviderError]:
        """Fetch account information.

        Args:
            api_key: Alpaca API Key ID.
            api_secret: Alpaca API Secret Key.

        Returns:
            Success(dict): Account JSON object from Alpaca.
            Failure(ProviderAuthenticationError): If credentials are invalid.
            Failure(ProviderUnavailableError): If Alpaca API is unreachable.
        """
        logger.debug("alpaca_accounts_api_get_account_started")

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/v2/account",
                    headers=self._build_headers(api_key, api_secret),
                )

            return self._handle_response(response, "get_account")

        except httpx.TimeoutException as e:
            logger.warning(
                "alpaca_accounts_api_timeout",
                operation="get_account",
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message="Alpaca API request timed out",
                    provider_name="alpaca",
                    is_transient=True,
                )
            )
        except httpx.RequestError as e:
            logger.warning(
                "alpaca_accounts_api_connection_error",
                operation="get_account",
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Failed to connect to Alpaca API: {e}",
                    provider_name="alpaca",
                    is_transient=True,
                )
            )

    async def get_positions(
        self,
        api_key: str,
        api_secret: str,
    ) -> Result[list[dict[str, Any]], ProviderError]:
        """Fetch all open positions.

        Args:
            api_key: Alpaca API Key ID.
            api_secret: Alpaca API Secret Key.

        Returns:
            Success(list[dict]): List of position JSON objects.
            Failure(ProviderAuthenticationError): If credentials are invalid.
            Failure(ProviderUnavailableError): If Alpaca API is unreachable.
        """
        logger.debug("alpaca_accounts_api_get_positions_started")

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/v2/positions",
                    headers=self._build_headers(api_key, api_secret),
                )

            return self._handle_list_response(response, "get_positions")

        except httpx.TimeoutException as e:
            logger.warning(
                "alpaca_accounts_api_timeout",
                operation="get_positions",
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message="Alpaca API request timed out",
                    provider_name="alpaca",
                    is_transient=True,
                )
            )
        except httpx.RequestError as e:
            logger.warning(
                "alpaca_accounts_api_connection_error",
                operation="get_positions",
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Failed to connect to Alpaca API: {e}",
                    provider_name="alpaca",
                    is_transient=True,
                )
            )

    def _build_headers(self, api_key: str, api_secret: str) -> dict[str, str]:
        """Build HTTP headers for Alpaca API requests.

        Args:
            api_key: Alpaca API Key ID.
            api_secret: Alpaca API Secret Key.

        Returns:
            Headers dict with API key authentication.
        """
        return {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
            "Accept": "application/json",
        }

    def _handle_response(
        self,
        response: httpx.Response,
        operation: str,
    ) -> Result[dict[str, Any], ProviderError]:
        """Handle Alpaca API response for single-object endpoints.

        Args:
            response: HTTP response from Alpaca.
            operation: Operation name for logging.

        Returns:
            Success(dict) or Failure(ProviderError).
        """
        error_result = self._check_error_response(response, operation)
        if error_result is not None:
            return error_result

        try:
            data = response.json()
        except ValueError as e:
            logger.error(
                "alpaca_accounts_api_invalid_json",
                operation=operation,
                error=str(e),
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message="Invalid JSON response from Alpaca",
                    provider_name="alpaca",
                    response_body=response.text[:500],
                )
            )

        if not isinstance(data, dict):
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message="Expected object response from Alpaca",
                    provider_name="alpaca",
                    response_body=response.text[:500],
                )
            )

        logger.debug("alpaca_accounts_api_succeeded", operation=operation)
        return Success(value=data)

    def _handle_list_response(
        self,
        response: httpx.Response,
        operation: str,
    ) -> Result[list[dict[str, Any]], ProviderError]:
        """Handle Alpaca API response for list endpoints.

        Args:
            response: HTTP response from Alpaca.
            operation: Operation name for logging.

        Returns:
            Success(list[dict]) or Failure(ProviderError).
        """
        error_result = self._check_error_response(response, operation)
        if error_result is not None:
            return error_result

        try:
            data = response.json()
        except ValueError as e:
            logger.error(
                "alpaca_accounts_api_invalid_json",
                operation=operation,
                error=str(e),
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message="Invalid JSON response from Alpaca",
                    provider_name="alpaca",
                    response_body=response.text[:500],
                )
            )

        if not isinstance(data, list):
            data = [data] if data else []

        logger.debug(
            "alpaca_accounts_api_succeeded",
            operation=operation,
            count=len(data),
        )
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
                "alpaca_accounts_api_rate_limited",
                operation=operation,
                retry_after=retry_seconds,
            )
            return Failure(
                error=ProviderRateLimitError(
                    code=ErrorCode.PROVIDER_RATE_LIMITED,
                    message="Alpaca API rate limit exceeded",
                    provider_name="alpaca",
                    retry_after=retry_seconds,
                )
            )

        # Authentication errors
        if response.status_code in (401, 403):
            logger.warning("alpaca_accounts_api_auth_failed", operation=operation)
            return Failure(
                error=ProviderAuthenticationError(
                    code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
                    message="Alpaca API credentials are invalid",
                    provider_name="alpaca",
                    is_token_expired=False,
                )
            )

        # Not found
        if response.status_code == 404:
            logger.warning("alpaca_accounts_api_not_found", operation=operation)
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message="Alpaca resource not found",
                    provider_name="alpaca",
                    response_body=response.text[:500],
                )
            )

        # Server errors
        if response.status_code >= 500:
            logger.warning(
                "alpaca_accounts_api_server_error",
                operation=operation,
                status_code=response.status_code,
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Alpaca API server error: {response.status_code}",
                    provider_name="alpaca",
                    is_transient=True,
                )
            )

        # Success
        if response.status_code == 200:
            return None

        # Unexpected status
        logger.warning(
            "alpaca_accounts_api_unexpected_status",
            operation=operation,
            status_code=response.status_code,
        )
        return Failure(
            error=ProviderInvalidResponseError(
                code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                message=f"Unexpected response from Alpaca: {response.status_code}",
                provider_name="alpaca",
                response_body=response.text[:500],
            )
        )
