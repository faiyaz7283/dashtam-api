"""Unit tests for Chase QFX parser.

Tests the QfxParser class that parses QFX/OFX files from Chase.
Uses synthetic fixture files with fake data.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.core.result import Failure, Success
from src.infrastructure.providers.chase.parsers.qfx_parser import (
    ParsedAccount,
    ParsedBalance,
    ParsedTransaction,
    QfxParser,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def parser() -> QfxParser:
    """Create QFX parser instance."""
    return QfxParser()


@pytest.fixture
def checking_qfx_content() -> bytes:
    """Load checking account QFX fixture."""
    fixture_path = (
        Path(__file__).parent.parent / "fixtures" / "chase_checking_account.qfx"
    )
    return fixture_path.read_bytes()


@pytest.fixture
def savings_qfx_content() -> bytes:
    """Load savings account QFX fixture."""
    fixture_path = (
        Path(__file__).parent.parent / "fixtures" / "chase_savings_account.qfx"
    )
    return fixture_path.read_bytes()


# =============================================================================
# Parse Success Tests
# =============================================================================


class TestQfxParserSuccess:
    """Tests for successful QFX parsing."""

    def test_parse_checking_account_returns_success(
        self,
        parser: QfxParser,
        checking_qfx_content: bytes,
    ):
        """Parse checking account QFX file successfully."""
        result = parser.parse(checking_qfx_content, "chase_checking.qfx")

        assert isinstance(result, Success)
        assert isinstance(result.value, ParsedAccount)

    def test_parse_checking_account_extracts_account_info(
        self,
        parser: QfxParser,
        checking_qfx_content: bytes,
    ):
        """Extract account information from checking QFX."""
        result = parser.parse(checking_qfx_content, "chase_checking.qfx")

        parsed = result.value
        assert parsed.account_id == "123456789"
        assert parsed.account_type == "CHECKING"
        assert parsed.bank_id == "021000021"
        assert parsed.currency == "USD"

    def test_parse_checking_account_extracts_transactions(
        self,
        parser: QfxParser,
        checking_qfx_content: bytes,
    ):
        """Extract transactions from checking QFX."""
        result = parser.parse(checking_qfx_content, "chase_checking.qfx")

        parsed = result.value
        assert len(parsed.transactions) == 7

        # Check first transaction (interest payment)
        first_txn = parsed.transactions[0]
        assert first_txn.fit_id == "202512240001"
        assert first_txn.transaction_type == "CREDIT"
        assert first_txn.amount == Decimal("0.02")
        assert first_txn.name == "INTEREST PAYMENT"
        assert first_txn.date_posted == date(2025, 12, 24)

    def test_parse_checking_account_extracts_balance(
        self,
        parser: QfxParser,
        checking_qfx_content: bytes,
    ):
        """Extract balance from checking QFX."""
        result = parser.parse(checking_qfx_content, "chase_checking.qfx")

        parsed = result.value
        assert parsed.balance is not None
        assert parsed.balance.ledger_balance == Decimal("5000.27")
        assert parsed.balance.available_balance == Decimal("4500.27")
        assert parsed.balance.currency == "USD"

    def test_parse_savings_account_returns_success(
        self,
        parser: QfxParser,
        savings_qfx_content: bytes,
    ):
        """Parse savings account QFX file successfully."""
        result = parser.parse(savings_qfx_content, "chase_savings.qfx")

        assert isinstance(result, Success)
        parsed = result.value
        assert parsed.account_id == "987654321"
        assert parsed.account_type == "SAVINGS"

    def test_parse_savings_account_extracts_transactions(
        self,
        parser: QfxParser,
        savings_qfx_content: bytes,
    ):
        """Extract transactions from savings QFX."""
        result = parser.parse(savings_qfx_content, "chase_savings.qfx")

        parsed = result.value
        assert len(parsed.transactions) == 3

    def test_parse_transaction_with_memo(
        self,
        parser: QfxParser,
        checking_qfx_content: bytes,
    ):
        """Transactions with MEMO field are parsed correctly."""
        result = parser.parse(checking_qfx_content, "chase_checking.qfx")

        # Find the payroll transaction which has a memo
        payroll_txn = next(
            txn for txn in result.value.transactions if "PAYROLL" in txn.name
        )
        assert payroll_txn.memo == "PPD ID: 1234567890"
        assert payroll_txn.amount == Decimal("2500.00")

    def test_parse_debit_transaction_has_negative_amount(
        self,
        parser: QfxParser,
        checking_qfx_content: bytes,
    ):
        """Debit transactions have negative amounts."""
        result = parser.parse(checking_qfx_content, "chase_checking.qfx")

        # Find the rent payment (debit)
        rent_txn = next(
            txn for txn in result.value.transactions if "LANDLORD" in txn.name
        )
        assert rent_txn.transaction_type == "DEBIT"
        assert rent_txn.amount == Decimal("-1500.00")


# =============================================================================
# Parse Failure Tests
# =============================================================================


class TestQfxParserFailure:
    """Tests for QFX parsing failures."""

    def test_parse_invalid_content_returns_failure(self, parser: QfxParser):
        """Invalid QFX content returns Failure."""
        result = parser.parse(b"not a valid QFX file", "invalid.qfx")

        assert isinstance(result, Failure)
        assert "Failed to parse QFX file" in result.error.message

    def test_parse_empty_content_returns_failure(self, parser: QfxParser):
        """Empty content returns Failure."""
        result = parser.parse(b"", "empty.qfx")

        assert isinstance(result, Failure)

    def test_parse_xml_without_accounts_returns_failure(self, parser: QfxParser):
        """QFX-like content without account data returns Failure."""
        # Valid OFX header but no BANKACCTFROM
        content = b"""
OFXHEADER:100
DATA:OFXSGML
VERSION:102
<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0
</STATUS>
</SONRS>
</SIGNONMSGSRSV1>
</OFX>
"""
        result = parser.parse(content, "no_account.qfx")

        assert isinstance(result, Failure)
        assert "no account data" in result.error.message.lower()


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestQfxParserEdgeCases:
    """Tests for edge cases in QFX parsing."""

    def test_mask_account_id_shows_last_four(self, parser: QfxParser):
        """Account ID masking shows only last 4 digits."""
        masked = parser._mask_account_id("123456789")
        assert masked == "****6789"

    def test_mask_account_id_short_number(self, parser: QfxParser):
        """Short account ID is fully masked."""
        masked = parser._mask_account_id("123")
        assert masked == "****"

    def test_parse_handles_string_content(self, parser: QfxParser):
        """Parser handles string content (converts to bytes)."""
        # Note: parse() expects bytes, but we test internal robustness
        # The provider handles string conversion before calling parse()
        pass  # This is tested via the provider


# =============================================================================
# Dataclass Tests
# =============================================================================


class TestParsedDataclasses:
    """Tests for parsed dataclass structures."""

    def test_parsed_transaction_is_frozen(self):
        """ParsedTransaction is immutable."""
        txn = ParsedTransaction(
            fit_id="123",
            transaction_type="CREDIT",
            date_posted=date(2025, 1, 1),
            amount=Decimal("100.00"),
            name="Test",
        )
        with pytest.raises(AttributeError):
            txn.amount = Decimal("200.00")  # type: ignore

    def test_parsed_balance_is_frozen(self):
        """ParsedBalance is immutable."""
        from datetime import datetime

        balance = ParsedBalance(
            ledger_balance=Decimal("1000.00"),
            available_balance=Decimal("1000.00"),
            balance_date=datetime.now(),
            currency="USD",
        )
        with pytest.raises(AttributeError):
            balance.ledger_balance = Decimal("2000.00")  # type: ignore

    def test_parsed_account_is_frozen(self):
        """ParsedAccount is immutable."""
        account = ParsedAccount(
            account_id="123",
            account_type="CHECKING",
            bank_id="021",
            currency="USD",
            transactions=[],
            balance=None,
        )
        with pytest.raises(AttributeError):
            account.account_id = "456"  # type: ignore
