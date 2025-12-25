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

Architecture:
    SchwabProvider orchestrates:
    - api/accounts_api.py: HTTP client for accounts endpoints
    - api/transactions_api.py: HTTP client for transactions endpoints
    - mappers/account_mapper.py: JSON → ProviderAccountData
    - mappers/transaction_mapper.py: JSON → ProviderTransactionData

Reference:
    - docs/architecture/provider-integration-architecture.md
    - docs/architecture/provider-oauth-architecture.md
"""

import base64
import json
from datetime import date
from uuid import UUID

import httpx
import structlog

from src.core.config import Settings
from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success
from src.domain.protocols.cache_protocol import CacheProtocol
from src.infrastructure.cache.cache_keys import CacheKeys
from src.infrastructure.cache.cache_metrics import CacheMetrics
from src.domain.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from src.domain.protocols.provider_protocol import (
    OAuthTokens,
    ProviderAccountData,
    ProviderTransactionData,
)
from src.infrastructure.providers.schwab.api.accounts_api import SchwabAccountsAPI
from src.infrastructure.providers.schwab.api.transactions_api import (
    SchwabTransactionsAPI,
)
from src.infrastructure.providers.schwab.mappers.account_mapper import (
    SchwabAccountMapper,
)
from src.infrastructure.providers.schwab.mappers.transaction_mapper import (
    SchwabTransactionMapper,
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
        cache: CacheProtocol | None = None,
        cache_keys: CacheKeys | None = None,
        cache_metrics: CacheMetrics | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize Schwab provider.

        Args:
            settings: Application settings with Schwab configuration.
            cache: Optional cache for API response caching.
            cache_keys: Optional cache key utility.
            cache_metrics: Optional metrics tracker.
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
        self._cache = cache
        self._cache_keys = cache_keys
        self._cache_metrics = cache_metrics
        self._cache_ttl = settings.cache_schwab_ttl

        # Initialize API clients and mappers
        self._accounts_api = SchwabAccountsAPI(
            base_url=self._trader_api_base,
            timeout=timeout,
        )
        self._transactions_api = SchwabTransactionsAPI(
            base_url=self._trader_api_base,
            timeout=timeout,
        )
        self._account_mapper = SchwabAccountMapper()
        self._transaction_mapper = SchwabTransactionMapper()

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
        user_id: UUID | None = None,
    ) -> Result[list[ProviderAccountData], ProviderError]:
        """Fetch all accounts for the authenticated user.

        Uses cache-first strategy if cache is enabled and user_id provided.
        Delegates to SchwabAccountsAPI for HTTP and SchwabAccountMapper for mapping.

        Args:
            access_token: Valid Schwab access token.
            user_id: Optional user ID for caching (required for cache).

        Returns:
            Success(list[ProviderAccountData]): Account data from Schwab.
            Failure(ProviderAuthenticationError): If token is invalid/expired.
            Failure(ProviderUnavailableError): If Schwab API is unreachable.
        """
        logger.info(
            "schwab_fetch_accounts_started",
            provider=self.slug,
        )

        # Try cache first if enabled
        if self._cache and self._cache_keys and user_id:
            cache_key = self._cache_keys.schwab_accounts(user_id)
            cache_result = await self._cache.get(cache_key)

            if isinstance(cache_result, Success) and cache_result.value:
                # Cache hit
                if self._cache_metrics:
                    self._cache_metrics.record_hit("schwab")
                try:
                    cached_data = json.loads(cache_result.value)
                    accounts = [ProviderAccountData(**acc) for acc in cached_data]
                    logger.debug(
                        "schwab_fetch_accounts_cache_hit",
                        provider=self.slug,
                        user_id=str(user_id),
                    )
                    return Success(value=accounts)
                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    logger.warning(
                        "schwab_cache_deserialize_error",
                        error=str(e),
                    )
                    # Continue to API fetch on deserialization error

            # Cache miss
            if self._cache_metrics:
                self._cache_metrics.record_miss("schwab")

        # Fetch raw JSON from Schwab API
        result = await self._accounts_api.get_accounts(
            access_token=access_token,
            include_positions=True,
        )

        # Handle API errors
        if isinstance(result, Failure):
            return Failure(error=result.error)

        raw_accounts = result.value

        # Map raw JSON to ProviderAccountData
        accounts = self._account_mapper.map_accounts(raw_accounts)

        # Populate cache if enabled
        if self._cache and self._cache_keys and user_id:
            cache_key = self._cache_keys.schwab_accounts(user_id)
            try:
                # Serialize to JSON (ProviderAccountData is a dataclass)
                cache_data = json.dumps([acc.__dict__ for acc in accounts])
                await self._cache.set(cache_key, cache_data, ttl=self._cache_ttl)
                logger.debug(
                    "schwab_fetch_accounts_cached",
                    provider=self.slug,
                    user_id=str(user_id),
                )
            except (TypeError, ValueError) as e:
                logger.warning(
                    "schwab_cache_serialize_error",
                    error=str(e),
                )
                # Fail-open: cache write failure doesn't affect response

        logger.info(
            "schwab_fetch_accounts_succeeded",
            provider=self.slug,
            account_count=len(accounts),
        )

        return Success(value=accounts)

    async def fetch_transactions(
        self,
        access_token: str,
        provider_account_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Result[list[ProviderTransactionData], ProviderError]:
        """Fetch transactions for a specific account.

        Delegates to SchwabTransactionsAPI for HTTP and SchwabTransactionMapper for mapping.

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
            account_id=provider_account_id[-4:]
            if len(provider_account_id) >= 4
            else "****",
            start_date=str(start_date),
            end_date=str(end_date),
        )

        # Fetch raw JSON from Schwab API
        result = await self._transactions_api.get_transactions(
            access_token=access_token,
            account_number=provider_account_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Handle API errors
        if isinstance(result, Failure):
            return Failure(error=result.error)

        raw_transactions = result.value

        # Map raw JSON to ProviderTransactionData
        transactions = self._transaction_mapper.map_transactions(raw_transactions)

        logger.info(
            "schwab_fetch_transactions_succeeded",
            provider=self.slug,
            transaction_count=len(transactions),
        )

        return Success(value=transactions)

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
