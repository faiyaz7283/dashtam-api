"""Alpaca provider implementing ProviderProtocol.

Handles API Key authentication and Trading API calls for accounts/transactions/holdings.

Configuration loaded from settings (src/core/config.py):
    - alpaca_client_id: API Key ID (APCA-API-KEY-ID)
    - alpaca_client_secret: API Secret Key (APCA-API-SECRET-KEY)
    - alpaca_api_base_url: API base URL (paper or live)

Alpaca API Documentation:
    - Trading API: https://docs.alpaca.markets/docs/trading-api
    - Authentication: https://docs.alpaca.markets/docs/using-oauth2-and-trading-api

Architecture:
    AlpacaProvider orchestrates:
    - api/accounts_api.py: HTTP client for account and positions endpoints
    - api/transactions_api.py: HTTP client for activities endpoint
    - mappers/account_mapper.py: JSON → ProviderAccountData
    - mappers/holding_mapper.py: JSON → ProviderHoldingData
    - mappers/transaction_mapper.py: JSON → ProviderTransactionData

Authentication Difference from Schwab:
    - Schwab: OAuth 2.0 with token exchange/refresh
    - Alpaca: API Key authentication (persistent credentials)

    For Alpaca, credentials are stored encrypted in provider_connections.credentials
    and used directly for API calls (no token refresh needed).

Reference:
    - docs/architecture/provider-integration-architecture.md
"""

from datetime import date
from typing import Any

import structlog

from src.core.config import Settings
from src.core.result import Failure, Result, Success
from src.domain.errors import ProviderError
from src.domain.protocols.cache_protocol import CacheProtocol
from src.domain.protocols.provider_protocol import (
    ProviderAccountData,
    ProviderHoldingData,
    ProviderTransactionData,
)
from src.infrastructure.cache.cache_keys import CacheKeys
from src.infrastructure.cache.cache_metrics import CacheMetrics
from src.infrastructure.providers.alpaca.api.accounts_api import AlpacaAccountsAPI
from src.infrastructure.providers.alpaca.api.transactions_api import (
    AlpacaTransactionsAPI,
)
from src.infrastructure.providers.alpaca.mappers.account_mapper import (
    AlpacaAccountMapper,
)
from src.infrastructure.providers.alpaca.mappers.holding_mapper import (
    AlpacaHoldingMapper,
)
from src.infrastructure.providers.alpaca.mappers.transaction_mapper import (
    AlpacaTransactionMapper,
)

logger = structlog.get_logger(__name__)


class AlpacaProvider:
    """Alpaca provider adapter implementing ProviderProtocol.

    Handles API Key authentication and Trading API integration for Alpaca.
    Configuration is loaded from application settings.

    Key Differences from OAuth Providers (Schwab):
    - Uses API Key authentication (not OAuth Bearer tokens)
    - No token exchange or refresh needed
    - Credentials (api_key, api_secret) are passed to each API call
    - Single account per API key (not multiple accounts)

    Attributes:
        settings: Application settings containing Alpaca credentials.
        timeout: HTTP request timeout in seconds.

    Example:
        >>> from src.core.config import settings
        >>> provider = AlpacaProvider(settings=settings)
        >>> credentials = {"api_key": "PKXXXX", "api_secret": "secret123"}
        >>> result = await provider.fetch_accounts(credentials)
        >>> match result:
        ...     case Success(accounts):
        ...         print(f"Found {len(accounts)} account(s)")
        ...     case Failure(error):
        ...         print(f"Failed: {error.message}")
    """

    def __init__(
        self,
        *,
        settings: Settings,
        cache: CacheProtocol | None = None,
        cache_keys: CacheKeys | None = None,
        cache_metrics: CacheMetrics | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize Alpaca provider.

        Args:
            settings: Application settings with Alpaca configuration.
            cache: Optional cache for API response caching.
            cache_keys: Optional cache key utility.
            cache_metrics: Optional metrics tracker.
            timeout: HTTP request timeout in seconds.
        """
        self._settings = settings
        self._timeout = timeout
        self._cache = cache
        self._cache_keys = cache_keys
        self._cache_metrics = cache_metrics

        # Get base URL from settings
        self._base_url = settings.alpaca_api_base_url

        # Initialize API clients and mappers
        self._accounts_api = AlpacaAccountsAPI(
            base_url=self._base_url,
            timeout=timeout,
        )
        self._transactions_api = AlpacaTransactionsAPI(
            base_url=self._base_url,
            timeout=timeout,
        )
        self._account_mapper = AlpacaAccountMapper()
        self._holding_mapper = AlpacaHoldingMapper()
        self._transaction_mapper = AlpacaTransactionMapper()

    @property
    def slug(self) -> str:
        """Return provider slug identifier."""
        return "alpaca"

    async def fetch_accounts(
        self,
        credentials: dict[str, Any],
    ) -> Result[list[ProviderAccountData], ProviderError]:
        """Fetch all accounts for the authenticated user.

        Alpaca has a single account per API key, unlike Schwab which has
        multiple accounts per user.

        Args:
            credentials: Decrypted credentials dict containing:
                - api_key: Alpaca API Key ID
                - api_secret: Alpaca API Secret Key

        Returns:
            Success(list[ProviderAccountData]): Single account wrapped in list.
            Failure(ProviderAuthenticationError): If credentials are invalid.
            Failure(ProviderUnavailableError): If Alpaca API is unreachable.
        """
        # Extract API credentials from dict
        api_key = credentials.get("api_key", "")
        api_secret = credentials.get("api_secret", "")

        logger.info(
            "alpaca_fetch_accounts_started",
            provider=self.slug,
        )

        # Fetch account data from Alpaca API
        result = await self._accounts_api.get_account(
            api_key=api_key,
            api_secret=api_secret,
        )

        # Handle API errors
        if isinstance(result, Failure):
            return Failure(error=result.error)

        raw_account = result.value

        # Map raw JSON to ProviderAccountData
        account = self._account_mapper.map_account(raw_account)
        if account is None:
            logger.warning(
                "alpaca_fetch_accounts_mapping_failed",
                provider=self.slug,
            )
            return Success(value=[])

        logger.info(
            "alpaca_fetch_accounts_succeeded",
            provider=self.slug,
            account_count=1,
        )

        return Success(value=[account])

    async def fetch_transactions(
        self,
        credentials: dict[str, Any],
        provider_account_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Result[list[ProviderTransactionData], ProviderError]:
        """Fetch transactions (activities) for the account.

        Alpaca calls transactions "activities" in their API. This method
        fetches all account activities and maps them to Dashtam transactions.

        Note: provider_account_id is required by the protocol but not used by
        Alpaca since each API key maps to a single account.

        Args:
            credentials: Decrypted credentials dict containing:
                - api_key: Alpaca API Key ID
                - api_secret: Alpaca API Secret Key
            provider_account_id: Required by protocol but not used (single account).
            start_date: Beginning of date range.
            end_date: End of date range.

        Returns:
            Success(list[ProviderTransactionData]): Transaction data from Alpaca.
            Failure(ProviderAuthenticationError): If credentials are invalid.
            Failure(ProviderUnavailableError): If Alpaca API is unreachable.
        """
        # Extract API credentials from dict
        api_key = credentials.get("api_key", "")
        api_secret = credentials.get("api_secret", "")

        logger.info(
            "alpaca_fetch_transactions_started",
            provider=self.slug,
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
        )

        # Fetch activities from Alpaca API
        result = await self._transactions_api.get_transactions(
            api_key=api_key,
            api_secret=api_secret,
            start_date=start_date,
            end_date=end_date,
        )

        # Handle API errors
        if isinstance(result, Failure):
            return Failure(error=result.error)

        raw_activities = result.value

        # Map raw JSON to ProviderTransactionData
        transactions = self._transaction_mapper.map_transactions(raw_activities)

        logger.info(
            "alpaca_fetch_transactions_succeeded",
            provider=self.slug,
            transaction_count=len(transactions),
        )

        return Success(value=transactions)

    async def fetch_holdings(
        self,
        credentials: dict[str, Any],
        provider_account_id: str,
    ) -> Result[list[ProviderHoldingData], ProviderError]:
        """Fetch holdings (positions) for the account.

        Note: provider_account_id is required by the protocol but not used by
        Alpaca since each API key maps to a single account.

        Args:
            credentials: Decrypted credentials dict containing:
                - api_key: Alpaca API Key ID
                - api_secret: Alpaca API Secret Key
            provider_account_id: Required by protocol but not used (single account).

        Returns:
            Success(list[ProviderHoldingData]): Holding data from Alpaca.
            Failure(ProviderAuthenticationError): If credentials are invalid.
            Failure(ProviderUnavailableError): If Alpaca API is unreachable.
        """
        # Extract API credentials from dict
        api_key = credentials.get("api_key", "")
        api_secret = credentials.get("api_secret", "")

        logger.info(
            "alpaca_fetch_holdings_started",
            provider=self.slug,
        )

        # Fetch positions from Alpaca API
        result = await self._accounts_api.get_positions(
            api_key=api_key,
            api_secret=api_secret,
        )

        # Handle API errors
        if isinstance(result, Failure):
            return Failure(error=result.error)

        raw_positions = result.value

        # Map raw JSON to ProviderHoldingData
        holdings = self._holding_mapper.map_holdings(raw_positions)

        logger.info(
            "alpaca_fetch_holdings_succeeded",
            provider=self.slug,
            holding_count=len(holdings),
        )

        return Success(value=holdings)

    async def validate_credentials(
        self,
        credentials: dict[str, Any],
    ) -> Result[bool, ProviderError]:
        """Validate API credentials by making a test API call.

        Useful for verifying credentials during provider connection setup.

        Args:
            credentials: Decrypted credentials dict containing:
                - api_key: Alpaca API Key ID
                - api_secret: Alpaca API Secret Key

        Returns:
            Success(True): If credentials are valid.
            Failure(ProviderAuthenticationError): If credentials are invalid.
            Failure(ProviderUnavailableError): If Alpaca API is unreachable.
        """
        # Extract API credentials from dict
        api_key = credentials.get("api_key", "")
        api_secret = credentials.get("api_secret", "")

        logger.info(
            "alpaca_validate_credentials_started",
            provider=self.slug,
        )

        # Use get_account as a lightweight validation call
        result = await self._accounts_api.get_account(
            api_key=api_key,
            api_secret=api_secret,
        )

        if isinstance(result, Failure):
            logger.warning(
                "alpaca_validate_credentials_failed",
                provider=self.slug,
                error=result.error.message,
            )
            return Failure(error=result.error)

        logger.info(
            "alpaca_validate_credentials_succeeded",
            provider=self.slug,
        )

        return Success(value=True)
