"""Schwab Transactions API client.

HTTP client for Schwab Trader API transactions endpoints.
Handles HTTP concerns only - returns raw JSON responses.

Endpoints:
    GET /trader/v1/accounts/{accountNumber}/transactions - Get all transactions
    GET /trader/v1/accounts/{accountNumber}/transactions/{transactionId} - Get specific transaction

Reference:
    - Schwab Trader API: https://developer.schwab.com
    - docs/architecture/provider-integration-architecture.md
"""

from datetime import date
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


class SchwabTransactionsAPI:
    """HTTP client for Schwab Trader API transactions endpoints.

    Handles HTTP communication with Schwab's transactions API.
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
        >>> api = SchwabTransactionsAPI(
        ...     base_url="https://api.schwabapi.com/trader/v1",
        ...     timeout=30.0,
        ... )
        >>> result = await api.get_transactions(
        ...     access_token="...",
        ...     account_number="12345678",
        ...     start_date=date(2024, 1, 1),
        ... )
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 30.0,
    ) -> None:
        """Initialize Schwab Transactions API client.

        Args:
            base_url: Schwab Trader API base URL (e.g., "https://api.schwabapi.com/trader/v1").
            timeout: HTTP request timeout in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def get_transactions(
        self,
        access_token: str,
        account_number: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        transaction_type: str | None = None,
    ) -> Result[list[dict[str, Any]], ProviderError]:
        """Fetch transactions for a specific account.

        Args:
            access_token: Valid Schwab access token (Bearer token).
            account_number: Schwab account number.
            start_date: Beginning of date range (ISO format YYYY-MM-DD).
            end_date: End of date range (ISO format YYYY-MM-DD).
            transaction_type: Filter by transaction type (e.g., "TRADE", "DIVIDEND").

        Returns:
            Success(list[dict]): List of transaction JSON objects from Schwab.
            Failure(ProviderAuthenticationError): If token is invalid/expired.
            Failure(ProviderRateLimitError): If rate limit exceeded.
            Failure(ProviderUnavailableError): If Schwab API is unreachable.
            Failure(ProviderInvalidResponseError): If response is malformed.

        Example:
            >>> result = await api.get_transactions(
            ...     access_token,
            ...     "12345678",
            ...     start_date=date(2024, 1, 1),
            ...     end_date=date(2024, 12, 31),
            ... )
        """
        # Mask account number for logging
        masked_account = (
            f"****{account_number[-4:]}" if len(account_number) >= 4 else "****"
        )

        logger.debug(
            "schwab_transactions_api_get_transactions_started",
            account_number_masked=masked_account,
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
            transaction_type=transaction_type,
        )

        # Build query params
        params: dict[str, str] = {}
        if start_date:
            params["startDate"] = start_date.isoformat()
        if end_date:
            params["endDate"] = end_date.isoformat()
        if transaction_type:
            params["types"] = transaction_type

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/accounts/{account_number}/transactions",
                    headers=self._build_headers(access_token),
                    params=params if params else None,
                )

            return self._handle_response(response, "get_transactions")

        except httpx.TimeoutException as e:
            logger.warning(
                "schwab_transactions_api_timeout",
                operation="get_transactions",
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
                "schwab_transactions_api_connection_error",
                operation="get_transactions",
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

    async def get_transaction(
        self,
        access_token: str,
        account_number: str,
        transaction_id: str,
    ) -> Result[dict[str, Any], ProviderError]:
        """Fetch a specific transaction by ID.

        Args:
            access_token: Valid Schwab access token (Bearer token).
            account_number: Schwab account number.
            transaction_id: Schwab transaction ID.

        Returns:
            Success(dict): Single transaction JSON object from Schwab.
            Failure(ProviderAuthenticationError): If token is invalid/expired.
            Failure(ProviderRateLimitError): If rate limit exceeded.
            Failure(ProviderUnavailableError): If Schwab API is unreachable.
            Failure(ProviderInvalidResponseError): If response is malformed.

        Example:
            >>> result = await api.get_transaction(
            ...     access_token, "12345678", "txn_abc123"
            ... )
        """
        # Mask account number for logging
        masked_account = (
            f"****{account_number[-4:]}" if len(account_number) >= 4 else "****"
        )

        logger.debug(
            "schwab_transactions_api_get_transaction_started",
            account_number_masked=masked_account,
            transaction_id=transaction_id,
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/accounts/{account_number}/transactions/{transaction_id}",
                    headers=self._build_headers(access_token),
                )

            return self._handle_single_response(response, "get_transaction")

        except httpx.TimeoutException as e:
            logger.warning(
                "schwab_transactions_api_timeout",
                operation="get_transaction",
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
                "schwab_transactions_api_connection_error",
                operation="get_transaction",
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
                "schwab_transactions_api_invalid_json",
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
                "schwab_transactions_api_unexpected_format",
                operation=operation,
                data_type=type(data).__name__,
            )
            # Some endpoints return single object, wrap in list
            data = [data] if data else []

        logger.debug(
            "schwab_transactions_api_succeeded",
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
                "schwab_transactions_api_invalid_json",
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
                "schwab_transactions_api_unexpected_format",
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

        logger.debug("schwab_transactions_api_succeeded", operation=operation)

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
                "schwab_transactions_api_rate_limited",
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
            logger.warning("schwab_transactions_api_auth_failed", operation=operation)
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
            logger.warning("schwab_transactions_api_forbidden", operation=operation)
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
            logger.warning("schwab_transactions_api_not_found", operation=operation)
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
                "schwab_transactions_api_server_error",
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
            "schwab_transactions_api_unexpected_status",
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
