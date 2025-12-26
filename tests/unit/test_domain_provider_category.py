"""Unit tests for ProviderCategory enum.

Tests cover:
- All enum values
- values() class method
- is_valid() class method
- supports_holdings() method

Architecture:
- Unit tests for domain enum (no database, no I/O)
- Tests business rules for category classification
"""

import pytest

from src.domain.enums.provider_category import ProviderCategory


class TestProviderCategoryValues:
    """Test ProviderCategory enum values."""

    def test_brokerage_value(self):
        """Test BROKERAGE enum value."""
        assert ProviderCategory.BROKERAGE.value == "brokerage"

    def test_bank_value(self):
        """Test BANK enum value."""
        assert ProviderCategory.BANK.value == "bank"

    def test_credit_card_value(self):
        """Test CREDIT_CARD enum value."""
        assert ProviderCategory.CREDIT_CARD.value == "credit_card"

    def test_loan_value(self):
        """Test LOAN enum value."""
        assert ProviderCategory.LOAN.value == "loan"

    def test_crypto_value(self):
        """Test CRYPTO enum value."""
        assert ProviderCategory.CRYPTO.value == "crypto"

    def test_aggregator_value(self):
        """Test AGGREGATOR enum value."""
        assert ProviderCategory.AGGREGATOR.value == "aggregator"

    def test_other_value(self):
        """Test OTHER enum value."""
        assert ProviderCategory.OTHER.value == "other"


class TestProviderCategoryClassMethods:
    """Test ProviderCategory class methods."""

    def test_values_returns_all_categories(self):
        """Test values() returns all category strings."""
        values = ProviderCategory.values()

        assert isinstance(values, list)
        assert len(values) == 7
        assert "brokerage" in values
        assert "bank" in values
        assert "credit_card" in values
        assert "loan" in values
        assert "crypto" in values
        assert "aggregator" in values
        assert "other" in values

    def test_is_valid_with_valid_categories(self):
        """Test is_valid() returns True for valid categories."""
        assert ProviderCategory.is_valid("brokerage") is True
        assert ProviderCategory.is_valid("bank") is True
        assert ProviderCategory.is_valid("credit_card") is True
        assert ProviderCategory.is_valid("loan") is True
        assert ProviderCategory.is_valid("crypto") is True
        assert ProviderCategory.is_valid("aggregator") is True
        assert ProviderCategory.is_valid("other") is True

    def test_is_valid_with_invalid_categories(self):
        """Test is_valid() returns False for invalid categories."""
        assert ProviderCategory.is_valid("invalid") is False
        assert ProviderCategory.is_valid("BROKERAGE") is False  # Case sensitive
        assert ProviderCategory.is_valid("") is False
        assert ProviderCategory.is_valid("broker") is False


class TestProviderCategorySupportsHoldings:
    """Test supports_holdings() method."""

    def test_brokerage_supports_holdings(self):
        """Test BROKERAGE supports holdings."""
        assert ProviderCategory.BROKERAGE.supports_holdings() is True

    def test_crypto_supports_holdings(self):
        """Test CRYPTO supports holdings."""
        assert ProviderCategory.CRYPTO.supports_holdings() is True

    def test_bank_does_not_support_holdings(self):
        """Test BANK does not support holdings."""
        assert ProviderCategory.BANK.supports_holdings() is False

    def test_credit_card_does_not_support_holdings(self):
        """Test CREDIT_CARD does not support holdings."""
        assert ProviderCategory.CREDIT_CARD.supports_holdings() is False

    def test_loan_does_not_support_holdings(self):
        """Test LOAN does not support holdings."""
        assert ProviderCategory.LOAN.supports_holdings() is False

    def test_aggregator_does_not_support_holdings(self):
        """Test AGGREGATOR does not support holdings."""
        assert ProviderCategory.AGGREGATOR.supports_holdings() is False

    def test_other_does_not_support_holdings(self):
        """Test OTHER does not support holdings."""
        assert ProviderCategory.OTHER.supports_holdings() is False


class TestProviderCategoryStringBehavior:
    """Test string enum behavior."""

    def test_category_is_string_subclass(self):
        """Test ProviderCategory is a string subclass."""
        category = ProviderCategory.BROKERAGE
        assert isinstance(category, str)
        assert category == "brokerage"

    @pytest.mark.parametrize(
        "category",
        list(ProviderCategory),
    )
    def test_all_categories_are_strings(self, category):
        """Test all categories behave as strings."""
        assert isinstance(category, str)
        assert category == category.value
