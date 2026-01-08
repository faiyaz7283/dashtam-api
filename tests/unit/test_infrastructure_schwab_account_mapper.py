"""Unit tests for SchwabAccountMapper.

Tests cover:
- Account type mapping (all Schwab types to Dashtam AccountType)
- Balance parsing (Decimal precision, edge cases)
- Account number masking
- Missing/invalid data handling
- Full account mapping integration

Architecture:
- Pure unit tests (no HTTP, no mocking needed)
- Tests mapper in isolation with raw dict input
- Verifies ProviderAccountData output
"""

from decimal import Decimal
from typing import Any

import pytest

from src.domain.enums.account_type import AccountType
from src.domain.protocols.provider_protocol import ProviderAccountData
from src.infrastructure.providers.schwab.mappers.account_mapper import (
    SCHWAB_ACCOUNT_TYPE_MAP,
    SchwabAccountMapper,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mapper() -> SchwabAccountMapper:
    """Create SchwabAccountMapper instance."""
    return SchwabAccountMapper()


def _build_schwab_account(
    *,
    account_number: str = "12345678",
    account_type: str = "INDIVIDUAL",
    account_name: str | None = "My Brokerage",
    liquidation_value: float | int = 50000.00,
    available_funds: float | int | None = 10000.00,
    cash_balance: float | int | None = None,
) -> dict[str, Any]:
    """Build a Schwab account JSON structure for testing."""
    current_balances: dict[str, Any] = {"liquidationValue": liquidation_value}
    if available_funds is not None:
        current_balances["availableFunds"] = available_funds
    if cash_balance is not None:
        current_balances["cashBalance"] = cash_balance

    securities_account: dict[str, Any] = {
        "type": account_type,
        "accountNumber": account_number,
        "currentBalances": current_balances,
    }
    if account_name is not None:
        securities_account["accountName"] = account_name

    return {"securitiesAccount": securities_account}


# =============================================================================
# Test: Account Type Mapping
# =============================================================================


class TestAccountTypeMapping:
    """Test Schwab account type to AccountType enum mapping."""

    def test_cash_maps_to_brokerage(self, mapper: SchwabAccountMapper):
        """CASH account type maps to BROKERAGE."""
        result = mapper._map_account_type("CASH")
        assert result == AccountType.BROKERAGE

    def test_margin_maps_to_brokerage(self, mapper: SchwabAccountMapper):
        """MARGIN account type maps to BROKERAGE."""
        result = mapper._map_account_type("MARGIN")
        assert result == AccountType.BROKERAGE

    def test_individual_maps_to_brokerage(self, mapper: SchwabAccountMapper):
        """INDIVIDUAL account type maps to BROKERAGE."""
        result = mapper._map_account_type("INDIVIDUAL")
        assert result == AccountType.BROKERAGE

    def test_joint_maps_to_brokerage(self, mapper: SchwabAccountMapper):
        """JOINT account type maps to BROKERAGE."""
        result = mapper._map_account_type("JOINT")
        assert result == AccountType.BROKERAGE

    def test_ira_maps_to_ira(self, mapper: SchwabAccountMapper):
        """IRA account type maps to IRA."""
        result = mapper._map_account_type("IRA")
        assert result == AccountType.IRA

    def test_traditional_ira_maps_to_ira(self, mapper: SchwabAccountMapper):
        """TRADITIONAL_IRA account type maps to IRA."""
        result = mapper._map_account_type("TRADITIONAL_IRA")
        assert result == AccountType.IRA

    def test_rollover_ira_maps_to_ira(self, mapper: SchwabAccountMapper):
        """ROLLOVER_IRA account type maps to IRA."""
        result = mapper._map_account_type("ROLLOVER_IRA")
        assert result == AccountType.IRA

    def test_sep_ira_maps_to_ira(self, mapper: SchwabAccountMapper):
        """SEP_IRA account type maps to IRA."""
        result = mapper._map_account_type("SEP_IRA")
        assert result == AccountType.IRA

    def test_simple_ira_maps_to_ira(self, mapper: SchwabAccountMapper):
        """SIMPLE_IRA account type maps to IRA."""
        result = mapper._map_account_type("SIMPLE_IRA")
        assert result == AccountType.IRA

    def test_roth_ira_maps_to_roth_ira(self, mapper: SchwabAccountMapper):
        """ROTH_IRA account type maps to ROTH_IRA."""
        result = mapper._map_account_type("ROTH_IRA")
        assert result == AccountType.ROTH_IRA

    def test_roth_maps_to_roth_ira(self, mapper: SchwabAccountMapper):
        """ROTH account type maps to ROTH_IRA."""
        result = mapper._map_account_type("ROTH")
        assert result == AccountType.ROTH_IRA

    def test_401k_maps_to_retirement_401k(self, mapper: SchwabAccountMapper):
        """401K account type maps to RETIREMENT_401K."""
        result = mapper._map_account_type("401K")
        assert result == AccountType.RETIREMENT_401K

    def test_roth_401k_maps_to_retirement_401k(self, mapper: SchwabAccountMapper):
        """ROTH_401K account type maps to RETIREMENT_401K."""
        result = mapper._map_account_type("ROTH_401K")
        assert result == AccountType.RETIREMENT_401K

    def test_403b_maps_to_retirement_403b(self, mapper: SchwabAccountMapper):
        """403B account type maps to RETIREMENT_403B."""
        result = mapper._map_account_type("403B")
        assert result == AccountType.RETIREMENT_403B

    def test_hsa_maps_to_hsa(self, mapper: SchwabAccountMapper):
        """HSA account type maps to HSA."""
        result = mapper._map_account_type("HSA")
        assert result == AccountType.HSA

    def test_trust_maps_to_brokerage(self, mapper: SchwabAccountMapper):
        """TRUST account type maps to BROKERAGE."""
        result = mapper._map_account_type("TRUST")
        assert result == AccountType.BROKERAGE

    def test_custodial_maps_to_brokerage(self, mapper: SchwabAccountMapper):
        """CUSTODIAL account type maps to BROKERAGE."""
        result = mapper._map_account_type("CUSTODIAL")
        assert result == AccountType.BROKERAGE

    def test_529_maps_to_other(self, mapper: SchwabAccountMapper):
        """529 education account maps to OTHER."""
        result = mapper._map_account_type("529")
        assert result == AccountType.OTHER

    def test_coverdell_maps_to_other(self, mapper: SchwabAccountMapper):
        """COVERDELL education account maps to OTHER."""
        result = mapper._map_account_type("COVERDELL")
        assert result == AccountType.OTHER

    def test_corporate_maps_to_brokerage(self, mapper: SchwabAccountMapper):
        """CORPORATE account type maps to BROKERAGE."""
        result = mapper._map_account_type("CORPORATE")
        assert result == AccountType.BROKERAGE

    def test_unknown_type_maps_to_other(self, mapper: SchwabAccountMapper):
        """Unknown account types default to OTHER."""
        result = mapper._map_account_type("UNKNOWN_TYPE")
        assert result == AccountType.OTHER

    def test_empty_type_maps_to_other(self, mapper: SchwabAccountMapper):
        """Empty account type defaults to OTHER."""
        result = mapper._map_account_type("")
        assert result == AccountType.OTHER

    def test_type_mapping_is_case_insensitive(self, mapper: SchwabAccountMapper):
        """Account type mapping should be case-insensitive."""
        assert mapper._map_account_type("ira") == AccountType.IRA
        assert mapper._map_account_type("IRA") == AccountType.IRA
        assert mapper._map_account_type("Ira") == AccountType.IRA

    def test_type_mapping_handles_whitespace(self, mapper: SchwabAccountMapper):
        """Account type mapping should handle leading/trailing whitespace."""
        assert mapper._map_account_type("  IRA  ") == AccountType.IRA
        assert mapper._map_account_type("\tMARGIN\n") == AccountType.BROKERAGE

    def test_all_mapped_types_are_valid(self):
        """Verify all mapped types in SCHWAB_ACCOUNT_TYPE_MAP are valid AccountType."""
        for schwab_type, account_type in SCHWAB_ACCOUNT_TYPE_MAP.items():
            assert isinstance(account_type, AccountType)
            assert account_type in AccountType


# =============================================================================
# Test: Decimal Parsing
# =============================================================================


class TestDecimalParsing:
    """Test balance value parsing to Decimal."""

    def test_parse_integer(self, mapper: SchwabAccountMapper):
        """Parse integer value to Decimal."""
        result = mapper._parse_decimal(50000)
        assert result == Decimal("50000")

    def test_parse_float(self, mapper: SchwabAccountMapper):
        """Parse float value to Decimal."""
        result = mapper._parse_decimal(50000.50)
        assert result == Decimal("50000.5")

    def test_parse_string(self, mapper: SchwabAccountMapper):
        """Parse string value to Decimal."""
        result = mapper._parse_decimal("50000.99")
        assert result == Decimal("50000.99")

    def test_parse_none_returns_zero(self, mapper: SchwabAccountMapper):
        """None value should return Decimal(0)."""
        result = mapper._parse_decimal(None)
        assert result == Decimal("0")

    def test_parse_zero(self, mapper: SchwabAccountMapper):
        """Zero value should parse correctly."""
        result = mapper._parse_decimal(0)
        assert result == Decimal("0")

    def test_parse_negative(self, mapper: SchwabAccountMapper):
        """Negative value should parse correctly."""
        result = mapper._parse_decimal(-1000.50)
        assert result == Decimal("-1000.5")

    def test_parse_invalid_string_returns_zero(self, mapper: SchwabAccountMapper):
        """Invalid string should return Decimal(0)."""
        result = mapper._parse_decimal("not_a_number")
        assert result == Decimal("0")

    def test_parse_large_value(self, mapper: SchwabAccountMapper):
        """Large value should parse with full precision."""
        result = mapper._parse_decimal(1234567890.123456)
        assert result == Decimal("1234567890.123456")


# =============================================================================
# Test: Account Number Masking
# =============================================================================


class TestAccountNumberMasking:
    """Test account number masking for security."""

    def test_mask_standard_account_number(self, mapper: SchwabAccountMapper):
        """Standard 8-digit account shows last 4."""
        result = mapper._mask_account_number("12345678")
        assert result == "****5678"

    def test_mask_long_account_number(self, mapper: SchwabAccountMapper):
        """Long account number shows last 4."""
        result = mapper._mask_account_number("1234567890123")
        assert result == "****0123"

    def test_mask_short_account_number(self, mapper: SchwabAccountMapper):
        """Short account number (< 4 digits) shows all after ****."""
        result = mapper._mask_account_number("123")
        assert result == "****123"

    def test_mask_exactly_four_digits(self, mapper: SchwabAccountMapper):
        """Four digit account shows all after ****."""
        result = mapper._mask_account_number("1234")
        assert result == "****1234"

    def test_mask_empty_string(self, mapper: SchwabAccountMapper):
        """Empty account number produces ****."""
        result = mapper._mask_account_number("")
        assert result == "****"


# =============================================================================
# Test: Full Account Mapping
# =============================================================================


class TestFullAccountMapping:
    """Test complete account mapping from Schwab JSON."""

    def test_map_valid_account(self, mapper: SchwabAccountMapper):
        """Map valid Schwab account to ProviderAccountData."""
        data = _build_schwab_account(
            account_number="98765432",
            account_type="MARGIN",
            account_name="Trading Account",
            liquidation_value=75000.50,
            available_funds=25000.00,
        )

        result = mapper.map_account(data)

        assert result is not None
        assert isinstance(result, ProviderAccountData)
        assert result.provider_account_id == "98765432"
        assert result.account_number_masked == "****5432"
        assert result.name == "Trading Account"
        assert result.account_type == "brokerage"
        assert result.balance == Decimal("75000.5")
        assert result.available_balance == Decimal("25000")
        assert result.currency == "USD"
        assert result.is_active is True
        assert result.raw_data == data

    def test_map_account_uses_cash_balance_as_fallback(
        self, mapper: SchwabAccountMapper
    ):
        """Use cashBalance when availableFunds is not present."""
        data = _build_schwab_account(
            available_funds=None,
            cash_balance=5000.00,
        )

        result = mapper.map_account(data)

        assert result is not None
        assert result.available_balance == Decimal("5000")

    def test_map_account_without_available_balance(self, mapper: SchwabAccountMapper):
        """Account without available balance sets it to None."""
        data = _build_schwab_account(
            available_funds=None,
            cash_balance=None,
        )

        result = mapper.map_account(data)

        assert result is not None
        assert result.available_balance is None

    def test_map_account_generates_default_name(self, mapper: SchwabAccountMapper):
        """Generate default name when accountName is missing."""
        data = _build_schwab_account(
            account_number="11112222",
            account_name=None,
        )

        result = mapper.map_account(data)

        assert result is not None
        assert result.name == "Schwab ****2222"

    def test_map_account_uses_nickname_as_fallback(self, mapper: SchwabAccountMapper):
        """Use nickname when accountName is not present."""
        data = _build_schwab_account(account_name=None)
        data["securitiesAccount"]["nickname"] = "My Nickname"

        result = mapper.map_account(data)

        assert result is not None
        assert result.name == "My Nickname"

    def test_map_account_missing_securities_account(self, mapper: SchwabAccountMapper):
        """Missing securitiesAccount key returns None."""
        data: dict[str, Any] = {"someOtherKey": {}}

        result = mapper.map_account(data)

        assert result is None

    def test_map_account_empty_securities_account(self, mapper: SchwabAccountMapper):
        """Empty securitiesAccount returns None."""
        data: dict[str, Any] = {"securitiesAccount": {}}

        result = mapper.map_account(data)

        assert result is None

    def test_map_account_missing_account_number(self, mapper: SchwabAccountMapper):
        """Missing accountNumber returns None."""
        data = {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "currentBalances": {"liquidationValue": 1000},
            }
        }

        result = mapper.map_account(data)

        assert result is None

    def test_map_account_empty_account_number(self, mapper: SchwabAccountMapper):
        """Empty accountNumber returns None."""
        data = _build_schwab_account(account_number="")

        result = mapper.map_account(data)

        assert result is None

    def test_map_account_missing_balances(self, mapper: SchwabAccountMapper):
        """Missing currentBalances uses default zero balance."""
        data = {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "accountNumber": "12345678",
            }
        }

        result = mapper.map_account(data)

        assert result is not None
        assert result.balance == Decimal("0")

    def test_map_account_preserves_raw_data(self, mapper: SchwabAccountMapper):
        """Raw Schwab data is preserved in raw_data field."""
        data = _build_schwab_account()

        result = mapper.map_account(data)

        assert result is not None
        assert result.raw_data == data


# =============================================================================
# Test: Batch Account Mapping
# =============================================================================


class TestBatchAccountMapping:
    """Test mapping multiple accounts."""

    def test_map_multiple_accounts(self, mapper: SchwabAccountMapper):
        """Map list of accounts successfully."""
        data_list = [
            _build_schwab_account(account_number="11111111", account_type="MARGIN"),
            _build_schwab_account(account_number="22222222", account_type="IRA"),
            _build_schwab_account(account_number="33333333", account_type="ROTH_IRA"),
        ]

        results = mapper.map_accounts(data_list)

        assert len(results) == 3
        assert results[0].provider_account_id == "11111111"
        assert results[0].account_type == "brokerage"
        assert results[1].provider_account_id == "22222222"
        assert results[1].account_type == "ira"
        assert results[2].provider_account_id == "33333333"
        assert results[2].account_type == "roth_ira"

    def test_map_accounts_skips_invalid(self, mapper: SchwabAccountMapper):
        """Invalid accounts are skipped, valid ones are returned."""
        data_list = [
            _build_schwab_account(account_number="11111111"),
            {"securitiesAccount": {}},  # Invalid - missing account number
            _build_schwab_account(account_number="33333333"),
            {"invalid": "data"},  # Invalid - missing securitiesAccount
        ]

        results = mapper.map_accounts(data_list)

        assert len(results) == 2
        assert results[0].provider_account_id == "11111111"
        assert results[1].provider_account_id == "33333333"

    def test_map_empty_list(self, mapper: SchwabAccountMapper):
        """Empty list returns empty list."""
        results = mapper.map_accounts([])

        assert results == []

    def test_map_all_invalid_returns_empty(self, mapper: SchwabAccountMapper):
        """List with all invalid accounts returns empty list."""
        data_list: list[dict[str, Any]] = [
            {"securitiesAccount": {}},
            {"invalid": "data"},
        ]

        results = mapper.map_accounts(data_list)

        assert results == []


# =============================================================================
# Test: Edge Cases and Error Handling
# =============================================================================


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling."""

    def test_map_account_with_none_data(self, mapper: SchwabAccountMapper):
        """Mapping None data doesn't crash (handles gracefully)."""
        # This tests that map_account handles TypeError from None
        result = mapper.map_account(None)  # type: ignore
        assert result is None

    def test_map_account_with_non_dict(self, mapper: SchwabAccountMapper):
        """Mapping non-dict data doesn't crash."""
        result = mapper.map_account("not a dict")  # type: ignore
        assert result is None

    def test_map_account_with_list(self, mapper: SchwabAccountMapper):
        """Mapping list data doesn't crash."""
        result = mapper.map_account([1, 2, 3])  # type: ignore
        assert result is None

    def test_extremely_long_account_number(self, mapper: SchwabAccountMapper):
        """Very long account number is handled."""
        data = _build_schwab_account(account_number="1" * 100)

        result = mapper.map_account(data)

        assert result is not None
        assert result.provider_account_id == "1" * 100
        assert result.account_number_masked == "****1111"

    def test_special_characters_in_account_name(self, mapper: SchwabAccountMapper):
        """Special characters in account name are preserved."""
        data = _build_schwab_account(account_name="John's IRA (2024) - Rollover")

        result = mapper.map_account(data)

        assert result is not None
        assert result.name == "John's IRA (2024) - Rollover"

    def test_unicode_in_account_name(self, mapper: SchwabAccountMapper):
        """Unicode characters in account name are preserved."""
        data = _build_schwab_account(account_name="José's Account 日本語")

        result = mapper.map_account(data)

        assert result is not None
        assert result.name == "José's Account 日本語"

    def test_very_large_balance(self, mapper: SchwabAccountMapper):
        """Very large balance is handled with precision."""
        data = _build_schwab_account(liquidation_value=999999999999.99)

        result = mapper.map_account(data)

        assert result is not None
        assert result.balance == Decimal("999999999999.99")

    def test_zero_balance(self, mapper: SchwabAccountMapper):
        """Zero balance is handled correctly."""
        data = _build_schwab_account(liquidation_value=0)

        result = mapper.map_account(data)

        assert result is not None
        assert result.balance == Decimal("0")

    def test_negative_balance(self, mapper: SchwabAccountMapper):
        """Negative balance (margin debt) is handled."""
        data = _build_schwab_account(liquidation_value=-5000)

        result = mapper.map_account(data)

        assert result is not None
        assert result.balance == Decimal("-5000")
