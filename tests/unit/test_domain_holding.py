"""Unit tests for Holding domain entity.

Tests cover:
- Entity creation with valid data
- Validation errors for invalid data
- Computed properties (gain/loss calculations)
- Query methods (is_profitable, is_equity, etc.)
- Update methods (update_from_sync, mark_synced, deactivate)

Architecture:
- Unit tests for domain entity (no database, no I/O)
- Tests business rules defined in entity
- Uses pytest parameterization for edge cases
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from uuid_extensions import uuid7

from src.domain.entities.holding import Holding
from src.domain.enums.asset_type import AssetType
from src.domain.value_objects.money import Money


# =============================================================================
# Test Fixtures
# =============================================================================


def create_test_holding(
    holding_id=None,
    account_id=None,
    provider_holding_id="SCHWAB-AAPL-123",
    symbol="AAPL",
    security_name="Apple Inc.",
    asset_type=AssetType.EQUITY,
    quantity=Decimal("100"),
    cost_basis=None,
    market_value=None,
    currency="USD",
    **kwargs,
) -> Holding:
    """Create a test Holding with sensible defaults."""
    return Holding(
        id=holding_id or uuid7(),
        account_id=account_id or uuid7(),
        provider_holding_id=provider_holding_id,
        symbol=symbol,
        security_name=security_name,
        asset_type=asset_type,
        quantity=quantity,
        cost_basis=cost_basis or Money(Decimal("15000.00"), currency),
        market_value=market_value or Money(Decimal("17500.00"), currency),
        currency=currency,
        **kwargs,
    )


# =============================================================================
# Test Classes
# =============================================================================


class TestHoldingCreation:
    """Test Holding entity creation."""

    def test_create_minimal_holding(self):
        """Test creating holding with required fields only."""
        holding_id = uuid7()
        account_id = uuid7()

        holding = Holding(
            id=holding_id,
            account_id=account_id,
            provider_holding_id="SCHWAB-AAPL-123",
            symbol="AAPL",
            security_name="Apple Inc.",
            asset_type=AssetType.EQUITY,
            quantity=Decimal("100"),
            cost_basis=Money(Decimal("15000.00"), "USD"),
            market_value=Money(Decimal("17500.00"), "USD"),
            currency="USD",
        )

        assert holding.id == holding_id
        assert holding.account_id == account_id
        assert holding.provider_holding_id == "SCHWAB-AAPL-123"
        assert holding.symbol == "AAPL"
        assert holding.security_name == "Apple Inc."
        assert holding.asset_type == AssetType.EQUITY
        assert holding.quantity == Decimal("100")
        assert holding.cost_basis.amount == Decimal("15000.00")
        assert holding.market_value.amount == Decimal("17500.00")
        assert holding.currency == "USD"
        # Defaults
        assert holding.is_active is True
        assert holding.average_price is None
        assert holding.current_price is None
        assert holding.last_synced_at is None
        assert holding.provider_metadata is None

    def test_create_full_holding(self):
        """Test creating holding with all fields."""
        holding_id = uuid7()
        account_id = uuid7()
        now = datetime.now(UTC)

        holding = Holding(
            id=holding_id,
            account_id=account_id,
            provider_holding_id="SCHWAB-TSLA-456",
            symbol="TSLA",
            security_name="Tesla, Inc.",
            asset_type=AssetType.EQUITY,
            quantity=Decimal("50.5"),
            cost_basis=Money(Decimal("10000.00"), "USD"),
            market_value=Money(Decimal("12525.00"), "USD"),
            currency="USD",
            average_price=Money(Decimal("198.02"), "USD"),
            current_price=Money(Decimal("248.02"), "USD"),
            is_active=True,
            last_synced_at=now,
            provider_metadata={"lot_id": "LOT-123"},
            created_at=now,
            updated_at=now,
        )

        assert holding.symbol == "TSLA"
        assert holding.quantity == Decimal("50.5")
        assert holding.average_price.amount == Decimal("198.02")
        assert holding.current_price.amount == Decimal("248.02")
        assert holding.last_synced_at == now
        assert holding.provider_metadata == {"lot_id": "LOT-123"}

    def test_currency_normalized_to_uppercase(self):
        """Test that currency is normalized to uppercase."""
        holding = create_test_holding(currency="usd")
        assert holding.currency == "USD"


class TestHoldingValidation:
    """Test Holding validation rules."""

    def test_empty_provider_holding_id_raises_error(self):
        """Test that empty provider_holding_id raises ValueError."""
        with pytest.raises(ValueError, match="Provider holding ID cannot be empty"):
            create_test_holding(provider_holding_id="")

    def test_whitespace_provider_holding_id_raises_error(self):
        """Test that whitespace-only provider_holding_id raises ValueError."""
        with pytest.raises(ValueError, match="Provider holding ID cannot be empty"):
            create_test_holding(provider_holding_id="   ")

    def test_empty_symbol_raises_error(self):
        """Test that empty symbol raises ValueError."""
        with pytest.raises(ValueError, match="Symbol cannot be empty"):
            create_test_holding(symbol="")

    def test_empty_security_name_raises_error(self):
        """Test that empty security_name raises ValueError."""
        with pytest.raises(ValueError, match="Security name cannot be empty"):
            create_test_holding(security_name="")

    def test_negative_quantity_raises_error(self):
        """Test that negative quantity raises ValueError."""
        with pytest.raises(ValueError, match="Quantity cannot be negative"):
            create_test_holding(quantity=Decimal("-10"))

    def test_zero_quantity_is_valid(self):
        """Test that zero quantity is valid (closed position)."""
        holding = create_test_holding(quantity=Decimal("0"))
        assert holding.quantity == Decimal("0")

    def test_cost_basis_currency_mismatch_raises_error(self):
        """Test that cost_basis currency mismatch raises ValueError."""
        with pytest.raises(ValueError, match="Cost basis currency"):
            Holding(
                id=uuid7(),
                account_id=uuid7(),
                provider_holding_id="TEST-123",
                symbol="AAPL",
                security_name="Apple Inc.",
                asset_type=AssetType.EQUITY,
                quantity=Decimal("100"),
                cost_basis=Money(Decimal("15000.00"), "EUR"),  # Wrong currency
                market_value=Money(Decimal("17500.00"), "USD"),
                currency="USD",
            )

    def test_market_value_currency_mismatch_raises_error(self):
        """Test that market_value currency mismatch raises ValueError."""
        with pytest.raises(ValueError, match="Market value currency"):
            Holding(
                id=uuid7(),
                account_id=uuid7(),
                provider_holding_id="TEST-123",
                symbol="AAPL",
                security_name="Apple Inc.",
                asset_type=AssetType.EQUITY,
                quantity=Decimal("100"),
                cost_basis=Money(Decimal("15000.00"), "USD"),
                market_value=Money(Decimal("17500.00"), "EUR"),  # Wrong currency
                currency="USD",
            )

    def test_average_price_currency_mismatch_raises_error(self):
        """Test that average_price currency mismatch raises ValueError."""
        with pytest.raises(ValueError, match="Average price currency"):
            Holding(
                id=uuid7(),
                account_id=uuid7(),
                provider_holding_id="TEST-123",
                symbol="AAPL",
                security_name="Apple Inc.",
                asset_type=AssetType.EQUITY,
                quantity=Decimal("100"),
                cost_basis=Money(Decimal("15000.00"), "USD"),
                market_value=Money(Decimal("17500.00"), "USD"),
                currency="USD",
                average_price=Money(Decimal("150.00"), "EUR"),  # Wrong currency
            )

    def test_current_price_currency_mismatch_raises_error(self):
        """Test that current_price currency mismatch raises ValueError."""
        with pytest.raises(ValueError, match="Current price currency"):
            Holding(
                id=uuid7(),
                account_id=uuid7(),
                provider_holding_id="TEST-123",
                symbol="AAPL",
                security_name="Apple Inc.",
                asset_type=AssetType.EQUITY,
                quantity=Decimal("100"),
                cost_basis=Money(Decimal("15000.00"), "USD"),
                market_value=Money(Decimal("17500.00"), "USD"),
                currency="USD",
                current_price=Money(Decimal("175.00"), "EUR"),  # Wrong currency
            )


class TestHoldingComputedProperties:
    """Test Holding computed properties."""

    def test_unrealized_gain_loss_positive(self):
        """Test unrealized gain when market_value > cost_basis."""
        holding = create_test_holding(
            cost_basis=Money(Decimal("10000.00"), "USD"),
            market_value=Money(Decimal("12500.00"), "USD"),
        )

        assert holding.unrealized_gain_loss.amount == Decimal("2500.00")
        assert holding.unrealized_gain_loss.currency == "USD"

    def test_unrealized_gain_loss_negative(self):
        """Test unrealized loss when market_value < cost_basis."""
        holding = create_test_holding(
            cost_basis=Money(Decimal("10000.00"), "USD"),
            market_value=Money(Decimal("8000.00"), "USD"),
        )

        assert holding.unrealized_gain_loss.amount == Decimal("-2000.00")

    def test_unrealized_gain_loss_zero(self):
        """Test zero gain/loss when market_value equals cost_basis."""
        holding = create_test_holding(
            cost_basis=Money(Decimal("10000.00"), "USD"),
            market_value=Money(Decimal("10000.00"), "USD"),
        )

        assert holding.unrealized_gain_loss.amount == Decimal("0.00")

    def test_unrealized_gain_loss_percent_positive(self):
        """Test percentage gain calculation."""
        holding = create_test_holding(
            cost_basis=Money(Decimal("10000.00"), "USD"),
            market_value=Money(Decimal("11667.00"), "USD"),
        )

        # (11667 - 10000) / 10000 * 100 = 16.67%
        assert holding.unrealized_gain_loss_percent == Decimal("16.67")

    def test_unrealized_gain_loss_percent_negative(self):
        """Test percentage loss calculation."""
        holding = create_test_holding(
            cost_basis=Money(Decimal("10000.00"), "USD"),
            market_value=Money(Decimal("8500.00"), "USD"),
        )

        # (8500 - 10000) / 10000 * 100 = -15.00%
        assert holding.unrealized_gain_loss_percent == Decimal("-15.00")

    def test_unrealized_gain_loss_percent_zero_cost_basis(self):
        """Test percentage when cost_basis is zero (avoid division by zero)."""
        holding = create_test_holding(
            cost_basis=Money(Decimal("0"), "USD"),
            market_value=Money(Decimal("1000.00"), "USD"),
        )

        assert holding.unrealized_gain_loss_percent == Decimal("0")


class TestHoldingQueryMethods:
    """Test Holding query methods."""

    def test_is_profitable_true(self):
        """Test is_profitable returns True when market_value > cost_basis."""
        holding = create_test_holding(
            cost_basis=Money(Decimal("10000.00"), "USD"),
            market_value=Money(Decimal("12000.00"), "USD"),
        )
        assert holding.is_profitable() is True

    def test_is_profitable_false(self):
        """Test is_profitable returns False when market_value <= cost_basis."""
        holding = create_test_holding(
            cost_basis=Money(Decimal("10000.00"), "USD"),
            market_value=Money(Decimal("8000.00"), "USD"),
        )
        assert holding.is_profitable() is False

    def test_is_equity(self):
        """Test is_equity returns True for EQUITY asset type."""
        holding = create_test_holding(asset_type=AssetType.EQUITY)
        assert holding.is_equity() is True
        assert holding.is_etf() is False

    def test_is_etf(self):
        """Test is_etf returns True for ETF asset type."""
        holding = create_test_holding(asset_type=AssetType.ETF)
        assert holding.is_etf() is True
        assert holding.is_equity() is False

    def test_is_option(self):
        """Test is_option returns True for OPTION asset type."""
        holding = create_test_holding(asset_type=AssetType.OPTION)
        assert holding.is_option() is True
        assert holding.is_equity() is False

    def test_is_crypto(self):
        """Test is_crypto returns True for CRYPTOCURRENCY asset type."""
        holding = create_test_holding(asset_type=AssetType.CRYPTOCURRENCY)
        assert holding.is_crypto() is True
        assert holding.is_equity() is False

    def test_has_position_true(self):
        """Test has_position returns True when quantity > 0."""
        holding = create_test_holding(quantity=Decimal("100"))
        assert holding.has_position() is True

    def test_has_position_false(self):
        """Test has_position returns False when quantity is 0."""
        holding = create_test_holding(quantity=Decimal("0"))
        assert holding.has_position() is False


class TestHoldingUpdateMethods:
    """Test Holding update methods."""

    def test_update_from_sync(self):
        """Test update_from_sync updates all relevant fields."""
        holding = create_test_holding()
        before_update = holding.updated_at

        new_quantity = Decimal("150")
        new_cost_basis = Money(Decimal("22500.00"), "USD")
        new_market_value = Money(Decimal("26250.00"), "USD")
        new_current_price = Money(Decimal("175.00"), "USD")
        new_metadata = {"lot_id": "NEW-LOT"}

        holding.update_from_sync(
            quantity=new_quantity,
            cost_basis=new_cost_basis,
            market_value=new_market_value,
            current_price=new_current_price,
            provider_metadata=new_metadata,
        )

        assert holding.quantity == new_quantity
        assert holding.cost_basis == new_cost_basis
        assert holding.market_value == new_market_value
        assert holding.current_price == new_current_price
        assert holding.provider_metadata == new_metadata
        assert holding.is_active is True
        assert holding.last_synced_at is not None
        assert holding.updated_at > before_update

    def test_update_from_sync_zero_quantity_deactivates(self):
        """Test update_from_sync sets is_active=False when quantity is 0."""
        holding = create_test_holding()
        assert holding.is_active is True

        holding.update_from_sync(
            quantity=Decimal("0"),
            cost_basis=Money(Decimal("0"), "USD"),
            market_value=Money(Decimal("0"), "USD"),
        )

        assert holding.quantity == Decimal("0")
        assert holding.is_active is False

    def test_mark_synced(self):
        """Test mark_synced updates timestamps."""
        holding = create_test_holding()
        assert holding.last_synced_at is None
        before_update = holding.updated_at

        holding.mark_synced()

        assert holding.last_synced_at is not None
        assert holding.updated_at >= before_update

    def test_deactivate(self):
        """Test deactivate sets is_active to False."""
        holding = create_test_holding()
        assert holding.is_active is True
        before_update = holding.updated_at

        holding.deactivate()

        assert holding.is_active is False
        assert holding.updated_at >= before_update


class TestHoldingAssetTypes:
    """Test Holding with different asset types."""

    @pytest.mark.parametrize(
        "asset_type",
        list(AssetType),
    )
    def test_create_with_all_asset_types(self, asset_type):
        """Test creating holding with each asset type."""
        holding = create_test_holding(asset_type=asset_type)
        assert holding.asset_type == asset_type
