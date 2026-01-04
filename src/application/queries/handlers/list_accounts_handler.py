"""ListAccounts query handlers.

Handles requests to list accounts by connection or by user.
Returns DTOs with aggregated balance information.

Architecture:
- Application layer handlers (orchestrate data retrieval)
- Returns Result[DTO, str] (explicit error handling)
- NO domain events (queries are side-effect free)
- Connection-scoped and user-scoped queries

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/account-domain-model.md
"""

import json
from dataclasses import dataclass
from decimal import Decimal

from src.application.queries.account_queries import (
    ListAccountsByConnection,
    ListAccountsByUser,
)
from src.application.queries.handlers.get_account_handler import AccountResult
from src.core.config import settings
from src.core.result import Failure, Result, Success
from src.domain.protocols.cache_protocol import CacheProtocol
from src.infrastructure.cache.cache_keys import CacheKeys
from src.infrastructure.cache.cache_metrics import CacheMetrics
from src.domain.enums.account_type import AccountType
from src.domain.protocols.account_repository import AccountRepository
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)


@dataclass
class AccountListResult:
    """List of accounts with aggregated balance information.

    Attributes:
        accounts: List of account DTOs.
        total_count: Total number of accounts.
        active_count: Number of active accounts.
        total_balance_by_currency: Aggregated balances by currency (e.g.,
            {"USD": "15000.50", "EUR": "2000.00"}).
    """

    accounts: list[AccountResult]
    total_count: int
    active_count: int
    total_balance_by_currency: dict[str, str]


class ListAccountsByConnectionError:
    """ListAccountsByConnection-specific errors."""

    CONNECTION_NOT_FOUND = "Provider connection not found"
    NOT_OWNED_BY_USER = "Provider connection not owned by user"


class ListAccountsByConnectionHandler:
    """Handler for ListAccountsByConnection query.

    Retrieves accounts for a specific provider connection.
    Ownership checked by verifying the connection belongs to the user.

    Dependencies (injected via constructor):
        - AccountRepository: For account retrieval
        - ProviderConnectionRepository: For ownership verification
    """

    def __init__(
        self,
        account_repo: AccountRepository,
        connection_repo: ProviderConnectionRepository,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            account_repo: Account repository.
            connection_repo: Provider connection repository for ownership check.
        """
        self._account_repo = account_repo
        self._connection_repo = connection_repo

    async def handle(
        self, query: ListAccountsByConnection
    ) -> Result[AccountListResult, str]:
        """Handle ListAccountsByConnection query.

        Retrieves accounts for connection, verifies ownership, and maps to DTOs.

        Args:
            query: ListAccountsByConnection query.

        Returns:
            Success(AccountListResult): Accounts found and owned by user.
            Failure(error): Connection not found or not owned by user.
        """
        # Fetch connection to verify ownership
        connection = await self._connection_repo.find_by_id(query.connection_id)

        if connection is None:
            return Failure(error=ListAccountsByConnectionError.CONNECTION_NOT_FOUND)

        # Verify ownership (connection belongs to user)
        if connection.user_id != query.user_id:
            return Failure(error=ListAccountsByConnectionError.NOT_OWNED_BY_USER)

        # Fetch accounts for connection
        accounts = await self._account_repo.find_by_connection_id(
            connection_id=query.connection_id, active_only=query.active_only
        )

        # Map to DTOs
        account_dtos = [
            AccountResult(
                id=account.id,
                connection_id=account.connection_id,
                provider_account_id=account.provider_account_id,
                account_number_masked=account.account_number_masked,
                name=account.name,
                account_type=account.account_type.value,
                currency=account.currency,
                balance_amount=account.balance.amount,
                balance_currency=account.balance.currency,
                available_balance_amount=(
                    account.available_balance.amount
                    if account.available_balance
                    else None
                ),
                available_balance_currency=(
                    account.available_balance.currency
                    if account.available_balance
                    else None
                ),
                is_active=account.is_active,
                is_investment=account.is_investment_account(),
                is_bank=account.is_bank_account(),
                is_retirement=account.is_retirement_account(),
                is_credit=account.is_credit_account(),
                last_synced_at=account.last_synced_at,
                created_at=account.created_at,
                updated_at=account.updated_at,
            )
            for account in accounts
        ]

        # Calculate aggregates
        total_count = len(accounts)
        active_count = sum(1 for acc in accounts if acc.is_active)

        # Aggregate balances by currency
        balance_by_currency: dict[str, Decimal] = {}
        for account in accounts:
            currency = account.balance.currency
            balance_by_currency[currency] = (
                balance_by_currency.get(currency, Decimal("0.00"))
                + account.balance.amount
            )

        # Convert Decimal to string for JSON serialization
        total_balance_by_currency = {
            currency: str(amount) for currency, amount in balance_by_currency.items()
        }

        # Create result DTO
        dto = AccountListResult(
            accounts=account_dtos,
            total_count=total_count,
            active_count=active_count,
            total_balance_by_currency=total_balance_by_currency,
        )

        return Success(value=dto)


class ListAccountsByUserError:
    """ListAccountsByUser-specific errors."""

    # No errors currently - user always exists if authenticated


class ListAccountsByUserHandler:
    """Handler for ListAccountsByUser query.

    Retrieves all accounts for a user across all provider connections.
    Uses cache-first strategy for performance.

    Dependencies (injected via constructor):
        - AccountRepository: For account retrieval
        - CacheProtocol: Optional cache for account list caching
        - CacheKeys: Optional cache key utility
        - CacheMetrics: Optional metrics tracker
    """

    def __init__(
        self,
        account_repo: AccountRepository,
        cache: CacheProtocol | None = None,
        cache_keys: CacheKeys | None = None,
        cache_metrics: CacheMetrics | None = None,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            account_repo: Account repository.
            cache: Optional cache for account list caching.
            cache_keys: Optional cache key utility.
            cache_metrics: Optional metrics tracker.
        """
        self._account_repo = account_repo
        self._cache = cache
        self._cache_keys = cache_keys
        self._cache_metrics = cache_metrics
        self._cache_ttl = settings.cache_accounts_ttl

    async def handle(self, query: ListAccountsByUser) -> Result[AccountListResult, str]:
        """Handle ListAccountsByUser query.

        Uses cache-first strategy if cache is enabled.
        Retrieves all accounts for user and maps to DTOs.

        Args:
            query: ListAccountsByUser query.

        Returns:
            Success(AccountListResult): Accounts found.
            Failure(error): Error occurred (rare, DB-level issues only).
        """
        # Try cache first if enabled and no filters (cache only unfiltered lists)
        if (
            self._cache
            and self._cache_keys
            and not query.account_type
            and not query.active_only
        ):
            cache_key = self._cache_keys.account_list(query.user_id)
            cache_result = await self._cache.get(cache_key)

            if isinstance(cache_result, Success) and cache_result.value:
                # Cache hit
                if self._cache_metrics:
                    self._cache_metrics.record_hit("accounts")
                try:
                    cached_data = json.loads(cache_result.value)
                    dto = AccountListResult(**cached_data)
                    return Success(value=dto)
                except (json.JSONDecodeError, TypeError, ValueError):
                    # Continue to DB fetch on deserialization error
                    pass

            # Cache miss
            if self._cache_metrics:
                self._cache_metrics.record_miss("accounts")

        # Parse account_type filter if provided
        account_type: AccountType | None = None
        if query.account_type:
            try:
                account_type = AccountType(query.account_type)
            except ValueError:
                # Invalid account_type string - return empty list
                return Success(
                    value=AccountListResult(
                        accounts=[],
                        total_count=0,
                        active_count=0,
                        total_balance_by_currency={},
                    )
                )

        # Fetch accounts for user
        accounts = await self._account_repo.find_by_user_id(
            user_id=query.user_id,
            active_only=query.active_only,
            account_type=account_type,
        )

        # Map to DTOs
        account_dtos = [
            AccountResult(
                id=account.id,
                connection_id=account.connection_id,
                provider_account_id=account.provider_account_id,
                account_number_masked=account.account_number_masked,
                name=account.name,
                account_type=account.account_type.value,
                currency=account.currency,
                balance_amount=account.balance.amount,
                balance_currency=account.balance.currency,
                available_balance_amount=(
                    account.available_balance.amount
                    if account.available_balance
                    else None
                ),
                available_balance_currency=(
                    account.available_balance.currency
                    if account.available_balance
                    else None
                ),
                is_active=account.is_active,
                is_investment=account.is_investment_account(),
                is_bank=account.is_bank_account(),
                is_retirement=account.is_retirement_account(),
                is_credit=account.is_credit_account(),
                last_synced_at=account.last_synced_at,
                created_at=account.created_at,
                updated_at=account.updated_at,
            )
            for account in accounts
        ]

        # Calculate aggregates
        total_count = len(accounts)
        active_count = sum(1 for acc in accounts if acc.is_active)

        # Aggregate balances by currency
        balance_by_currency: dict[str, Decimal] = {}
        for account in accounts:
            currency = account.balance.currency
            balance_by_currency[currency] = (
                balance_by_currency.get(currency, Decimal("0.00"))
                + account.balance.amount
            )

        # Convert Decimal to string for JSON serialization
        total_balance_by_currency = {
            currency: str(amount) for currency, amount in balance_by_currency.items()
        }

        # Create result DTO
        dto = AccountListResult(
            accounts=account_dtos,
            total_count=total_count,
            active_count=active_count,
            total_balance_by_currency=total_balance_by_currency,
        )

        # Populate cache if enabled and no filters
        if (
            self._cache
            and self._cache_keys
            and not query.account_type
            and not query.active_only
        ):
            cache_key = self._cache_keys.account_list(query.user_id)
            try:
                # Serialize DTO to JSON
                # Convert dataclasses to dict, handling nested AccountResult objects
                cache_data = {
                    "accounts": [
                        {
                            "id": str(acc.id),
                            "connection_id": str(acc.connection_id),
                            "provider_account_id": acc.provider_account_id,
                            "account_number_masked": acc.account_number_masked,
                            "name": acc.name,
                            "account_type": acc.account_type,
                            "currency": acc.currency,
                            "balance_amount": str(acc.balance_amount),
                            "balance_currency": acc.balance_currency,
                            "available_balance_amount": (
                                str(acc.available_balance_amount)
                                if acc.available_balance_amount is not None
                                else None
                            ),
                            "available_balance_currency": acc.available_balance_currency,
                            "is_active": acc.is_active,
                            "is_investment": acc.is_investment,
                            "is_bank": acc.is_bank,
                            "is_retirement": acc.is_retirement,
                            "is_credit": acc.is_credit,
                            "last_synced_at": (
                                acc.last_synced_at.isoformat()
                                if acc.last_synced_at
                                else None
                            ),
                            "created_at": acc.created_at.isoformat(),
                            "updated_at": acc.updated_at.isoformat(),
                        }
                        for acc in dto.accounts
                    ],
                    "total_count": dto.total_count,
                    "active_count": dto.active_count,
                    "total_balance_by_currency": dto.total_balance_by_currency,
                }
                cache_json = json.dumps(cache_data)
                await self._cache.set(cache_key, cache_json, ttl=self._cache_ttl)
            except (TypeError, ValueError):
                # Fail-open: cache write failure doesn't affect response
                pass

        return Success(value=dto)
