"""Schwab provider implementing ProviderProtocol.

Handles OAuth token exchange/refresh and Trader API calls for accounts/transactions.

Configuration loaded from settings (src/core/config.py):
    - schwab_api_key: OAuth client ID
    - schwab_api_secret: OAuth client secret
    - schwab_api_base_url: API base URL
    - schwab_redirect_uri: OAuth callback URL

Schwab API Documentation:
    - OAuth: https://developer.schwab.com/products/trader-api--individual/details/documentation/Retail%20Trader%20API%20Production
    - Trader API: https://api.schwabapi.com/trader/v1

Reference:
    - docs/architecture/provider-integration-architecture.md
    - docs/architecture/provider-oauth-architecture.md
"""

import base64
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
import structlog

from src.core.config import Settings
from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success
from src.domain.protocols.provider_protocol import (
    OAuthTokens,
    ProviderAccountData,
    ProviderTransactionData,
)
from src.infrastructure.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

logger = structlog.get_logger(__name__)


class SchwabProvider:
    """Schwab provider adapter implementing ProviderProtocol.

    Handles OAuth authentication and Trader API integration for Charles Schwab.
    Configuration is loaded from application settings.

    Attributes:
        settings: Application settings containing Schwab credentials.
        timeout: HTTP request timeout in seconds.

    Example:
        >>> from src.core.config import settings
        >>> provider = SchwabProvider(settings=settings)
        >>> result = await provider.exchange_code_for_tokens(auth_code)
        >>> match result:
        ...     case Success(tokens):
        ...         print(f"Access token expires in {tokens.expires_in}s")
        ...     case Failure(error):
        ...         print(f"Failed: {error.message}")
    """

    def __init__(
        self,
        *,
        settings: Settings,
        timeout: float = 30.0,
    ) -> None:
        """Initialize Schwab provider.

        Args:
            settings: Application settings with Schwab configuration.
            timeout: HTTP request timeout in seconds.

        Raises:
            ValueError: If required Schwab settings are not configured.
        """
        if not settings.schwab_api_key:
            raise ValueError("schwab_api_key is required in settings")
        if not settings.schwab_api_secret:
            raise ValueError("schwab_api_secret is required in settings")
        if not settings.schwab_redirect_uri:
            raise ValueError("schwab_redirect_uri is required in settings")

        self._settings = settings
        self._timeout = timeout

    @property
    def slug(self) -> str:
        """Return provider slug identifier."""
        return "schwab"

    @property
    def _token_url(self) -> str:
        """OAuth token endpoint URL."""
        return f"{self._settings.schwab_api_base_url}/v1/oauth/token"

    @property
    def _trader_api_base(self) -> str:
        """Trader API base URL."""
        return f"{self._settings.schwab_api_base_url}/trader/v1"

    def _get_basic_auth_header(self) -> str:
        """Generate Basic Auth header for OAuth token requests.

        Schwab requires Base64-encoded client_id:client_secret for token requests.

        Returns:
            Basic auth header value.
        """
        credentials = (
            f"{self._settings.schwab_api_key}:{self._settings.schwab_api_secret}"
        )
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def exchange_code_for_tokens(
        self,
        authorization_code: str,
    ) -> Result[OAuthTokens, ProviderError]:
        """Exchange OAuth authorization code for access and refresh tokens.

        Called after user completes Schwab OAuth consent flow.

        Args:
            authorization_code: Code from OAuth callback query parameter.

        Returns:
            Success(OAuthTokens): With access_token, refresh_token, and expiration.
            Failure(ProviderAuthenticationError): If code is invalid or expired.
            Failure(ProviderUnavailableError): If Schwab API is unreachable.
        """
        logger.info(
            "schwab_token_exchange_started",
            provider=self.slug,
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._token_url,
                    headers={
                        "Authorization": self._get_basic_auth_header(),
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={
                        "grant_type": "authorization_code",
                        "code": authorization_code,
                        "redirect_uri": self._settings.schwab_redirect_uri,
                    },
                )

            return self._handle_token_response(response, "exchange")

        except httpx.TimeoutException as e:
            logger.warning(
                "schwab_token_exchange_timeout",
                provider=self.slug,
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message="Schwab API request timed out",
                    provider_name=self.slug,
                    is_transient=True,
                )
            )
        except httpx.RequestError as e:
            logger.warning(
                "schwab_token_exchange_connection_error",
                provider=self.slug,
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Failed to connect to Schwab API: {e}",
                    provider_name=self.slug,
                    is_transient=True,
                )
            )

    async def refresh_access_token(
        self,
        refresh_token: str,
    ) -> Result[OAuthTokens, ProviderError]:
        """Refresh access token using refresh token.

        Schwab rotates refresh tokens on each refresh (7-day validity).

        Args:
            refresh_token: Current refresh token.

        Returns:
            Success(OAuthTokens): With new access_token and rotated refresh_token.
            Failure(ProviderAuthenticationError): If refresh token is invalid/expired.
            Failure(ProviderUnavailableError): If Schwab API is unreachable.
        """
        logger.info(
            "schwab_token_refresh_started",
            provider=self.slug,
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._token_url,
                    headers={
                        "Authorization": self._get_basic_auth_header(),
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    },
                )

            return self._handle_token_response(response, "refresh")

        except httpx.TimeoutException as e:
            logger.warning(
                "schwab_token_refresh_timeout",
                provider=self.slug,
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message="Schwab API request timed out",
                    provider_name=self.slug,
                    is_transient=True,
                )
            )
        except httpx.RequestError as e:
            logger.warning(
                "schwab_token_refresh_connection_error",
                provider=self.slug,
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Failed to connect to Schwab API: {e}",
                    provider_name=self.slug,
                    is_transient=True,
                )
            )

    def _handle_token_response(
        self,
        response: httpx.Response,
        operation: str,
    ) -> Result[OAuthTokens, ProviderError]:
        """Handle Schwab OAuth token response.

        Args:
            response: HTTP response from token endpoint.
            operation: "exchange" or "refresh" for logging.

        Returns:
            Success(OAuthTokens) or Failure(ProviderError).
        """
        # Handle rate limiting
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            retry_seconds = int(retry_after) if retry_after else None
            logger.warning(
                f"schwab_token_{operation}_rate_limited",
                provider=self.slug,
                retry_after=retry_seconds,
            )
            return Failure(
                error=ProviderRateLimitError(
                    code=ErrorCode.PROVIDER_RATE_LIMITED,
                    message="Schwab API rate limit exceeded",
                    provider_name=self.slug,
                    retry_after=retry_seconds,
                )
            )

        # Handle authentication errors (4xx)
        if response.status_code in (400, 401):
            logger.warning(
                f"schwab_token_{operation}_auth_failed",
                provider=self.slug,
                status_code=response.status_code,
            )
            # Check if it's an expired token
            is_expired = "expired" in response.text.lower()
            return Failure(
                error=ProviderAuthenticationError(
                    code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
                    message=f"Schwab authentication failed: {response.text}",
                    provider_name=self.slug,
                    is_token_expired=is_expired,
                )
            )

        # Handle server errors (5xx)
        if response.status_code >= 500:
            logger.warning(
                f"schwab_token_{operation}_server_error",
                provider=self.slug,
                status_code=response.status_code,
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Schwab API server error: {response.status_code}",
                    provider_name=self.slug,
                    is_transient=True,
                )
            )

        # Handle unexpected status codes
        if response.status_code != 200:
            logger.warning(
                f"schwab_token_{operation}_unexpected_status",
                provider=self.slug,
                status_code=response.status_code,
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message=f"Unexpected response from Schwab: {response.status_code}",
                    provider_name=self.slug,
                    response_body=response.text[:500],
                )
            )

        # Parse successful response
        try:
            data = response.json()
        except ValueError as e:
            logger.error(
                f"schwab_token_{operation}_invalid_json",
                provider=self.slug,
                error=str(e),
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message="Invalid JSON response from Schwab",
                    provider_name=self.slug,
                    response_body=response.text[:500],
                )
            )

        # Extract tokens
        try:
            tokens = OAuthTokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_in=data["expires_in"],
                token_type=data.get("token_type", "Bearer"),
                scope=data.get("scope"),
            )
        except KeyError as e:
            logger.error(
                f"schwab_token_{operation}_missing_field",
                provider=self.slug,
                missing_field=str(e),
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message=f"Missing required field in Schwab response: {e}",
                    provider_name=self.slug,
                    response_body=response.text[:500],
                )
            )

        logger.info(
            f"schwab_token_{operation}_succeeded",
            provider=self.slug,
            expires_in=tokens.expires_in,
            has_refresh_token=tokens.refresh_token is not None,
        )

        return Success(value=tokens)

    async def fetch_accounts(
        self,
        access_token: str,
    ) -> Result[list[ProviderAccountData], ProviderError]:
        """Fetch all accounts for the authenticated user.

        Args:
            access_token: Valid Schwab access token.

        Returns:
            Success(list[ProviderAccountData]): Account data from Schwab.
            Failure(ProviderAuthenticationError): If token is invalid/expired.
            Failure(ProviderUnavailableError): If Schwab API is unreachable.
        """
        logger.info(
            "schwab_fetch_accounts_started",
            provider=self.slug,
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._trader_api_base}/accounts",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                    params={"fields": "positions"},
                )

            return self._handle_accounts_response(response)

        except httpx.TimeoutException as e:
            logger.warning(
                "schwab_fetch_accounts_timeout",
                provider=self.slug,
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message="Schwab API request timed out",
                    provider_name=self.slug,
                    is_transient=True,
                )
            )
        except httpx.RequestError as e:
            logger.warning(
                "schwab_fetch_accounts_connection_error",
                provider=self.slug,
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Failed to connect to Schwab API: {e}",
                    provider_name=self.slug,
                    is_transient=True,
                )
            )

    def _handle_accounts_response(
        self,
        response: httpx.Response,
    ) -> Result[list[ProviderAccountData], ProviderError]:
        """Handle Schwab accounts API response.

        Args:
            response: HTTP response from accounts endpoint.

        Returns:
            Success(list[ProviderAccountData]) or Failure(ProviderError).
        """
        # Handle common error cases
        error_result = self._check_api_error_response(response, "fetch_accounts")
        if error_result is not None:
            return error_result

        # Parse successful response
        try:
            data = response.json()
        except ValueError as e:
            logger.error(
                "schwab_fetch_accounts_invalid_json",
                provider=self.slug,
                error=str(e),
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message="Invalid JSON response from Schwab",
                    provider_name=self.slug,
                    response_body=response.text[:500],
                )
            )

        # Map Schwab accounts to ProviderAccountData
        accounts: list[ProviderAccountData] = []

        # Schwab returns list of account objects
        account_list = data if isinstance(data, list) else []

        for account_data in account_list:
            try:
                account = self._map_account(account_data)
                if account is not None:
                    accounts.append(account)
            except (KeyError, TypeError, InvalidOperation) as e:
                logger.warning(
                    "schwab_account_mapping_error",
                    provider=self.slug,
                    error=str(e),
                    account_data=str(account_data)[:200],
                )
                # Continue processing other accounts
                continue

        logger.info(
            "schwab_fetch_accounts_succeeded",
            provider=self.slug,
            account_count=len(accounts),
        )

        return Success(value=accounts)

    def _map_account(self, data: dict[str, Any]) -> ProviderAccountData | None:
        """Map Schwab account JSON to ProviderAccountData.

        Args:
            data: Single account object from Schwab API.

        Returns:
            ProviderAccountData or None if mapping fails.
        """
        # Schwab structure: { "securitiesAccount": { ... } }
        securities_account = data.get("securitiesAccount", {})

        if not securities_account:
            return None

        account_number = securities_account.get("accountNumber", "")
        current_balances = securities_account.get("currentBalances", {})

        # Mask account number (show last 4 digits)
        masked = f"****{account_number[-4:]}" if len(account_number) >= 4 else "****"

        return ProviderAccountData(
            provider_account_id=account_number,
            account_number_masked=masked,
            name=securities_account.get("accountName", f"Schwab {masked}"),
            account_type=securities_account.get("type", "UNKNOWN"),
            balance=Decimal(str(current_balances.get("liquidationValue", 0))),
            currency="USD",
            available_balance=Decimal(str(current_balances.get("availableFunds", 0))),
            is_active=True,
            raw_data=data,
        )

    async def fetch_transactions(
        self,
        access_token: str,
        provider_account_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Result[list[ProviderTransactionData], ProviderError]:
        """Fetch transactions for a specific account.

        Args:
            access_token: Valid Schwab access token.
            provider_account_id: Schwab account number.
            start_date: Beginning of date range (default: 30 days ago).
            end_date: End of date range (default: today).

        Returns:
            Success(list[ProviderTransactionData]): Transaction data from Schwab.
            Failure(ProviderAuthenticationError): If token is invalid/expired.
            Failure(ProviderUnavailableError): If Schwab API is unreachable.
        """
        logger.info(
            "schwab_fetch_transactions_started",
            provider=self.slug,
            account_id=provider_account_id[-4:],  # Log only last 4 chars
            start_date=str(start_date),
            end_date=str(end_date),
        )

        # Build query params
        params: dict[str, str] = {}
        if start_date:
            params["startDate"] = start_date.isoformat()
        if end_date:
            params["endDate"] = end_date.isoformat()

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._trader_api_base}/accounts/{provider_account_id}/transactions",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                    params=params if params else None,
                )

            return self._handle_transactions_response(response)

        except httpx.TimeoutException as e:
            logger.warning(
                "schwab_fetch_transactions_timeout",
                provider=self.slug,
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message="Schwab API request timed out",
                    provider_name=self.slug,
                    is_transient=True,
                )
            )
        except httpx.RequestError as e:
            logger.warning(
                "schwab_fetch_transactions_connection_error",
                provider=self.slug,
                error=str(e),
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Failed to connect to Schwab API: {e}",
                    provider_name=self.slug,
                    is_transient=True,
                )
            )

    def _handle_transactions_response(
        self,
        response: httpx.Response,
    ) -> Result[list[ProviderTransactionData], ProviderError]:
        """Handle Schwab transactions API response.

        Args:
            response: HTTP response from transactions endpoint.

        Returns:
            Success(list[ProviderTransactionData]) or Failure(ProviderError).
        """
        # Handle common error cases
        error_result = self._check_api_error_response(response, "fetch_transactions")
        if error_result is not None:
            return error_result

        # Parse successful response
        try:
            data = response.json()
        except ValueError as e:
            logger.error(
                "schwab_fetch_transactions_invalid_json",
                provider=self.slug,
                error=str(e),
            )
            return Failure(
                error=ProviderInvalidResponseError(
                    code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                    message="Invalid JSON response from Schwab",
                    provider_name=self.slug,
                    response_body=response.text[:500],
                )
            )

        # Map Schwab transactions to ProviderTransactionData
        transactions: list[ProviderTransactionData] = []

        # Schwab returns list of transaction objects
        transaction_list = data if isinstance(data, list) else []

        for txn_data in transaction_list:
            try:
                txn = self._map_transaction(txn_data)
                if txn is not None:
                    transactions.append(txn)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(
                    "schwab_transaction_mapping_error",
                    provider=self.slug,
                    error=str(e),
                )
                # Continue processing other transactions
                continue

        logger.info(
            "schwab_fetch_transactions_succeeded",
            provider=self.slug,
            transaction_count=len(transactions),
        )

        return Success(value=transactions)

    def _map_transaction(self, data: dict[str, Any]) -> ProviderTransactionData | None:
        """Map Schwab transaction JSON to ProviderTransactionData.

        Args:
            data: Single transaction object from Schwab API.

        Returns:
            ProviderTransactionData or None if mapping fails.
        """
        txn_id = data.get("activityId") or data.get("transactionId")
        if not txn_id:
            return None

        # Parse transaction date
        txn_date_str = data.get("tradeDate") or data.get("transactionDate")
        if not txn_date_str:
            return None

        # Parse date (format: YYYY-MM-DD or ISO datetime)
        txn_date = date.fromisoformat(txn_date_str[:10])

        # Parse settlement date if present
        settle_date_str = data.get("settlementDate")
        settle_date = (
            date.fromisoformat(settle_date_str[:10]) if settle_date_str else None
        )

        # Get transaction info
        txn_info = data.get("transactionItem", {})
        instrument = txn_info.get("instrument", {})

        # Calculate amount
        net_amount = data.get("netAmount", 0)

        return ProviderTransactionData(
            provider_transaction_id=str(txn_id),
            transaction_type=data.get("type", "UNKNOWN"),
            subtype=data.get("subType"),
            amount=Decimal(str(net_amount)),
            currency="USD",
            description=data.get("description", ""),
            transaction_date=txn_date,
            settlement_date=settle_date,
            status=data.get("status", "EXECUTED"),
            # Security details
            symbol=instrument.get("symbol"),
            security_name=instrument.get("description"),
            asset_type=instrument.get("assetType"),
            quantity=(
                Decimal(str(txn_info.get("amount", 0)))
                if txn_info.get("amount")
                else None
            ),
            unit_price=(
                Decimal(str(txn_info.get("price", 0)))
                if txn_info.get("price")
                else None
            ),
            commission=(
                Decimal(str(data.get("totalCommission", 0)))
                if data.get("totalCommission")
                else None
            ),
            raw_data=data,
        )

    def _check_api_error_response(
        self,
        response: httpx.Response,
        operation: str,
    ) -> Failure[ProviderError] | None:
        """Check for common API error responses.

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
                f"schwab_{operation}_rate_limited",
                provider=self.slug,
                retry_after=retry_seconds,
            )
            return Failure(
                error=ProviderRateLimitError(
                    code=ErrorCode.PROVIDER_RATE_LIMITED,
                    message="Schwab API rate limit exceeded",
                    provider_name=self.slug,
                    retry_after=retry_seconds,
                )
            )

        # Authentication errors
        if response.status_code == 401:
            logger.warning(
                f"schwab_{operation}_auth_failed",
                provider=self.slug,
            )
            return Failure(
                error=ProviderAuthenticationError(
                    code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
                    message="Schwab access token is invalid or expired",
                    provider_name=self.slug,
                    is_token_expired=True,
                )
            )

        # Forbidden (authorization)
        if response.status_code == 403:
            logger.warning(
                f"schwab_{operation}_forbidden",
                provider=self.slug,
            )
            return Failure(
                error=ProviderAuthenticationError(
                    code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
                    message="Access denied to Schwab resource",
                    provider_name=self.slug,
                    is_token_expired=False,
                )
            )

        # Server errors
        if response.status_code >= 500:
            logger.warning(
                f"schwab_{operation}_server_error",
                provider=self.slug,
                status_code=response.status_code,
            )
            return Failure(
                error=ProviderUnavailableError(
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    message=f"Schwab API server error: {response.status_code}",
                    provider_name=self.slug,
                    is_transient=True,
                )
            )

        # Success
        if response.status_code == 200:
            return None

        # Unexpected status
        logger.warning(
            f"schwab_{operation}_unexpected_status",
            provider=self.slug,
            status_code=response.status_code,
        )
        return Failure(
            error=ProviderInvalidResponseError(
                code=ErrorCode.PROVIDER_CREDENTIAL_INVALID,
                message=f"Unexpected response from Schwab: {response.status_code}",
                provider_name=self.slug,
                response_body=response.text[:500],
            )
        )
