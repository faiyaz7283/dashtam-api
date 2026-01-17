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

from src.core.constants import BEARER_PREFIX, PROVIDER_TIMEOUT_DEFAULT
from src.core.result import Result
from src.domain.errors import ProviderError
from src.infrastructure.providers.base_api_client import BaseProviderAPIClient


class SchwabAccountsAPI(BaseProviderAPIClient):
    """HTTP client for Schwab Trader API accounts endpoints.

    Extends BaseProviderAPIClient with Schwab-specific authentication.
    Returns raw JSON responses - mapping to domain types is done by mappers.

    Thread-safe: Uses httpx.AsyncClient per-request (no shared state).

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
        timeout: float = PROVIDER_TIMEOUT_DEFAULT,
    ) -> None:
        """Initialize Schwab Accounts API client.

        Args:
            base_url: Schwab Trader API base URL (e.g., "https://api.schwabapi.com/trader/v1").
            timeout: HTTP request timeout in seconds.
        """
        super().__init__(
            base_url=base_url,
            provider_name="schwab",
            timeout=timeout,
        )

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
        """
        self._logger.debug(
            "schwab_accounts_api_get_accounts_started",
            include_positions=include_positions,
        )

        params: dict[str, str] | None = (
            {"fields": "positions"} if include_positions else None
        )

        return await self._execute_and_parse_list(
            method="GET",
            path="/accounts",
            headers=self._build_headers(access_token),
            params=params,
            operation="get_accounts",
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
        """
        self._logger.debug(
            "schwab_accounts_api_get_account_started",
            account_number_masked=f"****{account_number[-4:]}"
            if len(account_number) >= 4
            else "****",
            include_positions=include_positions,
        )

        params: dict[str, str] | None = (
            {"fields": "positions"} if include_positions else None
        )

        return await self._execute_and_parse_object(
            method="GET",
            path=f"/accounts/{account_number}",
            headers=self._build_headers(access_token),
            params=params,
            operation="get_account",
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
