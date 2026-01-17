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

from src.core.constants import PROVIDER_TIMEOUT_DEFAULT
from src.core.result import Result
from src.domain.errors import ProviderError
from src.infrastructure.providers.base_api_client import BaseProviderAPIClient


class AlpacaTransactionsAPI(BaseProviderAPIClient):
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
        timeout: float = PROVIDER_TIMEOUT_DEFAULT,
    ) -> None:
        """Initialize Alpaca Activities API client.

        Args:
            base_url: Alpaca Trading API base URL.
            timeout: HTTP request timeout in seconds.
        """
        super().__init__(
            base_url=base_url,
            provider_name="alpaca",
            timeout=timeout,
        )

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
        self._logger.debug(
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

        headers = self._build_alpaca_headers(api_key, api_secret)

        return await self._execute_and_parse_list(
            method="GET",
            path="/v2/account/activities",
            headers=headers,
            params=params,
            operation="get_transactions",
        )

    def _build_alpaca_headers(self, api_key: str, api_secret: str) -> dict[str, str]:
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
