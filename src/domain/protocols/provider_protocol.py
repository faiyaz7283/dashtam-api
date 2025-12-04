"""ProviderProtocol for financial provider adapters.

Port (interface) for hexagonal architecture.
Infrastructure layer implements this protocol for each provider (Schwab, Plaid, etc.).

This protocol defines the contract that all financial providers must implement,
regardless of their authentication mechanism (OAuth, API key, etc.) or API structure.

Methods return Result types following railway-oriented programming pattern.
See docs/architecture/error-handling-architecture.md for details.

Reference:
    - docs/architecture/provider-integration-architecture.md
    - docs/architecture/provider-oauth-architecture.md
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from src.core.result import Result
    from src.infrastructure.errors import ProviderError


# =============================================================================
# Provider Data Types (returned by providers, before mapping to domain)
# =============================================================================


@dataclass(frozen=True, kw_only=True)
class OAuthTokens:
    """OAuth tokens returned by provider after authentication.

    Returned from exchange_code_for_tokens() and refresh_access_token().

    Attributes:
        access_token: Bearer token for API authentication.
        refresh_token: Token for obtaining new access tokens. May be None if
            provider doesn't rotate tokens on refresh.
        expires_in: Seconds until access_token expires.
        token_type: Token type, typically "Bearer".
        scope: OAuth scope granted (provider-specific).

    Example:
        >>> tokens = await provider.exchange_code_for_tokens(code)
        >>> print(f"Token expires in {tokens.expires_in} seconds")
    """

    access_token: str
    refresh_token: str | None
    expires_in: int
    token_type: str = "Bearer"
    scope: str | None = None


@dataclass(frozen=True, kw_only=True)
class ProviderAccountData:
    """Account data as returned by provider (before mapping to domain).

    Provider adapters return this; mappers convert to Account entity.
    This intermediate type decouples provider response format from domain model.

    Attributes:
        provider_account_id: Provider's unique account identifier.
        account_number_masked: Masked account number for display (e.g., "****1234").
        name: Account name from provider.
        account_type: Provider's account type string (mapped by AccountMapper).
        balance: Current account balance.
        available_balance: Available balance if different from balance.
        currency: ISO 4217 currency code (e.g., "USD").
        is_active: Whether account is active on provider.
        raw_data: Full provider response for metadata/debugging.

    Example:
        >>> accounts = await provider.fetch_accounts(access_token)
        >>> for account in accounts:
        ...     domain_account = mapper.to_entity(account, connection_id)
    """

    provider_account_id: str
    account_number_masked: str
    name: str
    account_type: str
    balance: Decimal
    currency: str
    available_balance: Decimal | None = None
    is_active: bool = True
    raw_data: dict[str, Any] | None = None


@dataclass(frozen=True, kw_only=True)
class ProviderTransactionData:
    """Transaction data as returned by provider (before mapping to domain).

    Provider adapters return this; mappers convert to Transaction entity.
    This intermediate type decouples provider response format from domain model.

    Attributes:
        provider_transaction_id: Provider's unique transaction identifier.
        transaction_type: Provider's transaction type string.
        subtype: Provider's transaction subtype (if applicable).
        amount: Transaction amount (positive=credit, negative=debit).
        currency: ISO 4217 currency code.
        description: Human-readable transaction description.
        transaction_date: Date transaction occurred.
        settlement_date: Date funds/securities settled (if applicable).
        status: Provider's transaction status string.
        symbol: Security ticker symbol (for trades).
        security_name: Full security name (for trades).
        asset_type: Security asset type (for trades).
        quantity: Number of shares/units (for trades).
        unit_price: Price per share/unit (for trades).
        commission: Trading commission (for trades).
        raw_data: Full provider response for metadata/debugging.

    Example:
        >>> transactions = await provider.fetch_transactions(
        ...     access_token, account_id, start_date, end_date
        ... )
        >>> for txn in transactions:
        ...     domain_txn = mapper.to_entity(txn, account_id)
    """

    provider_transaction_id: str
    transaction_type: str
    amount: Decimal
    currency: str
    description: str
    transaction_date: date
    status: str
    subtype: str | None = None
    settlement_date: date | None = None
    # Security details (for trades)
    symbol: str | None = None
    security_name: str | None = None
    asset_type: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    commission: Decimal | None = None
    # Metadata
    raw_data: dict[str, Any] | None = None


# =============================================================================
# Provider Protocol (Port)
# =============================================================================


class ProviderProtocol(Protocol):
    """Protocol (port) for financial provider adapters.

    Each financial provider (Schwab, Plaid, Chase, etc.) implements this
    protocol to integrate with Dashtam. The protocol is auth-agnostic -
    OAuth providers implement exchange_code_for_tokens, API-key providers
    may have different initialization.

    This is a Protocol (not ABC) for structural typing.
    Implementations don't need to inherit from this.

    All methods return Result types (railway-oriented programming):
    - Success(data) on successful API calls
    - Failure(ProviderError) on failures

    Provider implementations live in:
        src/infrastructure/providers/{provider_slug}/

    Example Implementation:
        >>> class SchwabProvider:
        ...     @property
        ...     def slug(self) -> str:
        ...         return "schwab"
        ...
        ...     async def exchange_code_for_tokens(
        ...         self, code: str
        ...     ) -> Result[OAuthTokens, ProviderError]:
        ...         # Schwab-specific OAuth implementation
        ...         ...

    Reference:
        - docs/architecture/provider-integration-architecture.md
        - docs/architecture/error-handling-architecture.md
    """

    @property
    def slug(self) -> str:
        """Unique provider identifier.

        Used for routing, configuration, and database storage.
        Must be lowercase, alphanumeric with underscores.

        Returns:
            Provider slug (e.g., "schwab", "plaid", "chase").

        Example:
            >>> provider.slug
            'schwab'
        """
        ...

    async def exchange_code_for_tokens(
        self,
        authorization_code: str,
    ) -> "Result[OAuthTokens, ProviderError]":
        """Exchange OAuth authorization code for access and refresh tokens.

        Called after user completes OAuth consent flow and is redirected
        back with an authorization code.

        Args:
            authorization_code: Code from OAuth callback query parameter.

        Returns:
            Success(OAuthTokens): With access_token, refresh_token, and expiration.
            Failure(ProviderAuthenticationError): If code is invalid or expired.
            Failure(ProviderUnavailableError): If provider API is unreachable.

        Example:
            >>> result = await provider.exchange_code_for_tokens(code)
            >>> match result:
            ...     case Success(tokens):
            ...         encrypted = encryption_service.encrypt({
            ...             "access_token": tokens.access_token,
            ...             "refresh_token": tokens.refresh_token,
            ...         })
            ...     case Failure(error):
            ...         logger.error(f"Token exchange failed: {error.message}")
        """
        ...

    async def refresh_access_token(
        self,
        refresh_token: str,
    ) -> "Result[OAuthTokens, ProviderError]":
        """Refresh access token using refresh token.

        Called when access token is expired or about to expire.
        May return a new refresh token if provider rotates tokens.

        Args:
            refresh_token: Current refresh token.

        Returns:
            Success(OAuthTokens): With new access_token. refresh_token is:
                - None if provider doesn't rotate tokens
                - New token if provider rotated
                - Same token if provider returns same token
            Failure(ProviderAuthenticationError): If refresh token is invalid/expired.
                User must re-authenticate via OAuth flow.
            Failure(ProviderUnavailableError): If provider API is unreachable.

        Example:
            >>> result = await provider.refresh_access_token(refresh_token)
            >>> match result:
            ...     case Success(new_tokens):
            ...         if new_tokens.refresh_token:
            ...             # Provider rotated token, must update storage
            ...             new_refresh = new_tokens.refresh_token
            ...         else:
            ...             # Keep existing refresh token
            ...             new_refresh = refresh_token
            ...     case Failure(error):
            ...         # User must re-authenticate
            ...         logger.warning(f"Token refresh failed: {error.message}")
        """
        ...

    async def fetch_accounts(
        self,
        access_token: str,
    ) -> "Result[list[ProviderAccountData], ProviderError]":
        """Fetch all accounts for the authenticated user.

        Returns account data in provider's format. Use AccountMapper
        to convert to domain Account entities.

        Args:
            access_token: Valid access token for API authentication.

        Returns:
            Success(list[ProviderAccountData]): Account data (empty list if no accounts).
            Failure(ProviderAuthenticationError): If token is invalid/expired.
            Failure(ProviderUnavailableError): If provider API is unreachable.
            Failure(ProviderRateLimitError): If rate limit exceeded.

        Example:
            >>> result = await provider.fetch_accounts(access_token)
            >>> match result:
            ...     case Success(accounts):
            ...         for account_data in accounts:
            ...             account = mapper.to_entity(account_data, connection_id)
            ...             await account_repo.save(account)
            ...     case Failure(error):
            ...         logger.error(f"Failed to fetch accounts: {error.message}")
        """
        ...

    async def fetch_transactions(
        self,
        access_token: str,
        provider_account_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> "Result[list[ProviderTransactionData], ProviderError]":
        """Fetch transactions for a specific account.

        Returns transaction data in provider's format. Use TransactionMapper
        to convert to domain Transaction entities.

        Args:
            access_token: Valid access token for API authentication.
            provider_account_id: Provider's account identifier (from ProviderAccountData).
            start_date: Beginning of date range (default: provider-specific, often 30 days).
            end_date: End of date range (default: today).

        Returns:
            Success(list[ProviderTransactionData]): Transaction data (empty list if none).
            Failure(ProviderAuthenticationError): If token is invalid/expired.
            Failure(ProviderUnavailableError): If provider API is unreachable.
            Failure(ProviderRateLimitError): If rate limit exceeded.

        Example:
            >>> result = await provider.fetch_transactions(
            ...     access_token,
            ...     "12345",
            ...     start_date=date(2024, 1, 1),
            ...     end_date=date(2024, 12, 31),
            ... )
            >>> match result:
            ...     case Success(transactions):
            ...         for txn_data in transactions:
            ...             txn = mapper.to_entity(txn_data, account_id)
            ...             await txn_repo.save(txn)
            ...     case Failure(error):
            ...         logger.error(f"Failed to fetch transactions: {error.message}")
        """
        ...
