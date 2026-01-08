"""Unit tests for AlpacaProvider.

Tests for:
- fetch_accounts: Fetching account data via API
- fetch_transactions: Fetching transaction data via API
- fetch_holdings: Fetching holdings data via API
- validate_credentials: Validating API credentials

Uses mocked API clients to test provider orchestration logic.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.config import Settings
from src.core.enums.error_code import ErrorCode
from src.core.result import Failure, Success
from src.domain.errors import ProviderAuthenticationError, ProviderUnavailableError
from src.domain.protocols.provider_protocol import (
    ProviderAccountData,
    ProviderHoldingData,
    ProviderTransactionData,
)
from src.infrastructure.providers.alpaca.alpaca_provider import AlpacaProvider


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings."""
    settings = MagicMock(spec=Settings)
    settings.alpaca_api_base_url = "https://paper-api.alpaca.markets"
    return settings


@pytest.fixture
def mock_accounts_api() -> AsyncMock:
    """Create mock AlpacaAccountsAPI."""
    return AsyncMock()


@pytest.fixture
def mock_transactions_api() -> AsyncMock:
    """Create mock AlpacaTransactionsAPI."""
    return AsyncMock()


@pytest.fixture
def provider(
    mock_settings: MagicMock,
    mock_accounts_api: AsyncMock,
    mock_transactions_api: AsyncMock,
) -> AlpacaProvider:
    """Create AlpacaProvider with mocked dependencies."""
    provider = AlpacaProvider(settings=mock_settings)
    # Inject mocked API clients
    provider._accounts_api = mock_accounts_api
    provider._transactions_api = mock_transactions_api
    return provider


@pytest.fixture
def valid_credentials() -> dict[str, str]:
    """Valid API credentials dict."""
    return {"api_key": "PKTEST123", "api_secret": "secret456"}


@pytest.fixture
def sample_account_json() -> dict[str, str]:
    """Sample Alpaca account JSON response."""
    return {
        "account_number": "PA3CRCJ7QUIR",
        "status": "ACTIVE",
        "currency": "USD",
        "equity": "150000.50",
        "buying_power": "300000.00",
        "cash": "50000.00",
    }


@pytest.fixture
def sample_position_json() -> dict[str, str]:
    """Sample Alpaca position JSON response."""
    return {
        "asset_id": "b0b6dd9d-8b9b-48a9-ba46-b9d54906e415",
        "symbol": "AAPL",
        "asset_class": "us_equity",
        "qty": "100",
        "avg_entry_price": "150.25",
        "market_value": "15500.00",
        "cost_basis": "15025.00",
        "current_price": "155.00",
        "side": "long",
    }


@pytest.fixture
def sample_activity_json() -> dict[str, str]:
    """Sample Alpaca activity JSON response."""
    return {
        "id": "20210301000000000::8c51c51d-2ccb-4a7c-9bc1-f31b0a7b0ae9",
        "activity_type": "FILL",
        "transaction_time": "2021-03-01T09:30:00Z",
        "symbol": "AAPL",
        "side": "buy",
        "qty": "100",
        "price": "150.25",
    }


# =============================================================================
# Provider Slug Tests
# =============================================================================


@pytest.mark.unit
class TestProviderSlug:
    """Tests for provider slug property."""

    def test_slug_is_alpaca(self, provider: AlpacaProvider):
        """Provider slug should be 'alpaca'."""
        assert provider.slug == "alpaca"


# =============================================================================
# Fetch Accounts Tests
# =============================================================================


@pytest.mark.unit
class TestFetchAccounts:
    """Tests for AlpacaProvider.fetch_accounts."""

    async def test_fetch_accounts_success(
        self,
        provider: AlpacaProvider,
        mock_accounts_api: AsyncMock,
        valid_credentials: dict[str, str],
        sample_account_json: dict[str, str],
    ):
        """Successfully fetch accounts returns ProviderAccountData."""
        mock_accounts_api.get_account.return_value = Success(value=sample_account_json)

        result = await provider.fetch_accounts(valid_credentials)

        assert isinstance(result, Success)
        assert len(result.value) == 1
        account = result.value[0]
        assert isinstance(account, ProviderAccountData)
        assert account.provider_account_id == "PA3CRCJ7QUIR"
        assert account.balance == Decimal("150000.50")

    async def test_fetch_accounts_api_auth_failure(
        self,
        provider: AlpacaProvider,
        mock_accounts_api: AsyncMock,
        valid_credentials: dict[str, str],
    ):
        """API authentication failure returns Failure."""
        error = ProviderAuthenticationError(
            code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
            message="Invalid credentials",
            provider_name="alpaca",
            is_token_expired=False,
        )
        mock_accounts_api.get_account.return_value = Failure(error=error)

        result = await provider.fetch_accounts(valid_credentials)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderAuthenticationError)

    async def test_fetch_accounts_api_unavailable(
        self,
        provider: AlpacaProvider,
        mock_accounts_api: AsyncMock,
        valid_credentials: dict[str, str],
    ):
        """API unavailable returns Failure."""
        error = ProviderUnavailableError(
            code=ErrorCode.PROVIDER_UNAVAILABLE,
            message="API timeout",
            provider_name="alpaca",
            is_transient=True,
        )
        mock_accounts_api.get_account.return_value = Failure(error=error)

        result = await provider.fetch_accounts(valid_credentials)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)

    async def test_fetch_accounts_empty_credentials(
        self,
        provider: AlpacaProvider,
        mock_accounts_api: AsyncMock,
    ):
        """Empty credentials dict is passed to API."""
        mock_accounts_api.get_account.return_value = Success(
            value={"account_number": "PA123", "status": "ACTIVE", "equity": "0"}
        )

        await provider.fetch_accounts({})

        # API should be called with empty strings
        mock_accounts_api.get_account.assert_called_once_with(api_key="", api_secret="")

    async def test_fetch_accounts_invalid_response_returns_empty_list(
        self,
        provider: AlpacaProvider,
        mock_accounts_api: AsyncMock,
        valid_credentials: dict[str, str],
    ):
        """Invalid account data returns empty list (mapper returns None)."""
        # Response with no account_number will fail mapping
        mock_accounts_api.get_account.return_value = Success(
            value={"status": "ACTIVE", "equity": "100000"}
        )

        result = await provider.fetch_accounts(valid_credentials)

        assert isinstance(result, Success)
        assert result.value == []


# =============================================================================
# Fetch Holdings Tests
# =============================================================================


@pytest.mark.unit
class TestFetchHoldings:
    """Tests for AlpacaProvider.fetch_holdings."""

    async def test_fetch_holdings_success(
        self,
        provider: AlpacaProvider,
        mock_accounts_api: AsyncMock,
        valid_credentials: dict[str, str],
        sample_position_json: dict[str, str],
    ):
        """Successfully fetch holdings returns ProviderHoldingData."""
        mock_accounts_api.get_positions.return_value = Success(
            value=[sample_position_json]
        )

        result = await provider.fetch_holdings(valid_credentials, "PA123")

        assert isinstance(result, Success)
        assert len(result.value) == 1
        holding = result.value[0]
        assert isinstance(holding, ProviderHoldingData)
        assert holding.symbol == "AAPL"
        assert holding.quantity == Decimal("100")

    async def test_fetch_holdings_empty_positions(
        self,
        provider: AlpacaProvider,
        mock_accounts_api: AsyncMock,
        valid_credentials: dict[str, str],
    ):
        """Empty positions returns empty list."""
        mock_accounts_api.get_positions.return_value = Success(value=[])

        result = await provider.fetch_holdings(valid_credentials, "PA123")

        assert isinstance(result, Success)
        assert result.value == []

    async def test_fetch_holdings_api_failure(
        self,
        provider: AlpacaProvider,
        mock_accounts_api: AsyncMock,
        valid_credentials: dict[str, str],
    ):
        """API failure returns Failure."""
        error = ProviderAuthenticationError(
            code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
            message="Invalid credentials",
            provider_name="alpaca",
            is_token_expired=False,
        )
        mock_accounts_api.get_positions.return_value = Failure(error=error)

        result = await provider.fetch_holdings(valid_credentials, "PA123")

        assert isinstance(result, Failure)

    async def test_fetch_holdings_multiple_positions(
        self,
        provider: AlpacaProvider,
        mock_accounts_api: AsyncMock,
        valid_credentials: dict[str, str],
    ):
        """Multiple positions are all mapped."""
        positions = [
            {
                "asset_id": "1",
                "symbol": "AAPL",
                "qty": "100",
                "cost_basis": "15000",
                "market_value": "16000",
            },
            {
                "asset_id": "2",
                "symbol": "GOOGL",
                "qty": "50",
                "cost_basis": "70000",
                "market_value": "75000",
            },
        ]
        mock_accounts_api.get_positions.return_value = Success(value=positions)

        result = await provider.fetch_holdings(valid_credentials, "PA123")

        assert isinstance(result, Success)
        assert len(result.value) == 2


# =============================================================================
# Fetch Transactions Tests
# =============================================================================


@pytest.mark.unit
class TestFetchTransactions:
    """Tests for AlpacaProvider.fetch_transactions."""

    async def test_fetch_transactions_success(
        self,
        provider: AlpacaProvider,
        mock_transactions_api: AsyncMock,
        valid_credentials: dict[str, str],
        sample_activity_json: dict[str, str],
    ):
        """Successfully fetch transactions returns ProviderTransactionData."""
        mock_transactions_api.get_transactions.return_value = Success(
            value=[sample_activity_json]
        )

        result = await provider.fetch_transactions(valid_credentials, "PA123")

        assert isinstance(result, Success)
        assert len(result.value) == 1
        txn = result.value[0]
        assert isinstance(txn, ProviderTransactionData)
        assert txn.symbol == "AAPL"
        assert txn.transaction_type == "trade"

    async def test_fetch_transactions_with_date_range(
        self,
        provider: AlpacaProvider,
        mock_transactions_api: AsyncMock,
        valid_credentials: dict[str, str],
    ):
        """Date range is passed to API."""
        mock_transactions_api.get_transactions.return_value = Success(value=[])
        start = date(2021, 1, 1)
        end = date(2021, 12, 31)

        await provider.fetch_transactions(
            valid_credentials, "PA123", start_date=start, end_date=end
        )

        mock_transactions_api.get_transactions.assert_called_once()
        call_kwargs = mock_transactions_api.get_transactions.call_args[1]
        assert call_kwargs["start_date"] == start
        assert call_kwargs["end_date"] == end

    async def test_fetch_transactions_empty(
        self,
        provider: AlpacaProvider,
        mock_transactions_api: AsyncMock,
        valid_credentials: dict[str, str],
    ):
        """Empty transactions returns empty list."""
        mock_transactions_api.get_transactions.return_value = Success(value=[])

        result = await provider.fetch_transactions(valid_credentials, "PA123")

        assert isinstance(result, Success)
        assert result.value == []

    async def test_fetch_transactions_api_failure(
        self,
        provider: AlpacaProvider,
        mock_transactions_api: AsyncMock,
        valid_credentials: dict[str, str],
    ):
        """API failure returns Failure."""
        error = ProviderUnavailableError(
            code=ErrorCode.PROVIDER_UNAVAILABLE,
            message="Timeout",
            provider_name="alpaca",
            is_transient=True,
        )
        mock_transactions_api.get_transactions.return_value = Failure(error=error)

        result = await provider.fetch_transactions(valid_credentials, "PA123")

        assert isinstance(result, Failure)


# =============================================================================
# Validate Credentials Tests
# =============================================================================


@pytest.mark.unit
class TestValidateCredentials:
    """Tests for AlpacaProvider.validate_credentials."""

    async def test_validate_credentials_success(
        self,
        provider: AlpacaProvider,
        mock_accounts_api: AsyncMock,
        valid_credentials: dict[str, str],
        sample_account_json: dict[str, str],
    ):
        """Valid credentials return Success(True)."""
        mock_accounts_api.get_account.return_value = Success(value=sample_account_json)

        result = await provider.validate_credentials(valid_credentials)

        assert isinstance(result, Success)
        assert result.value is True

    async def test_validate_credentials_failure(
        self,
        provider: AlpacaProvider,
        mock_accounts_api: AsyncMock,
        valid_credentials: dict[str, str],
    ):
        """Invalid credentials return Failure."""
        error = ProviderAuthenticationError(
            code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
            message="Invalid API credentials",
            provider_name="alpaca",
            is_token_expired=False,
        )
        mock_accounts_api.get_account.return_value = Failure(error=error)

        result = await provider.validate_credentials(valid_credentials)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderAuthenticationError)


# =============================================================================
# Credentials Extraction Tests
# =============================================================================


@pytest.mark.unit
class TestCredentialsExtraction:
    """Tests for credential extraction from dict."""

    async def test_extracts_api_key_from_credentials(
        self,
        provider: AlpacaProvider,
        mock_accounts_api: AsyncMock,
    ):
        """API key is extracted from credentials dict."""
        mock_accounts_api.get_account.return_value = Success(
            value={"account_number": "PA123", "status": "ACTIVE", "equity": "0"}
        )

        await provider.fetch_accounts({"api_key": "MY_KEY", "api_secret": "MY_SECRET"})

        mock_accounts_api.get_account.assert_called_once_with(
            api_key="MY_KEY", api_secret="MY_SECRET"
        )

    async def test_missing_credentials_default_to_empty_string(
        self,
        provider: AlpacaProvider,
        mock_accounts_api: AsyncMock,
    ):
        """Missing credentials default to empty strings."""
        mock_accounts_api.get_account.return_value = Success(
            value={"account_number": "PA123", "status": "ACTIVE", "equity": "0"}
        )

        await provider.fetch_accounts({"other_field": "value"})

        mock_accounts_api.get_account.assert_called_once_with(api_key="", api_secret="")
