"""Alpaca Transactions API client.

HTTP client for Alpaca Trading API account activities endpoint.
Uses API Key authentication headers.

Endpoints:
    GET /v2/account/activities - Get account activities (Alpaca's term for transactions)

Activity Types:
    FILL - Order fill (trade execution)
    DIV - Dividend
    DIVCGL/DIVCGS/DIVNRA/DIVFT/DIVTXEX - Various dividend types
    INT - Interest
    JNLC - Journal entry (cash)
    JNLS - Journal entry (stock)
    MA - Merger/Acquisition
    NC - Name change
    PTC - Pass-through charge
    REO - Reorg fee
    SC - Symbol change
    SSO - Stock spinoff
    SSP - Stock split

Reference:
    - https://docs.alpaca.markets/reference/getaccountactivities-1
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


class AlpacaTransactionsAPI:
    """HTTP client for Alpaca Trading API transactions (activities) endpoint.

    Uses API Key authentication (not OAuth Bearer tokens).
    Returns raw JSON responses - mapping to domain types is done by mappers.

    Note: Alpaca calls transactions "activities" in their API.

    Attributes:
        base_url: Alpaca Trading API base URL (paper or live).
        timeout: HTTP request timeout in seconds.

    Example:
        >>> api = AlpacaTransactionsAPI(
        ...     base_url="https://paper-api.alpaca.markets",
        ...     timeout=30.0,
        ... )
        >>> result = await api.get_transactions(api_key="...", api_secret="...")
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 30.0,
    ) -> None:
        """Initialize Alpaca Activities API client.

        Args:
            base_url: Alpaca Trading API base URL.
            timeout: HTTP request timeout in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def get_transactions(
        self,
        api_key: str,
        api_secret: str,
        *,
        activity_types: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        page_size: int = 100,
    ) -> Result[list[dict[str, Any]], ProviderError]:
        """Fetch account transactions (called 'activities' in Alpaca API).

        Args:
            api_key: Alpaca API Key ID.
            api_secret: Alpaca API Secret Key.
            activity_types: Filter by Alpaca activity types (e.g., ["FILL", "DIV"]).
            start_date: Get transactions after this date.
            end_date: Get transactions until this date.
            page_size: Number of transactions per page (max 100).

        Returns:
            Success(list[dict]): List of transaction JSON objects.
            Failure(ProviderAuthenticationError): If credentials are invalid.
            Failure(ProviderUnavailableError): If Alpaca API is unreachable.
        """
        logger.debug(
            "alpaca_transactions_api_get_transactions_started",
            activity_types=activity_types,
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
        )

        # Build query parameters
        params: dict[str, Any] = {"page_size": page_size}
        if activity_types:
            params["activity_types"] = ",".join(activity_types)
        if start_date:
            params["after"] = start_date.isoformat()
        if end_date:
            params["until"] = end_date.isoformat()

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/v2/account/activities",
                    headers=self._build_headers(api_key, api_secret),
                    params=params,
                )

            return self._handle_response(response, "get_transactions")

        except httpx.TimeoutException as e:
            logger.warning(
                "alpaca_transactions_api_timeout",
                operation="get_transactions",
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
                "alpaca_transactions_api_connection_error",
                operation="get_transactions",
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
    ) -> Result[list[dict[str, Any]], ProviderError]:
        """Handle Alpaca API response for transactions endpoint.

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
                "alpaca_transactions_api_invalid_json",
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
            "alpaca_transactions_api_succeeded",
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
                "alpaca_transactions_api_rate_limited",
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
            logger.warning("alpaca_transactions_api_auth_failed", operation=operation)
            return Failure(
                error=ProviderAuthenticationError(
                    code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
                    message="Alpaca API credentials are invalid",
                    provider_name="alpaca",
                    is_token_expired=False,
                )
            )

        # Server errors
        if response.status_code >= 500:
            logger.warning(
                "alpaca_transactions_api_server_error",
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
            "alpaca_transactions_api_unexpected_status",
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
