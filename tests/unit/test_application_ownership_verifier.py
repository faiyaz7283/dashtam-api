"""Tests for src/application/services/ownership_verifier.py.

Verifies the OwnershipVerifier service correctly validates ownership
through the entity ownership chain: Entity → Account → Connection → User.

Reference:
    - src/application/services/ownership_verifier.py
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.application.services.ownership_verifier import (
    OwnershipError,
    OwnershipErrorCode,
    OwnershipVerifier,
)
from src.core.result import Failure, Success
from src.domain.entities import Account, Holding, ProviderConnection, Transaction
from src.domain.enums import (
    AccountType,
    AssetType,
    ConnectionStatus,
    CredentialType,
    TransactionStatus,
    TransactionSubtype,
    TransactionType,
)
from src.domain.value_objects import Money, ProviderCredentials


@pytest.fixture
def mock_transaction_repo() -> AsyncMock:
    """Mock TransactionRepository."""
    return AsyncMock()


@pytest.fixture
def mock_holding_repo() -> AsyncMock:
    """Mock HoldingRepository."""
    return AsyncMock()


@pytest.fixture
def mock_account_repo() -> AsyncMock:
    """Mock AccountRepository."""
    return AsyncMock()


@pytest.fixture
def mock_connection_repo() -> AsyncMock:
    """Mock ProviderConnectionRepository."""
    return AsyncMock()


@pytest.fixture
def verifier(
    mock_transaction_repo: AsyncMock,
    mock_holding_repo: AsyncMock,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
) -> OwnershipVerifier:
    """Create OwnershipVerifier with mocked dependencies."""
    return OwnershipVerifier(
        transaction_repo=mock_transaction_repo,
        holding_repo=mock_holding_repo,
        account_repo=mock_account_repo,
        connection_repo=mock_connection_repo,
    )


@pytest.fixture
def user_id():
    """Standard test user ID."""
    return cast(UUID, uuid7())


@pytest.fixture
def other_user_id():
    """Different user ID for ownership failure tests."""
    return cast(UUID, uuid7())


@pytest.fixture
def connection_id():
    """Provider connection ID."""
    return cast(UUID, uuid7())


@pytest.fixture
def account_id():
    """Account ID."""
    return cast(UUID, uuid7())


@pytest.fixture
def holding_id():
    """Holding ID."""
    return cast(UUID, uuid7())


@pytest.fixture
def transaction_id():
    """Transaction ID."""
    return cast(UUID, uuid7())


@pytest.fixture
def mock_connection(user_id, connection_id) -> ProviderConnection:
    """Create mock ProviderConnection owned by user_id."""
    return ProviderConnection(
        id=connection_id,
        user_id=user_id,
        provider_id=cast(UUID, uuid7()),
        provider_slug="schwab",
        status=ConnectionStatus.ACTIVE,
        credentials=ProviderCredentials(
            encrypted_data=b"test_encrypted_token",
            credential_type=CredentialType.OAUTH2,
        ),
        connected_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def mock_account(connection_id, account_id) -> Account:
    """Create mock Account linked to connection."""
    return Account(
        id=account_id,
        connection_id=connection_id,
        provider_account_id="test-account-123",
        account_number_masked="****1234",
        name="Test Brokerage",
        account_type=AccountType.BROKERAGE,
        currency="USD",
        balance=Money(amount=Decimal("15000.50"), currency="USD"),
        is_active=True,
        created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def mock_holding(account_id, holding_id) -> Holding:
    """Create mock Holding linked to account."""
    return Holding(
        id=holding_id,
        account_id=account_id,
        provider_holding_id="test-holding-123",
        symbol="AAPL",
        security_name="Apple Inc.",
        asset_type=AssetType.EQUITY,
        quantity=Decimal("100.0"),
        cost_basis=Money(amount=Decimal("15000.00"), currency="USD"),
        market_value=Money(amount=Decimal("17500.00"), currency="USD"),
        currency="USD",
        is_active=True,
        created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
    )


class TestVerifyConnectionOwnership:
    """Tests for verify_connection_ownership method."""

    @pytest.mark.asyncio
    async def test_returns_connection_when_owned_by_user(
        self,
        verifier: OwnershipVerifier,
        mock_connection_repo: AsyncMock,
        mock_connection: ProviderConnection,
        user_id,
        connection_id,
    ) -> None:
        """Should return Success with connection when user owns it."""
        mock_connection_repo.find_by_id.return_value = mock_connection

        result = await verifier.verify_connection_ownership(connection_id, user_id)

        assert isinstance(result, Success)
        assert result.value == mock_connection
        mock_connection_repo.find_by_id.assert_called_once_with(connection_id)

    @pytest.mark.asyncio
    async def test_returns_failure_when_connection_not_found(
        self,
        verifier: OwnershipVerifier,
        mock_connection_repo: AsyncMock,
        user_id,
        connection_id,
    ) -> None:
        """Should return Failure when connection doesn't exist."""
        mock_connection_repo.find_by_id.return_value = None

        result = await verifier.verify_connection_ownership(connection_id, user_id)

        assert isinstance(result, Failure)
        assert result.error.code == OwnershipErrorCode.CONNECTION_NOT_FOUND
        assert "not found" in result.error.message.lower()

    @pytest.mark.asyncio
    async def test_returns_failure_when_not_owned_by_user(
        self,
        verifier: OwnershipVerifier,
        mock_connection_repo: AsyncMock,
        mock_connection: ProviderConnection,
        other_user_id,
        connection_id,
    ) -> None:
        """Should return Failure when connection owned by different user."""
        mock_connection_repo.find_by_id.return_value = mock_connection

        result = await verifier.verify_connection_ownership(
            connection_id, other_user_id
        )

        assert isinstance(result, Failure)
        assert result.error.code == OwnershipErrorCode.NOT_OWNED_BY_USER
        assert "not owned" in result.error.message.lower()


class TestVerifyAccountOwnership:
    """Tests for verify_account_ownership method."""

    @pytest.mark.asyncio
    async def test_returns_account_when_owned_by_user(
        self,
        verifier: OwnershipVerifier,
        mock_account_repo: AsyncMock,
        mock_connection_repo: AsyncMock,
        mock_account: Account,
        mock_connection: ProviderConnection,
        user_id,
        account_id,
    ) -> None:
        """Should return Success with account when user owns it via connection."""
        mock_account_repo.find_by_id.return_value = mock_account
        mock_connection_repo.find_by_id.return_value = mock_connection

        result = await verifier.verify_account_ownership(account_id, user_id)

        assert isinstance(result, Success)
        assert result.value == mock_account
        mock_account_repo.find_by_id.assert_called_once_with(account_id)
        mock_connection_repo.find_by_id.assert_called_once_with(
            mock_account.connection_id
        )

    @pytest.mark.asyncio
    async def test_returns_failure_when_account_not_found(
        self,
        verifier: OwnershipVerifier,
        mock_account_repo: AsyncMock,
        user_id,
        account_id,
    ) -> None:
        """Should return Failure when account doesn't exist."""
        mock_account_repo.find_by_id.return_value = None

        result = await verifier.verify_account_ownership(account_id, user_id)

        assert isinstance(result, Failure)
        assert result.error.code == OwnershipErrorCode.ACCOUNT_NOT_FOUND
        assert "account" in result.error.message.lower()

    @pytest.mark.asyncio
    async def test_returns_failure_when_connection_not_found(
        self,
        verifier: OwnershipVerifier,
        mock_account_repo: AsyncMock,
        mock_connection_repo: AsyncMock,
        mock_account: Account,
        user_id,
        account_id,
    ) -> None:
        """Should return Failure when account's connection doesn't exist."""
        mock_account_repo.find_by_id.return_value = mock_account
        mock_connection_repo.find_by_id.return_value = None

        result = await verifier.verify_account_ownership(account_id, user_id)

        assert isinstance(result, Failure)
        assert result.error.code == OwnershipErrorCode.CONNECTION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_returns_failure_when_not_owned_by_user(
        self,
        verifier: OwnershipVerifier,
        mock_account_repo: AsyncMock,
        mock_connection_repo: AsyncMock,
        mock_account: Account,
        mock_connection: ProviderConnection,
        other_user_id,
        account_id,
    ) -> None:
        """Should return Failure when account's connection owned by different user."""
        mock_account_repo.find_by_id.return_value = mock_account
        mock_connection_repo.find_by_id.return_value = mock_connection

        result = await verifier.verify_account_ownership(account_id, other_user_id)

        assert isinstance(result, Failure)
        assert result.error.code == OwnershipErrorCode.NOT_OWNED_BY_USER


class TestVerifyAccountOwnershipOnly:
    """Tests for verify_account_ownership_only method."""

    @pytest.mark.asyncio
    async def test_returns_success_none_when_owned(
        self,
        verifier: OwnershipVerifier,
        mock_account_repo: AsyncMock,
        mock_connection_repo: AsyncMock,
        mock_account: Account,
        mock_connection: ProviderConnection,
        user_id,
        account_id,
    ) -> None:
        """Should return Success(None) when user owns account."""
        mock_account_repo.find_by_id.return_value = mock_account
        mock_connection_repo.find_by_id.return_value = mock_connection

        result = await verifier.verify_account_ownership_only(account_id, user_id)

        assert isinstance(result, Success)
        assert result.value is None

    @pytest.mark.asyncio
    async def test_returns_failure_when_not_owned(
        self,
        verifier: OwnershipVerifier,
        mock_account_repo: AsyncMock,
        mock_connection_repo: AsyncMock,
        mock_account: Account,
        mock_connection: ProviderConnection,
        other_user_id,
        account_id,
    ) -> None:
        """Should return Failure when user doesn't own account."""
        mock_account_repo.find_by_id.return_value = mock_account
        mock_connection_repo.find_by_id.return_value = mock_connection

        result = await verifier.verify_account_ownership_only(account_id, other_user_id)

        assert isinstance(result, Failure)
        assert result.error.code == OwnershipErrorCode.NOT_OWNED_BY_USER


class TestVerifyHoldingOwnership:
    """Tests for verify_holding_ownership method."""

    @pytest.mark.asyncio
    async def test_returns_holding_when_owned_by_user(
        self,
        verifier: OwnershipVerifier,
        mock_holding_repo: AsyncMock,
        mock_account_repo: AsyncMock,
        mock_connection_repo: AsyncMock,
        mock_holding: Holding,
        mock_account: Account,
        mock_connection: ProviderConnection,
        user_id,
        holding_id,
    ) -> None:
        """Should return Success with holding when user owns it via account/connection."""
        mock_holding_repo.find_by_id.return_value = mock_holding
        mock_account_repo.find_by_id.return_value = mock_account
        mock_connection_repo.find_by_id.return_value = mock_connection

        result = await verifier.verify_holding_ownership(holding_id, user_id)

        assert isinstance(result, Success)
        assert result.value == mock_holding
        mock_holding_repo.find_by_id.assert_called_once_with(holding_id)

    @pytest.mark.asyncio
    async def test_returns_failure_when_holding_not_found(
        self,
        verifier: OwnershipVerifier,
        mock_holding_repo: AsyncMock,
        user_id,
        holding_id,
    ) -> None:
        """Should return Failure when holding doesn't exist."""
        mock_holding_repo.find_by_id.return_value = None

        result = await verifier.verify_holding_ownership(holding_id, user_id)

        assert isinstance(result, Failure)
        assert result.error.code == OwnershipErrorCode.HOLDING_NOT_FOUND
        assert "holding" in result.error.message.lower()

    @pytest.mark.asyncio
    async def test_returns_failure_when_account_not_found(
        self,
        verifier: OwnershipVerifier,
        mock_holding_repo: AsyncMock,
        mock_account_repo: AsyncMock,
        mock_holding: Holding,
        user_id,
        holding_id,
    ) -> None:
        """Should return Failure when holding's account doesn't exist."""
        mock_holding_repo.find_by_id.return_value = mock_holding
        mock_account_repo.find_by_id.return_value = None

        result = await verifier.verify_holding_ownership(holding_id, user_id)

        assert isinstance(result, Failure)
        assert result.error.code == OwnershipErrorCode.ACCOUNT_NOT_FOUND

    @pytest.mark.asyncio
    async def test_returns_failure_when_connection_not_found(
        self,
        verifier: OwnershipVerifier,
        mock_holding_repo: AsyncMock,
        mock_account_repo: AsyncMock,
        mock_connection_repo: AsyncMock,
        mock_holding: Holding,
        mock_account: Account,
        user_id,
        holding_id,
    ) -> None:
        """Should return Failure when account's connection doesn't exist."""
        mock_holding_repo.find_by_id.return_value = mock_holding
        mock_account_repo.find_by_id.return_value = mock_account
        mock_connection_repo.find_by_id.return_value = None

        result = await verifier.verify_holding_ownership(holding_id, user_id)

        assert isinstance(result, Failure)
        assert result.error.code == OwnershipErrorCode.CONNECTION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_returns_failure_when_not_owned_by_user(
        self,
        verifier: OwnershipVerifier,
        mock_holding_repo: AsyncMock,
        mock_account_repo: AsyncMock,
        mock_connection_repo: AsyncMock,
        mock_holding: Holding,
        mock_account: Account,
        mock_connection: ProviderConnection,
        other_user_id,
        holding_id,
    ) -> None:
        """Should return Failure when holding's connection owned by different user."""
        mock_holding_repo.find_by_id.return_value = mock_holding
        mock_account_repo.find_by_id.return_value = mock_account
        mock_connection_repo.find_by_id.return_value = mock_connection

        result = await verifier.verify_holding_ownership(holding_id, other_user_id)

        assert isinstance(result, Failure)
        assert result.error.code == OwnershipErrorCode.NOT_OWNED_BY_USER


class TestOwnershipError:
    """Tests for OwnershipError dataclass."""

    def test_ownership_error_is_frozen(self) -> None:
        """OwnershipError should be immutable."""
        error = OwnershipError(
            code=OwnershipErrorCode.ACCOUNT_NOT_FOUND,
            message="Account not found",
        )
        with pytest.raises(AttributeError):
            error.code = "new_code"  # type: ignore[misc]

    def test_ownership_error_codes_are_unique(self) -> None:
        """All OwnershipErrorCode values should be unique."""
        codes = [
            OwnershipErrorCode.TRANSACTION_NOT_FOUND,
            OwnershipErrorCode.HOLDING_NOT_FOUND,
            OwnershipErrorCode.ACCOUNT_NOT_FOUND,
            OwnershipErrorCode.CONNECTION_NOT_FOUND,
            OwnershipErrorCode.NOT_OWNED_BY_USER,
        ]
        assert len(codes) == len(set(codes))


@pytest.fixture
def mock_transaction(account_id, transaction_id) -> Transaction:
    """Create mock Transaction linked to account."""
    return Transaction(
        id=transaction_id,
        account_id=account_id,
        provider_transaction_id="test-txn-123",
        transaction_type=TransactionType.TRADE,
        subtype=TransactionSubtype.BUY,
        status=TransactionStatus.SETTLED,
        amount=Money(amount=Decimal("1500.00"), currency="USD"),
        description="Buy 10 shares of AAPL",
        transaction_date=datetime(2025, 1, 15, tzinfo=UTC).date(),
        created_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
    )


class TestVerifyTransactionOwnership:
    """Tests for verify_transaction_ownership method."""

    @pytest.mark.asyncio
    async def test_returns_transaction_when_owned_by_user(
        self,
        verifier: OwnershipVerifier,
        mock_transaction_repo: AsyncMock,
        mock_account_repo: AsyncMock,
        mock_connection_repo: AsyncMock,
        mock_transaction: Transaction,
        mock_account: Account,
        mock_connection: ProviderConnection,
        user_id,
        transaction_id,
    ) -> None:
        """Should return Success with transaction when user owns it."""
        mock_transaction_repo.find_by_id.return_value = mock_transaction
        mock_account_repo.find_by_id.return_value = mock_account
        mock_connection_repo.find_by_id.return_value = mock_connection

        result = await verifier.verify_transaction_ownership(transaction_id, user_id)

        assert isinstance(result, Success)
        assert result.value == mock_transaction
        mock_transaction_repo.find_by_id.assert_called_once_with(transaction_id)

    @pytest.mark.asyncio
    async def test_returns_failure_when_transaction_not_found(
        self,
        verifier: OwnershipVerifier,
        mock_transaction_repo: AsyncMock,
        user_id,
        transaction_id,
    ) -> None:
        """Should return Failure when transaction doesn't exist."""
        mock_transaction_repo.find_by_id.return_value = None

        result = await verifier.verify_transaction_ownership(transaction_id, user_id)

        assert isinstance(result, Failure)
        assert result.error.code == OwnershipErrorCode.TRANSACTION_NOT_FOUND
        assert "transaction" in result.error.message.lower()

    @pytest.mark.asyncio
    async def test_returns_failure_when_account_not_found(
        self,
        verifier: OwnershipVerifier,
        mock_transaction_repo: AsyncMock,
        mock_account_repo: AsyncMock,
        mock_transaction: Transaction,
        user_id,
        transaction_id,
    ) -> None:
        """Should return Failure when transaction's account doesn't exist."""
        mock_transaction_repo.find_by_id.return_value = mock_transaction
        mock_account_repo.find_by_id.return_value = None

        result = await verifier.verify_transaction_ownership(transaction_id, user_id)

        assert isinstance(result, Failure)
        assert result.error.code == OwnershipErrorCode.ACCOUNT_NOT_FOUND

    @pytest.mark.asyncio
    async def test_returns_failure_when_not_owned_by_user(
        self,
        verifier: OwnershipVerifier,
        mock_transaction_repo: AsyncMock,
        mock_account_repo: AsyncMock,
        mock_connection_repo: AsyncMock,
        mock_transaction: Transaction,
        mock_account: Account,
        mock_connection: ProviderConnection,
        other_user_id,
        transaction_id,
    ) -> None:
        """Should return Failure when transaction's connection owned by different user."""
        mock_transaction_repo.find_by_id.return_value = mock_transaction
        mock_account_repo.find_by_id.return_value = mock_account
        mock_connection_repo.find_by_id.return_value = mock_connection

        result = await verifier.verify_transaction_ownership(
            transaction_id, other_user_id
        )

        assert isinstance(result, Failure)
        assert result.error.code == OwnershipErrorCode.NOT_OWNED_BY_USER
