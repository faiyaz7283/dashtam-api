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

from src.core.constants import BEARER_PREFIX, PROVIDER_TIMEOUT_DEFAULT
from src.core.result import Result
from src.domain.errors import ProviderError
from src.infrastructure.providers.base_api_client import BaseProviderAPIClient


class SchwabTransactionsAPI(BaseProviderAPIClient):
    """HTTP client for Schwab Trader API transactions endpoints.

    Extends BaseProviderAPIClient with Schwab-specific authentication.
    Returns raw JSON responses - mapping to domain types is done by mappers.

    Thread-safe: Uses httpx.AsyncClient per-request (no shared state).

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
        timeout: float = PROVIDER_TIMEOUT_DEFAULT,
    ) -> None:
        """Initialize Schwab Transactions API client.

        Args:
            base_url: Schwab Trader API base URL (e.g., "https://api.schwabapi.com/trader/v1").
            timeout: HTTP request timeout in seconds.
        """
        super().__init__(
            base_url=base_url,
            provider_name="schwab",
            timeout=timeout,
        )

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
        """
        masked_account = (
            f"****{account_number[-4:]}" if len(account_number) >= 4 else "****"
        )

        self._logger.debug(
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

        return await self._execute_and_parse_list(
            method="GET",
            path=f"/accounts/{account_number}/transactions",
            headers=self._build_headers(access_token),
            params=params if params else None,
            operation="get_transactions",
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
        """
        masked_account = (
            f"****{account_number[-4:]}" if len(account_number) >= 4 else "****"
        )

        self._logger.debug(
            "schwab_transactions_api_get_transaction_started",
            account_number_masked=masked_account,
            transaction_id=transaction_id,
        )

        return await self._execute_and_parse_object(
            method="GET",
            path=f"/accounts/{account_number}/transactions/{transaction_id}",
            headers=self._build_headers(access_token),
            operation="get_transaction",
        )

    def _build_headers(self, access_token: str) -> dict[str, str]:
        """Build HTTP headers for Schwab API requests.

        Args:
            access_token: Bearer token for authentication.

        Returns:
            Headers dict with Authorization and Accept.
        """
        return {
            "Authorization": f"{BEARER_PREFIX}{access_token}",
            "Accept": "application/json",
        }
