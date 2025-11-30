"""Unit tests for Money value object.

Tests cover:
- Money creation with validation
- Arithmetic operations (add, sub, mul, neg, abs)
- Comparison operations (lt, le, gt, ge)
- Query methods (is_positive, is_negative, is_zero)
- Factory methods (zero, from_cents)
- Currency validation
- CurrencyMismatchError handling

Architecture:
- Unit tests for domain value object (no dependencies)
- Tests immutability and precision requirements
- Validates currency safety for cross-currency operations
"""

from decimal import Decimal

import pytest

from src.domain.value_objects.money import (
    VALID_CURRENCIES,
    CurrencyMismatchError,
    Money,
    validate_currency,
)


# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


def create_money(
    amount: str | Decimal = "100.00",
    currency: str = "USD",
) -> Money:
    """Helper to create Money instances for testing."""
    if isinstance(amount, str):
        amount = Decimal(amount)
    return Money(amount, currency)


# =============================================================================
# Currency Validation Tests
# =============================================================================


@pytest.mark.unit
class TestCurrencyValidation:
    """Test currency validation function."""

    def test_validate_currency_normalizes_to_uppercase(self):
        """Test currency codes are normalized to uppercase."""
        assert validate_currency("usd") == "USD"
        assert validate_currency("eur") == "EUR"
        assert validate_currency("Gbp") == "GBP"

    def test_validate_currency_strips_whitespace(self):
        """Test whitespace is stripped from currency codes."""
        assert validate_currency("  USD  ") == "USD"
        assert validate_currency("\tEUR\n") == "EUR"

    def test_validate_currency_accepts_valid_codes(self):
        """Test all valid ISO 4217 codes are accepted."""
        for code in VALID_CURRENCIES:
            assert validate_currency(code) == code

    def test_validate_currency_rejects_empty_string(self):
        """Test empty string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_currency("")
        assert "empty" in str(exc_info.value).lower()

    def test_validate_currency_rejects_none(self):
        """Test None raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_currency(None)  # type: ignore
        assert "empty" in str(exc_info.value).lower()

    def test_validate_currency_rejects_wrong_length(self):
        """Test codes not exactly 3 chars raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_currency("US")
        assert "3 characters" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            validate_currency("USDD")
        assert "3 characters" in str(exc_info.value)

    def test_validate_currency_rejects_invalid_codes(self):
        """Test invalid currency codes raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_currency("XYZ")
        assert "Invalid currency code" in str(exc_info.value)


# =============================================================================
# Money Creation Tests
# =============================================================================


@pytest.mark.unit
class TestMoneyCreation:
    """Test Money value object creation."""

    def test_money_created_with_decimal_and_currency(self):
        """Test Money can be created with Decimal amount and currency."""
        money = Money(Decimal("100.50"), "USD")
        assert money.amount == Decimal("100.50")
        assert money.currency == "USD"

    def test_money_normalizes_currency_to_uppercase(self):
        """Test currency is normalized to uppercase."""
        money = Money(Decimal("100"), "usd")
        assert money.currency == "USD"

    def test_money_accepts_integer_amount(self):
        """Test Money accepts integer amounts (converts to Decimal)."""
        money = Money(100, "USD")  # type: ignore
        assert money.amount == Decimal("100")

    def test_money_accepts_float_amount_with_warning(self):
        """Test Money accepts float (converts to Decimal via string)."""
        # Note: This works but should be avoided
        money = Money(100.5, "USD")  # type: ignore
        assert money.amount == Decimal("100.5")

    def test_money_is_frozen(self):
        """Test Money is immutable (frozen dataclass)."""
        money = create_money()
        with pytest.raises(AttributeError):
            money.amount = Decimal("999")  # type: ignore

    def test_money_rejects_nan_amount(self):
        """Test NaN amount raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Money(Decimal("NaN"), "USD")
        assert "NaN" in str(exc_info.value)

    def test_money_rejects_infinity_amount(self):
        """Test Infinity amount raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Money(Decimal("Infinity"), "USD")
        assert "Infinite" in str(exc_info.value)

    def test_money_rejects_invalid_currency(self):
        """Test invalid currency raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Money(Decimal("100"), "XYZ")
        assert "Invalid currency code" in str(exc_info.value)

    def test_money_accepts_negative_amount(self):
        """Test Money can represent negative values."""
        money = Money(Decimal("-50.00"), "USD")
        assert money.amount == Decimal("-50.00")

    def test_money_accepts_zero_amount(self):
        """Test Money can represent zero."""
        money = Money(Decimal("0"), "USD")
        assert money.amount == Decimal("0")


# =============================================================================
# Arithmetic Operation Tests
# =============================================================================


@pytest.mark.unit
class TestMoneyAddition:
    """Test Money addition operations."""

    def test_add_same_currency(self):
        """Test adding two Money values with same currency."""
        a = create_money("100.00", "USD")
        b = create_money("50.50", "USD")
        result = a + b
        assert result.amount == Decimal("150.50")
        assert result.currency == "USD"

    def test_add_returns_new_instance(self):
        """Test addition returns new Money instance."""
        a = create_money("100.00")
        b = create_money("50.00")
        result = a + b
        assert result is not a
        assert result is not b
        assert a.amount == Decimal("100.00")  # Original unchanged

    def test_add_different_currency_raises_error(self):
        """Test adding different currencies raises CurrencyMismatchError."""
        usd = create_money("100.00", "USD")
        eur = create_money("50.00", "EUR")
        with pytest.raises(CurrencyMismatchError) as exc_info:
            usd + eur
        assert exc_info.value.currency1 == "USD"
        assert exc_info.value.currency2 == "EUR"

    def test_add_non_money_returns_not_implemented(self):
        """Test adding non-Money returns NotImplemented."""
        money = create_money("100.00")
        result = money.__add__(100)  # type: ignore
        assert result is NotImplemented


@pytest.mark.unit
class TestMoneySubtraction:
    """Test Money subtraction operations."""

    def test_sub_same_currency(self):
        """Test subtracting two Money values with same currency."""
        a = create_money("100.00", "USD")
        b = create_money("30.50", "USD")
        result = a - b
        assert result.amount == Decimal("69.50")
        assert result.currency == "USD"

    def test_sub_can_result_in_negative(self):
        """Test subtraction can result in negative Money."""
        a = create_money("50.00", "USD")
        b = create_money("100.00", "USD")
        result = a - b
        assert result.amount == Decimal("-50.00")

    def test_sub_different_currency_raises_error(self):
        """Test subtracting different currencies raises CurrencyMismatchError."""
        usd = create_money("100.00", "USD")
        gbp = create_money("50.00", "GBP")
        with pytest.raises(CurrencyMismatchError):
            usd - gbp


@pytest.mark.unit
class TestMoneyMultiplication:
    """Test Money multiplication operations."""

    def test_mul_by_integer(self):
        """Test multiplying Money by integer."""
        money = create_money("100.00", "USD")
        result = money * 3
        assert result.amount == Decimal("300.00")
        assert result.currency == "USD"

    def test_mul_by_decimal(self):
        """Test multiplying Money by Decimal."""
        money = create_money("100.00", "USD")
        result = money * Decimal("1.5")
        assert result.amount == Decimal("150.00")

    def test_mul_by_zero(self):
        """Test multiplying Money by zero."""
        money = create_money("100.00", "USD")
        result = money * 0
        assert result.amount == Decimal("0")

    def test_mul_by_negative(self):
        """Test multiplying Money by negative number."""
        money = create_money("100.00", "USD")
        result = money * -1
        assert result.amount == Decimal("-100.00")

    def test_rmul_by_integer(self):
        """Test reverse multiplication (integer * Money)."""
        money = create_money("100.00", "USD")
        result = 3 * money
        assert result.amount == Decimal("300.00")


@pytest.mark.unit
class TestMoneyNegationAndAbsolute:
    """Test Money negation and absolute value operations."""

    def test_neg_positive_money(self):
        """Test negating positive Money."""
        money = create_money("100.00", "USD")
        result = -money
        assert result.amount == Decimal("-100.00")

    def test_neg_negative_money(self):
        """Test negating negative Money."""
        money = create_money("-100.00", "USD")
        result = -money
        assert result.amount == Decimal("100.00")

    def test_abs_positive_money(self):
        """Test abs of positive Money."""
        money = create_money("100.00", "USD")
        result = abs(money)
        assert result.amount == Decimal("100.00")

    def test_abs_negative_money(self):
        """Test abs of negative Money."""
        money = create_money("-100.00", "USD")
        result = abs(money)
        assert result.amount == Decimal("100.00")


# =============================================================================
# Comparison Operation Tests
# =============================================================================


@pytest.mark.unit
class TestMoneyComparison:
    """Test Money comparison operations."""

    def test_lt_same_currency(self):
        """Test less than comparison with same currency."""
        a = create_money("50.00", "USD")
        b = create_money("100.00", "USD")
        assert (a < b) is True
        assert (b < a) is False
        assert (a < a) is False

    def test_le_same_currency(self):
        """Test less than or equal comparison."""
        a = create_money("50.00", "USD")
        b = create_money("100.00", "USD")
        c = create_money("50.00", "USD")
        assert (a <= b) is True
        assert (a <= c) is True
        assert (b <= a) is False

    def test_gt_same_currency(self):
        """Test greater than comparison with same currency."""
        a = create_money("100.00", "USD")
        b = create_money("50.00", "USD")
        assert (a > b) is True
        assert (b > a) is False

    def test_ge_same_currency(self):
        """Test greater than or equal comparison."""
        a = create_money("100.00", "USD")
        b = create_money("50.00", "USD")
        c = create_money("100.00", "USD")
        assert (a >= b) is True
        assert (a >= c) is True
        assert (b >= a) is False

    def test_comparison_different_currency_raises_error(self):
        """Test comparison between different currencies raises error."""
        usd = create_money("100.00", "USD")
        eur = create_money("100.00", "EUR")
        with pytest.raises(CurrencyMismatchError):
            usd < eur
        with pytest.raises(CurrencyMismatchError):
            usd <= eur
        with pytest.raises(CurrencyMismatchError):
            usd > eur
        with pytest.raises(CurrencyMismatchError):
            usd >= eur

    def test_equality_same_amount_and_currency(self):
        """Test equality for same amount and currency."""
        a = create_money("100.00", "USD")
        b = create_money("100.00", "USD")
        assert a == b

    def test_equality_different_amount(self):
        """Test inequality for different amounts."""
        a = create_money("100.00", "USD")
        b = create_money("99.99", "USD")
        assert a != b

    def test_equality_different_currency(self):
        """Test inequality for different currencies."""
        a = create_money("100.00", "USD")
        b = create_money("100.00", "EUR")
        assert a != b


# =============================================================================
# Query Method Tests
# =============================================================================


@pytest.mark.unit
class TestMoneyQueryMethods:
    """Test Money query methods."""

    def test_is_positive_true(self):
        """Test is_positive returns True for positive amount."""
        money = create_money("100.00")
        assert money.is_positive() is True

    def test_is_positive_false_for_zero(self):
        """Test is_positive returns False for zero."""
        money = create_money("0.00")
        assert money.is_positive() is False

    def test_is_positive_false_for_negative(self):
        """Test is_positive returns False for negative amount."""
        money = create_money("-100.00")
        assert money.is_positive() is False

    def test_is_negative_true(self):
        """Test is_negative returns True for negative amount."""
        money = create_money("-100.00")
        assert money.is_negative() is True

    def test_is_negative_false_for_zero(self):
        """Test is_negative returns False for zero."""
        money = create_money("0.00")
        assert money.is_negative() is False

    def test_is_negative_false_for_positive(self):
        """Test is_negative returns False for positive amount."""
        money = create_money("100.00")
        assert money.is_negative() is False

    def test_is_zero_true(self):
        """Test is_zero returns True for zero amount."""
        money = create_money("0.00")
        assert money.is_zero() is True

    def test_is_zero_true_for_negative_zero(self):
        """Test is_zero returns True for -0.00."""
        money = create_money("-0.00")
        assert money.is_zero() is True

    def test_is_zero_false_for_non_zero(self):
        """Test is_zero returns False for non-zero amount."""
        assert create_money("0.01").is_zero() is False
        assert create_money("-0.01").is_zero() is False


# =============================================================================
# Factory Method Tests
# =============================================================================


@pytest.mark.unit
class TestMoneyFactoryMethods:
    """Test Money factory methods."""

    def test_zero_default_currency(self):
        """Test zero factory with default USD currency."""
        money = Money.zero()
        assert money.amount == Decimal("0")
        assert money.currency == "USD"

    def test_zero_custom_currency(self):
        """Test zero factory with custom currency."""
        money = Money.zero("EUR")
        assert money.amount == Decimal("0")
        assert money.currency == "EUR"

    def test_from_cents_positive(self):
        """Test from_cents with positive cents."""
        money = Money.from_cents(1050, "USD")
        assert money.amount == Decimal("10.50")
        assert money.currency == "USD"

    def test_from_cents_zero(self):
        """Test from_cents with zero cents."""
        money = Money.from_cents(0, "USD")
        assert money.amount == Decimal("0.00")

    def test_from_cents_negative(self):
        """Test from_cents with negative cents."""
        money = Money.from_cents(-500, "USD")
        assert money.amount == Decimal("-5.00")

    def test_from_cents_large_amount(self):
        """Test from_cents with large amount."""
        money = Money.from_cents(100000000, "USD")  # $1,000,000
        assert money.amount == Decimal("1000000.00")

    def test_from_cents_default_currency(self):
        """Test from_cents uses USD by default."""
        money = Money.from_cents(100)
        assert money.currency == "USD"


# =============================================================================
# Edge Case Tests
# =============================================================================


@pytest.mark.unit
class TestMoneyEdgeCases:
    """Test Money edge cases and precision."""

    def test_decimal_precision_preserved(self):
        """Test Decimal precision is preserved in calculations."""
        # This would fail with float: 0.1 + 0.2 != 0.3
        a = Money(Decimal("0.1"), "USD")
        b = Money(Decimal("0.2"), "USD")
        result = a + b
        assert result.amount == Decimal("0.3")

    def test_very_small_amounts(self):
        """Test very small monetary amounts."""
        money = Money(Decimal("0.01"), "USD")
        result = money * Decimal("0.5")
        assert result.amount == Decimal("0.005")

    def test_very_large_amounts(self):
        """Test very large monetary amounts."""
        money = Money(Decimal("999999999999.99"), "USD")
        result = money + Money(Decimal("0.01"), "USD")
        assert result.amount == Decimal("1000000000000.00")

    def test_string_representation(self):
        """Test Money has useful string representation."""
        money = create_money("100.50", "USD")
        str_repr = str(money)
        assert "100.50" in str_repr
        assert "USD" in str_repr

    def test_hash_for_dict_key(self):
        """Test Money can be used as dict key (frozen dataclass)."""
        a = create_money("100.00", "USD")
        b = create_money("100.00", "USD")
        d = {a: "value"}
        assert d[b] == "value"  # Equal Money objects have same hash


# =============================================================================
# CurrencyMismatchError Tests
# =============================================================================


@pytest.mark.unit
class TestCurrencyMismatchError:
    """Test CurrencyMismatchError."""

    def test_error_stores_currencies(self):
        """Test error stores both currency codes."""
        error = CurrencyMismatchError("USD", "EUR")
        assert error.currency1 == "USD"
        assert error.currency2 == "EUR"

    def test_error_message_contains_currencies(self):
        """Test error message contains both currencies."""
        error = CurrencyMismatchError("USD", "EUR")
        assert "USD" in str(error)
        assert "EUR" in str(error)

    def test_error_is_value_error(self):
        """Test CurrencyMismatchError is a ValueError."""
        error = CurrencyMismatchError("USD", "EUR")
        assert isinstance(error, ValueError)
