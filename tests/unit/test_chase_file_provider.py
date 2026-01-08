"""Unit tests for ChaseFileProvider.

Tests the Chase file import provider that parses QFX/OFX files.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.core.result import Failure, Success
from src.infrastructure.providers.chase import ChaseFileProvider


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def provider() -> ChaseFileProvider:
    """Create ChaseFileProvider instance."""
    return ChaseFileProvider()


@pytest.fixture
def checking_credentials() -> dict[str, bytes | str]:
    """Credentials dict with checking account QFX file."""
    fixture_path = (
        Path(__file__).parent.parent / "fixtures" / "chase_checking_account.qfx"
    )
    return {
        "file_content": fixture_path.read_bytes(),
        "file_format": "qfx",
        "file_name": "chase_checking_account.qfx",
    }


@pytest.fixture
def savings_credentials() -> dict[str, bytes | str]:
    """Credentials dict with savings account QFX file."""
    fixture_path = (
        Path(__file__).parent.parent / "fixtures" / "chase_savings_account.qfx"
    )
    return {
        "file_content": fixture_path.read_bytes(),
        "file_format": "qfx",
        "file_name": "chase_savings_account.qfx",
    }


# =============================================================================
# Provider Properties Tests
# =============================================================================


class TestChaseFileProviderProperties:
    """Tests for provider properties."""

    def test_slug_returns_chase_file(self, provider: ChaseFileProvider):
        """Provider slug is 'chase_file'."""
        assert provider.slug == "chase_file"


# =============================================================================
# fetch_accounts Tests
# =============================================================================


class TestFetchAccounts:
    """Tests for fetch_accounts method."""

    @pytest.mark.asyncio
    async def test_fetch_accounts_returns_success(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """fetch_accounts returns Success with account list."""
        result = await provider.fetch_accounts(checking_credentials)

        assert isinstance(result, Success)
        assert len(result.value) == 1

    @pytest.mark.asyncio
    async def test_fetch_accounts_extracts_account_info(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """fetch_accounts extracts correct account information."""
        result = await provider.fetch_accounts(checking_credentials)

        assert isinstance(result, Success)
        account = result.value[0]
        assert account.provider_account_id == "123456789"
        assert account.account_number_masked == "****6789"
        assert account.account_type == "checking"
        assert account.currency == "USD"
        assert account.is_active is True

    @pytest.mark.asyncio
    async def test_fetch_accounts_extracts_balance(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """fetch_accounts extracts balance from file."""
        result = await provider.fetch_accounts(checking_credentials)

        assert isinstance(result, Success)
        account = result.value[0]
        assert account.balance == Decimal("5000.27")
        assert account.available_balance == Decimal("4500.27")

    @pytest.mark.asyncio
    async def test_fetch_accounts_savings_type(
        self,
        provider: ChaseFileProvider,
        savings_credentials: dict[str, bytes | str],
    ):
        """fetch_accounts correctly identifies savings account."""
        result = await provider.fetch_accounts(savings_credentials)

        assert isinstance(result, Success)
        account = result.value[0]
        assert account.account_type == "savings"
        assert account.provider_account_id == "987654321"

    @pytest.mark.asyncio
    async def test_fetch_accounts_generates_name(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """fetch_accounts generates account name."""
        result = await provider.fetch_accounts(checking_credentials)

        assert isinstance(result, Success)
        account = result.value[0]
        assert "Chase" in account.name
        assert "Checking" in account.name
        assert "6789" in account.name

    @pytest.mark.asyncio
    async def test_fetch_accounts_missing_content_returns_failure(
        self,
        provider: ChaseFileProvider,
    ):
        """fetch_accounts with missing file_content returns Failure."""
        credentials = {"file_format": "qfx"}
        result = await provider.fetch_accounts(credentials)

        assert isinstance(result, Failure)
        assert "Missing file_content" in result.error.message

    @pytest.mark.asyncio
    async def test_fetch_accounts_invalid_format_returns_failure(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """fetch_accounts with unsupported format returns Failure."""
        checking_credentials["file_format"] = "csv"
        result = await provider.fetch_accounts(checking_credentials)

        assert isinstance(result, Failure)
        assert "Unsupported file format" in result.error.message

    @pytest.mark.asyncio
    async def test_fetch_accounts_invalid_content_returns_failure(
        self,
        provider: ChaseFileProvider,
    ):
        """fetch_accounts with invalid content returns Failure."""
        credentials = {
            "file_content": b"not valid qfx",
            "file_format": "qfx",
        }
        result = await provider.fetch_accounts(credentials)

        assert isinstance(result, Failure)


# =============================================================================
# fetch_transactions Tests
# =============================================================================


class TestFetchTransactions:
    """Tests for fetch_transactions method."""

    @pytest.mark.asyncio
    async def test_fetch_transactions_returns_success(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """fetch_transactions returns Success with transaction list."""
        result = await provider.fetch_transactions(
            checking_credentials,
            provider_account_id="123456789",
        )

        assert isinstance(result, Success)
        assert len(result.value) == 7

    @pytest.mark.asyncio
    async def test_fetch_transactions_extracts_transaction_info(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """fetch_transactions extracts correct transaction information."""
        result = await provider.fetch_transactions(
            checking_credentials,
            provider_account_id="123456789",
        )

        assert isinstance(result, Success)
        # Find the payroll transaction
        payroll_txn = next(txn for txn in result.value if "PAYROLL" in txn.description)
        assert payroll_txn.amount == Decimal("2500.00")
        assert payroll_txn.transaction_type == "deposit"
        assert payroll_txn.currency == "USD"
        assert payroll_txn.status == "posted"

    @pytest.mark.asyncio
    async def test_fetch_transactions_maps_transaction_types(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """fetch_transactions maps OFX types to Dashtam types."""
        result = await provider.fetch_transactions(
            checking_credentials,
            provider_account_id="123456789",
        )

        assert isinstance(result, Success)
        # Credit transactions become deposits
        credits = [t for t in result.value if t.amount > 0]
        assert all(t.transaction_type == "deposit" for t in credits)

        # Debit transactions become withdrawals
        debits = [t for t in result.value if t.amount < 0]
        assert all(t.transaction_type == "withdrawal" for t in debits)

    @pytest.mark.asyncio
    async def test_fetch_transactions_detects_subtypes(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """fetch_transactions detects subtypes from transaction names."""
        result = await provider.fetch_transactions(
            checking_credentials,
            provider_account_id="123456789",
        )

        assert isinstance(result, Success)
        # Find Zelle transaction
        zelle_txn = next(txn for txn in result.value if "Zelle" in txn.description)
        assert zelle_txn.subtype == "zelle"

        # Find autopay transaction
        autopay_txn = next(txn for txn in result.value if "AUTOPAY" in txn.description)
        assert autopay_txn.subtype == "autopay"

    @pytest.mark.asyncio
    async def test_fetch_transactions_wrong_account_returns_empty(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """fetch_transactions with wrong account ID returns empty list."""
        result = await provider.fetch_transactions(
            checking_credentials,
            provider_account_id="wrong_account_id",
        )

        assert isinstance(result, Success)
        assert result.value == []

    @pytest.mark.asyncio
    async def test_fetch_transactions_with_date_filter(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """fetch_transactions applies date filtering."""
        result = await provider.fetch_transactions(
            checking_credentials,
            provider_account_id="123456789",
            start_date=date(2025, 12, 15),
            end_date=date(2025, 12, 20),
        )

        assert isinstance(result, Success)
        # Should only include transactions between Dec 15-20
        for txn in result.value:
            assert date(2025, 12, 15) <= txn.transaction_date <= date(2025, 12, 20)

    @pytest.mark.asyncio
    async def test_fetch_transactions_start_date_only(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """fetch_transactions filters by start_date only."""
        result = await provider.fetch_transactions(
            checking_credentials,
            provider_account_id="123456789",
            start_date=date(2025, 12, 20),
        )

        assert isinstance(result, Success)
        for txn in result.value:
            assert txn.transaction_date >= date(2025, 12, 20)


# =============================================================================
# fetch_holdings Tests
# =============================================================================


class TestFetchHoldings:
    """Tests for fetch_holdings method."""

    @pytest.mark.asyncio
    async def test_fetch_holdings_returns_empty_list(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """fetch_holdings returns empty list (bank accounts have no holdings)."""
        result = await provider.fetch_holdings(
            checking_credentials,
            provider_account_id="123456789",
        )

        assert isinstance(result, Success)
        assert result.value == []


# =============================================================================
# Caching Tests
# =============================================================================


class TestProviderCaching:
    """Tests for provider caching behavior."""

    @pytest.mark.asyncio
    async def test_parse_cache_reuses_result(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """Same file content uses cached parse result."""
        # First call parses the file
        await provider.fetch_accounts(checking_credentials)

        # Second call should use cache
        await provider.fetch_transactions(
            checking_credentials,
            provider_account_id="123456789",
        )

        # Cache should have one entry
        assert len(provider._parsed_cache) == 1

    @pytest.mark.asyncio
    async def test_clear_cache_empties_cache(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
    ):
        """clear_cache removes all cached data."""
        await provider.fetch_accounts(checking_credentials)
        assert len(provider._parsed_cache) == 1

        provider.clear_cache()
        assert len(provider._parsed_cache) == 0

    @pytest.mark.asyncio
    async def test_different_files_cached_separately(
        self,
        provider: ChaseFileProvider,
        checking_credentials: dict[str, bytes | str],
        savings_credentials: dict[str, bytes | str],
    ):
        """Different files are cached separately."""
        await provider.fetch_accounts(checking_credentials)
        await provider.fetch_accounts(savings_credentials)

        assert len(provider._parsed_cache) == 2


# =============================================================================
# String Content Tests
# =============================================================================


class TestStringContentHandling:
    """Tests for string content handling."""

    @pytest.mark.asyncio
    async def test_string_content_converted_to_bytes(
        self,
        provider: ChaseFileProvider,
    ):
        """String file_content is converted to bytes."""
        fixture_path = (
            Path(__file__).parent.parent / "fixtures" / "chase_checking_account.qfx"
        )
        string_content = fixture_path.read_text()

        credentials = {
            "file_content": string_content,  # String instead of bytes
            "file_format": "qfx",
        }

        result = await provider.fetch_accounts(credentials)
        assert isinstance(result, Success)
