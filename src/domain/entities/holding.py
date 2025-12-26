"""Holding (Position) domain entity.

Represents a current portfolio position in an investment account.
Holdings are synced from providers and represent what the user currently owns.

Architecture:
    - Pure domain entity (no infrastructure dependencies)
    - Read-only from Dashtam perspective (synced from provider)
    - Updated during account/holdings sync operations
    - NO domain events (sync operations handled at application layer)

Reference:
    - docs/architecture/holding-domain-model.md

Usage:
    from uuid_extensions import uuid7
    from src.domain.entities import Holding
    from src.domain.enums import AssetType
    from src.domain.value_objects import Money
    from decimal import Decimal

    holding = Holding(
        id=uuid7(),
        account_id=account.id,
        provider_holding_id="SCHWAB-AAPL-123",
        symbol="AAPL",
        security_name="Apple Inc.",
        asset_type=AssetType.EQUITY,
        quantity=Decimal("100"),
        cost_basis=Money(Decimal("15000.00"), "USD"),
        market_value=Money(Decimal("17500.00"), "USD"),
        currency="USD",
    )
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.domain.enums.asset_type import AssetType
from src.domain.value_objects.money import Money


@dataclass
class Holding:
    """Investment holding (position) in an account.

    Represents a current security position synced from a provider.
    Holdings show what the user currently owns in their investment accounts.

    Provider Agnostic:
        Holding structure works for any brokerage provider (Schwab, Fidelity, etc.).
        Provider-specific data stored in provider_metadata.

    Financial Precision:
        All monetary values use Money value object with Decimal precision.
        Never store money as float.

    Read-Only Nature:
        Holdings are synced FROM providers - Dashtam doesn't modify positions.
        Users buy/sell through their brokerage, then we sync the result.

    Attributes:
        id: Unique holding identifier (internal).
        account_id: FK to Account this holding belongs to.
        provider_holding_id: Provider's unique identifier for this position.
        symbol: Security ticker symbol (e.g., "AAPL", "TSLA").
        security_name: Full security name (e.g., "Apple Inc.").
        asset_type: Type of security (EQUITY, ETF, OPTION, etc.).
        quantity: Number of shares/units held.
        cost_basis: Total cost paid for this position.
        market_value: Current market value of the position.
        currency: ISO 4217 currency code.
        average_price: Average price per share (cost_basis / quantity).
        current_price: Current market price per share.
        unrealized_gain_loss: market_value - cost_basis.
        unrealized_gain_loss_percent: Percentage gain/loss.
        is_active: Whether position is still held (quantity > 0).
        last_synced_at: Last successful sync timestamp.
        provider_metadata: Provider-specific data (unstructured).
        created_at: Record creation timestamp.
        updated_at: Last modification timestamp.

    Example:
        >>> holding = Holding(
        ...     id=uuid7(),
        ...     account_id=account.id,
        ...     provider_holding_id="SCHWAB-AAPL-123",
        ...     symbol="AAPL",
        ...     security_name="Apple Inc.",
        ...     asset_type=AssetType.EQUITY,
        ...     quantity=Decimal("100"),
        ...     cost_basis=Money(Decimal("15000.00"), "USD"),
        ...     market_value=Money(Decimal("17500.00"), "USD"),
        ...     currency="USD",
        ... )
        >>> holding.unrealized_gain_loss.amount
        Decimal('2500.00')
        >>> holding.unrealized_gain_loss_percent
        Decimal('16.67')
    """

    # =========================================================================
    # Required Fields
    # =========================================================================

    id: UUID
    """Unique holding identifier (internal)."""

    account_id: UUID
    """FK to Account this holding belongs to."""

    provider_holding_id: str
    """Provider's unique identifier for this position.

    Used for deduplication during sync operations. Format varies by provider:
    - Schwab: Account number + symbol combination
    - Other providers may use different formats
    """

    symbol: str
    """Security ticker symbol (e.g., "AAPL", "TSLA", "BTC-USD")."""

    security_name: str
    """Full security name (e.g., "Apple Inc.")."""

    asset_type: AssetType
    """Type of security (EQUITY, ETF, OPTION, etc.)."""

    quantity: Decimal
    """Number of shares/units held.

    Precision: Up to 8 decimal places for fractional shares/crypto.
    """

    cost_basis: Money
    """Total cost paid for this position.

    Includes purchase price + commissions. Used to calculate gain/loss.
    """

    market_value: Money
    """Current market value of the position.

    Calculated as: quantity * current_price
    """

    currency: str
    """ISO 4217 currency code (e.g., "USD")."""

    # =========================================================================
    # Optional Fields
    # =========================================================================

    average_price: Money | None = None
    """Average price per share (cost_basis / quantity).

    May be provided by provider or calculated.
    """

    current_price: Money | None = None
    """Current market price per share.

    Used for market_value calculation.
    """

    is_active: bool = True
    """Whether position is still held (quantity > 0)."""

    last_synced_at: datetime | None = None
    """Last successful sync timestamp."""

    provider_metadata: dict[str, Any] | None = None
    """Provider-specific data.

    Preserves the original provider API response for:
    - Debugging sync issues
    - Future feature additions (without re-sync)
    - Additional position details (lot info, etc.)
    """

    # =========================================================================
    # Timestamps
    # =========================================================================

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    """Record creation timestamp."""

    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    """Last modification timestamp."""

    # =========================================================================
    # Validation
    # =========================================================================

    def __post_init__(self) -> None:
        """Validate holding after initialization.

        Raises:
            ValueError: If required fields are invalid.
        """
        # Validate provider_holding_id
        if not self.provider_holding_id or not self.provider_holding_id.strip():
            raise ValueError("Provider holding ID cannot be empty")

        # Validate symbol
        if not self.symbol or not self.symbol.strip():
            raise ValueError("Symbol cannot be empty")

        # Validate security_name
        if not self.security_name or not self.security_name.strip():
            raise ValueError("Security name cannot be empty")

        # Validate quantity is non-negative
        if self.quantity < 0:
            raise ValueError("Quantity cannot be negative")

        # Validate currency consistency with cost_basis
        if self.cost_basis.currency != self.currency.upper():
            raise ValueError(
                f"Cost basis currency ({self.cost_basis.currency}) must match "
                f"holding currency ({self.currency})"
            )

        # Validate currency consistency with market_value
        if self.market_value.currency != self.currency.upper():
            raise ValueError(
                f"Market value currency ({self.market_value.currency}) must match "
                f"holding currency ({self.currency})"
            )

        # Validate optional prices match currency if present
        if self.average_price is not None:
            if self.average_price.currency != self.currency.upper():
                raise ValueError(
                    f"Average price currency ({self.average_price.currency}) must "
                    f"match holding currency ({self.currency})"
                )

        if self.current_price is not None:
            if self.current_price.currency != self.currency.upper():
                raise ValueError(
                    f"Current price currency ({self.current_price.currency}) must "
                    f"match holding currency ({self.currency})"
                )

        # Normalize currency to uppercase
        object.__setattr__(self, "currency", self.currency.upper())

    # =========================================================================
    # Computed Properties
    # =========================================================================

    @property
    def unrealized_gain_loss(self) -> Money:
        """Calculate unrealized gain/loss.

        Returns:
            Money: market_value - cost_basis (positive = gain, negative = loss).

        Example:
            >>> holding.unrealized_gain_loss.amount
            Decimal('2500.00')
        """
        gain_loss = self.market_value.amount - self.cost_basis.amount
        return Money(amount=gain_loss, currency=self.currency)

    @property
    def unrealized_gain_loss_percent(self) -> Decimal:
        """Calculate unrealized gain/loss as percentage.

        Returns:
            Decimal: Percentage gain/loss (e.g., 16.67 for 16.67% gain).
            Returns 0 if cost_basis is 0.

        Example:
            >>> holding.unrealized_gain_loss_percent
            Decimal('16.67')
        """
        if self.cost_basis.amount == 0:
            return Decimal("0")

        percent = (self.unrealized_gain_loss.amount / self.cost_basis.amount) * 100
        return percent.quantize(Decimal("0.01"))

    # =========================================================================
    # Query Methods
    # =========================================================================

    def is_profitable(self) -> bool:
        """Check if position has unrealized gain.

        Returns:
            True if market_value > cost_basis.
        """
        return self.market_value.amount > self.cost_basis.amount

    def is_equity(self) -> bool:
        """Check if this is an equity (stock) holding.

        Returns:
            True if asset_type is EQUITY.
        """
        return self.asset_type == AssetType.EQUITY

    def is_etf(self) -> bool:
        """Check if this is an ETF holding.

        Returns:
            True if asset_type is ETF.
        """
        return self.asset_type == AssetType.ETF

    def is_option(self) -> bool:
        """Check if this is an options holding.

        Returns:
            True if asset_type is OPTION.
        """
        return self.asset_type == AssetType.OPTION

    def is_crypto(self) -> bool:
        """Check if this is a cryptocurrency holding.

        Returns:
            True if asset_type is CRYPTOCURRENCY.
        """
        return self.asset_type == AssetType.CRYPTOCURRENCY

    def has_position(self) -> bool:
        """Check if there's an actual position (quantity > 0).

        Returns:
            True if quantity is greater than 0.
        """
        return self.quantity > 0

    # =========================================================================
    # Update Methods (From Provider Sync)
    # =========================================================================

    def update_from_sync(
        self,
        quantity: Decimal,
        cost_basis: Money,
        market_value: Money,
        current_price: Money | None = None,
        provider_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Update holding from provider sync.

        Called when syncing holding data from provider.

        Args:
            quantity: Updated quantity from provider.
            cost_basis: Updated cost basis from provider.
            market_value: Updated market value from provider.
            current_price: Optional current price per share.
            provider_metadata: Optional provider-specific data.

        Side Effects:
            - Updates quantity, cost_basis, market_value
            - Updates current_price if provided
            - Updates provider_metadata if provided
            - Updates last_synced_at and updated_at timestamps
            - Sets is_active based on quantity
        """
        self.quantity = quantity
        self.cost_basis = cost_basis
        self.market_value = market_value

        if current_price is not None:
            self.current_price = current_price

        if provider_metadata is not None:
            self.provider_metadata = provider_metadata

        # Update activity status based on quantity
        self.is_active = quantity > 0

        # Update timestamps
        now = datetime.now(UTC)
        self.last_synced_at = now
        self.updated_at = now

    def mark_synced(self) -> None:
        """Record successful sync timestamp.

        Called after successful data synchronization with provider.

        Side Effects:
            - Updates last_synced_at to current time
            - Updates updated_at timestamp
        """
        now = datetime.now(UTC)
        self.last_synced_at = now
        self.updated_at = now

    def deactivate(self) -> None:
        """Mark holding as inactive (sold).

        Called when position is closed (quantity becomes 0).

        Side Effects:
            - Sets is_active to False
            - Updates updated_at timestamp
        """
        self.is_active = False
        self.updated_at = datetime.now(UTC)
