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

from src.core.constants import PROVIDER_TIMEOUT_DEFAULT
from src.core.result import Result
from src.domain.errors import ProviderError
from src.infrastructure.providers.base_api_client import BaseProviderAPIClient


class AlpacaAccountsAPI(BaseProviderAPIClient):
    """HTTP client for Alpaca Trading API account and positions endpoints.

    Extends BaseProviderAPIClient with Alpaca API Key authentication.
    Returns raw JSON responses - mapping to domain types is done by mappers.

    Thread-safe: Uses httpx.AsyncClient per-request (no shared state).

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
        timeout: float = PROVIDER_TIMEOUT_DEFAULT,
    ) -> None:
        """Initialize Alpaca Accounts API client.

        Args:
            base_url: Alpaca Trading API base URL.
            timeout: HTTP request timeout in seconds.
        """
        super().__init__(
            base_url=base_url,
            provider_name="alpaca",
            timeout=timeout,
        )

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
        self._logger.debug("alpaca_accounts_api_get_account_started")

        return await self._execute_and_parse_object(
            method="GET",
            path="/v2/account",
            headers=self._build_headers(api_key, api_secret),
            operation="get_account",
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
        self._logger.debug("alpaca_accounts_api_get_positions_started")

        return await self._execute_and_parse_list(
            method="GET",
            path="/v2/positions",
            headers=self._build_headers(api_key, api_secret),
            operation="get_positions",
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
