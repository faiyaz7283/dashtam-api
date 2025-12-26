"""Account domain entity.

Represents a financial account aggregated from a provider connection.
Multiple accounts can belong to a single connection (e.g., IRA and brokerage).

Architecture:
    - Pure domain entity (no infrastructure dependencies)
    - Primarily a data container with query methods
    - State changes come from provider sync operations
    - NO domain events (sync operations handled at application layer)

Reference:
    - docs/architecture/account-domain-model.md

Usage:
    from uuid_extensions import uuid7
    from src.domain.entities import Account
    from src.domain.enums import AccountType
    from src.domain.value_objects import Money
    from decimal import Decimal

    account = Account(
        id=uuid7(),
        connection_id=connection.id,
        provider_account_id="SCHWAB-12345",
        account_number_masked="****1234",
        name="Individual Brokerage",
        account_type=AccountType.BROKERAGE,
        balance=Money(Decimal("10000.00"), "USD"),
        currency="USD",
    )
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from src.core.result import Failure, Result, Success
from src.domain.enums.account_type import AccountType
from src.domain.errors.account_error import AccountError
from src.domain.value_objects.money import Money


@dataclass
class Account:
    """Financial account from a provider connection.

    Represents an individual account (brokerage, checking, IRA, etc.)
    aggregated from an external provider. Accounts are data containers
    reflecting provider state, not user-managed entities.

    Provider Agnostic:
        Account structure works for any provider (Schwab, Chase, Fidelity).
        Provider-specific data stored in provider_metadata.

    Financial Precision:
        All monetary values use Money value object with Decimal precision.
        Never store money as float.

    Attributes:
        id: Unique account identifier (internal).
        connection_id: FK to ProviderConnection.
        provider_account_id: Provider's unique account identifier.
        account_number_masked: Masked account number for display (****1234).
        name: Account name from provider.
        account_type: Type classification (BROKERAGE, CHECKING, etc.).
        balance: Current account balance.
        available_balance: Available balance if different (e.g., pending).
        currency: ISO 4217 currency code.
        is_active: Whether account is active on provider.
        last_synced_at: Last successful sync timestamp.
        provider_metadata: Provider-specific data (unstructured).
        created_at: Record creation timestamp.
        updated_at: Last modification timestamp.

    Example:
        >>> account = Account(
        ...     id=uuid7(),
        ...     connection_id=connection.id,
        ...     provider_account_id="ACC-12345",
        ...     account_number_masked="****1234",
        ...     name="Schwab Brokerage",
        ...     account_type=AccountType.BROKERAGE,
        ...     balance=Money(Decimal("10000.00"), "USD"),
        ...     currency="USD",
        ... )
        >>> account.is_investment_account()
        True
    """

    # Required fields
    id: UUID
    connection_id: UUID
    provider_account_id: str
    account_number_masked: str
    name: str
    account_type: AccountType
    balance: Money
    currency: str

    # Optional fields
    available_balance: Money | None = None
    is_active: bool = True
    last_synced_at: datetime | None = None
    provider_metadata: dict[str, Any] | None = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate account after initialization.

        Raises:
            ValueError: If required fields are invalid.

        Note:
            __post_init__ raises ValueError for construction errors.
            These are programming errors, not business logic failures.
        """
        # Validate provider_account_id
        if not self.provider_account_id or not self.provider_account_id.strip():
            raise ValueError(AccountError.INVALID_PROVIDER_ACCOUNT_ID)

        # Validate account_number_masked
        if not self.account_number_masked or not self.account_number_masked.strip():
            raise ValueError(AccountError.INVALID_ACCOUNT_NUMBER)

        # Validate name
        if not self.name or not self.name.strip():
            raise ValueError(AccountError.INVALID_ACCOUNT_NAME)

        # Validate currency consistency with balance
        if self.balance.currency != self.currency.upper():
            raise ValueError(
                f"Balance currency ({self.balance.currency}) must match "
                f"account currency ({self.currency})"
            )

        # Validate available_balance currency if present
        if self.available_balance is not None:
            if self.available_balance.currency != self.currency.upper():
                raise ValueError(
                    f"Available balance currency ({self.available_balance.currency}) "
                    f"must match account currency ({self.currency})"
                )

        # Normalize currency to uppercase
        object.__setattr__(self, "currency", self.currency.upper())

    # -------------------------------------------------------------------------
    # Query Methods (Read-Only)
    # -------------------------------------------------------------------------

    def is_investment_account(self) -> bool:
        """Check if account type is investment-related.

        Investment accounts can hold securities like stocks, bonds,
        mutual funds, and ETFs.

        Returns:
            True if account type is in investment category.

        Example:
            >>> account.account_type = AccountType.BROKERAGE
            >>> account.is_investment_account()
            True
        """
        return self.account_type.is_investment()

    def is_bank_account(self) -> bool:
        """Check if account type is banking-related.

        Bank accounts are traditional deposit accounts like checking
        and savings.

        Returns:
            True if account type is in banking category.

        Example:
            >>> account.account_type = AccountType.CHECKING
            >>> account.is_bank_account()
            True
        """
        return self.account_type.is_bank()

    def is_retirement_account(self) -> bool:
        """Check if account type is retirement-related.

        Retirement accounts have special tax treatment (IRA, 401k, etc.).

        Returns:
            True if account type is in retirement category.

        Example:
            >>> account.account_type = AccountType.IRA
            >>> account.is_retirement_account()
            True
        """
        return self.account_type.is_retirement()

    def is_credit_account(self) -> bool:
        """Check if account type is credit-related.

        Credit accounts represent money owed (credit cards, loans).

        Returns:
            True if account type is in credit category.

        Example:
            >>> account.account_type = AccountType.CREDIT_CARD
            >>> account.is_credit_account()
            True
        """
        return self.account_type.is_credit()

    def has_available_balance(self) -> bool:
        """Check if available balance differs from current balance.

        Some accounts distinguish between current balance and
        available balance (e.g., pending transactions).

        Returns:
            True if available_balance is set and differs from balance.

        Example:
            >>> account.balance = Money(Decimal("1000.00"), "USD")
            >>> account.available_balance = Money(Decimal("900.00"), "USD")
            >>> account.has_available_balance()
            True
        """
        if self.available_balance is None:
            return False
        return self.available_balance != self.balance

    def needs_sync(self, threshold: timedelta) -> bool:
        """Check if account hasn't been synced within threshold.

        Used to identify accounts that need data refresh from provider.

        Args:
            threshold: Maximum time since last sync.

        Returns:
            True if last_synced_at is None or older than threshold.

        Example:
            >>> account.needs_sync(timedelta(hours=1))
            True  # If not synced in last hour
        """
        if self.last_synced_at is None:
            return True
        return datetime.now(UTC) - self.last_synced_at > threshold

    def get_display_name(self) -> str:
        """Get user-friendly display name for account.

        Combines account name with masked number for identification.

        Returns:
            Display string like "Schwab Brokerage (****1234)".

        Example:
            >>> account.get_display_name()
            'Individual Brokerage (****1234)'
        """
        return f"{self.name} ({self.account_number_masked})"

    # -------------------------------------------------------------------------
    # Update Methods (From Provider Sync) - Return Result Types
    # -------------------------------------------------------------------------

    def update_balance(
        self,
        balance: Money,
        available_balance: Money | None = None,
    ) -> Result[None, str]:
        """Update balance from provider sync.

        Called when syncing account data from provider.
        Validates currency matches before updating.

        Args:
            balance: New current balance from provider.
            available_balance: Optional available balance if different.

        Returns:
            Success(None): Update successful.
            Failure(error): Currency mismatch.

        Side Effects (on success):
            - Updates balance
            - Updates available_balance
            - Updates updated_at timestamp
        """
        # Validate currency matches
        if balance.currency != self.currency:
            return Failure(
                error=f"Balance currency ({balance.currency}) must match "
                f"account currency ({self.currency})"
            )

        if (
            available_balance is not None
            and available_balance.currency != self.currency
        ):
            return Failure(
                error=f"Available balance currency ({available_balance.currency}) "
                f"must match account currency ({self.currency})"
            )

        self.balance = balance
        self.available_balance = available_balance
        self.updated_at = datetime.now(UTC)
        return Success(value=None)

    def update_from_provider(
        self,
        name: str | None = None,
        is_active: bool | None = None,
        provider_metadata: dict[str, Any] | None = None,
    ) -> Result[None, str]:
        """Update account details from provider sync.

        Called when syncing account metadata from provider.
        Only updates provided fields (None values ignored).

        Args:
            name: New account name from provider.
            is_active: Whether account is still active on provider.
            provider_metadata: Updated provider-specific data.

        Returns:
            Success(None): Update successful.
            Failure(error): Invalid name provided.

        Side Effects (on success):
            - Updates provided fields
            - Updates updated_at timestamp
        """
        if name is not None:
            if not name.strip():
                return Failure(error=AccountError.INVALID_ACCOUNT_NAME)
            self.name = name

        if is_active is not None:
            self.is_active = is_active

        if provider_metadata is not None:
            self.provider_metadata = provider_metadata

        self.updated_at = datetime.now(UTC)
        return Success(value=None)

    def mark_synced(self) -> Result[None, str]:
        """Record successful sync timestamp.

        Called after successful data synchronization with provider.

        Returns:
            Success(None): Always succeeds.

        Side Effects:
            - Updates last_synced_at to current time
            - Updates updated_at timestamp
        """
        now = datetime.now(UTC)
        self.last_synced_at = now
        self.updated_at = now
        return Success(value=None)

    def deactivate(self) -> Result[None, str]:
        """Mark account as inactive.

        Called when account is removed from provider or user
        requests account removal.

        Returns:
            Success(None): Always succeeds.

        Side Effects:
            - Sets is_active to False
            - Updates updated_at timestamp
        """
        self.is_active = False
        self.updated_at = datetime.now(UTC)
        return Success(value=None)

    def activate(self) -> Result[None, str]:
        """Mark account as active.

        Called when previously inactive account becomes available again.

        Returns:
            Success(None): Always succeeds.

        Side Effects:
            - Sets is_active to True
            - Updates updated_at timestamp
        """
        self.is_active = True
        self.updated_at = datetime.now(UTC)
        return Success(value=None)
