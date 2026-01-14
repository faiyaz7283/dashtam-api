"""Integration tests for Chase file import flow.

Tests cover:
- QFX file parsing with real ofxparse library
- Account creation from file data
- Transaction import with duplicate detection
- Full import flow with real database
- Re-import same file (idempotency)

Architecture:
- Integration tests with REAL PostgreSQL database
- Uses test_database fixture (fresh instance per test)
- Tests actual parsing, mapping, and persistence
- Async tests for database operations
"""

from decimal import Decimal
from unittest.mock import Mock

import pytest
import pytest_asyncio
from sqlalchemy import text
from uuid_extensions import uuid7

from src.core.result import Failure, Success
from src.domain.enums.account_type import AccountType
from src.infrastructure.persistence.repositories.account_repository import (
    AccountRepository,
)
from src.infrastructure.persistence.repositories.provider_connection_repository import (
    ProviderConnectionRepository,
)
from src.infrastructure.persistence.repositories.provider_repository import (
    ProviderRepository,
)
from src.infrastructure.persistence.repositories.transaction_repository import (
    TransactionRepository,
)
from src.infrastructure.providers.chase import ChaseFileProvider
from src.infrastructure.providers.chase.parsers.qfx_parser import QfxParser


# =============================================================================
# Sample QFX File Content
# =============================================================================


SAMPLE_QFX_CHECKING = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<DTSERVER>20241215120000
<LANGUAGE>ENG
<FI>
<ORG>Chase
<FID>10898
</FI>
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>0
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<STMTRS>
<CURDEF>USD
<BANKACCTFROM>
<BANKID>021000021
<ACCTID>123456789
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20241101
<DTEND>20241215
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20241210
<TRNAMT>-50.00
<FITID>202412100001
<NAME>AMAZON PURCHASE
<MEMO>Online Shopping
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20241205
<TRNAMT>2500.00
<FITID>202412050001
<NAME>DIRECT DEPOSIT
<MEMO>Payroll
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20241201
<TRNAMT>-75.50
<FITID>202412010001
<NAME>GROCERY STORE
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>5432.10
<DTASOF>20241215
</LEDGERBAL>
<AVAILBAL>
<BALAMT>5432.10
<DTASOF>20241215
</AVAILBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>"""


SAMPLE_QFX_SAVINGS = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<DTSERVER>20241215120000
<LANGUAGE>ENG
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>0
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<STMTRS>
<CURDEF>USD
<BANKACCTFROM>
<BANKID>021000021
<ACCTID>987654321
<ACCTTYPE>SAVINGS
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20241101
<DTEND>20241215
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20241201
<TRNAMT>100.00
<FITID>SAV202412010001
<NAME>INTEREST PAYMENT
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>10100.00
<DTASOF>20241215
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>"""


# =============================================================================
# Test Helpers
# =============================================================================


async def create_user_in_db(session, user_id=None, email=None):
    """Create a user in the database for FK constraint."""
    from src.infrastructure.persistence.models.user import User as UserModel

    user_id = user_id or uuid7()
    email = email or f"test_{user_id}@example.com"

    user = UserModel(
        id=user_id,
        email=email,
        password_hash="$2b$12$test_hash",
        is_verified=True,
        is_active=True,
        failed_login_attempts=0,
    )
    session.add(user)
    await session.commit()
    return user_id


def create_mock_provider_factory(provider):
    """Create a mock ProviderFactoryProtocol that returns the given provider."""
    factory = Mock()
    factory.get_provider.return_value = provider
    return factory


async def create_chase_provider_in_db(session):
    """Create Chase file provider in database if not exists."""
    # Check if provider exists
    result = await session.execute(
        text("SELECT id FROM providers WHERE slug = 'chase_file' LIMIT 1")
    )
    row = result.fetchone()
    if row:
        return row[0]

    # Create provider
    provider_id = uuid7()
    await session.execute(
        text("""
            INSERT INTO providers (id, slug, name, category, credential_type, is_active, created_at, updated_at)
            VALUES (:id, 'chase_file', 'Chase Bank (File Import)', 'bank', 'file_import', true, NOW(), NOW())
        """),
        {"id": provider_id},
    )
    await session.commit()
    return provider_id


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(test_database):
    """Clean up tables before each test."""
    async with test_database.get_session() as session:
        await session.execute(text("TRUNCATE TABLE transactions CASCADE"))
        await session.execute(text("TRUNCATE TABLE accounts CASCADE"))
        await session.execute(
            text("DELETE FROM provider_connections WHERE provider_slug = 'chase_file'")
        )
        await session.commit()
    yield


@pytest_asyncio.fixture
async def chase_provider(test_database):
    """Ensure Chase file provider exists in database."""
    async with test_database.get_session() as session:
        provider_id = await create_chase_provider_in_db(session)
    return provider_id


@pytest_asyncio.fixture
async def test_user(test_database):
    """Create a test user."""
    async with test_database.get_session() as session:
        user_id = await create_user_in_db(session)
    return user_id


# =============================================================================
# QFX Parser Integration Tests
# =============================================================================


@pytest.mark.integration
class TestQfxParserIntegration:
    """Test QFX parser with real ofxparse library."""

    def test_parse_checking_account(self):
        """Test parsing a checking account QFX file."""
        # Arrange
        parser = QfxParser()

        # Act
        result = parser.parse(SAMPLE_QFX_CHECKING, "checking.qfx")

        # Assert
        assert isinstance(result, Success)
        parsed = result.value

        assert parsed.account_id == "123456789"
        assert parsed.account_type == "CHECKING"
        assert parsed.bank_id == "021000021"
        assert parsed.currency == "USD"

        # Verify balance
        assert parsed.balance is not None
        assert parsed.balance.ledger_balance == Decimal("5432.10")

        # Verify transactions
        assert len(parsed.transactions) == 3

    def test_parse_savings_account(self):
        """Test parsing a savings account QFX file."""
        # Arrange
        parser = QfxParser()

        # Act
        result = parser.parse(SAMPLE_QFX_SAVINGS, "savings.qfx")

        # Assert
        assert isinstance(result, Success)
        parsed = result.value

        assert parsed.account_id == "987654321"
        assert parsed.account_type == "SAVINGS"
        assert len(parsed.transactions) == 1

    def test_parse_invalid_content_returns_failure(self):
        """Test parsing invalid content returns Failure."""
        # Arrange
        parser = QfxParser()

        # Act
        result = parser.parse(b"not valid qfx content", "invalid.qfx")

        # Assert
        assert isinstance(result, Failure)
        assert "parse" in result.error.message.lower()


# =============================================================================
# Chase File Provider Integration Tests
# =============================================================================


@pytest.mark.integration
class TestChaseFileProviderIntegration:
    """Test ChaseFileProvider with real parsing."""

    @pytest.mark.asyncio
    async def test_fetch_accounts_returns_provider_account_data(self):
        """Test fetch_accounts parses file and returns ProviderAccountData."""
        # Arrange
        provider = ChaseFileProvider()
        credentials = {
            "file_content": SAMPLE_QFX_CHECKING,
            "file_format": "qfx",
            "file_name": "checking.qfx",
        }

        # Act
        result = await provider.fetch_accounts(credentials)

        # Assert
        assert isinstance(result, Success)
        accounts = result.value
        assert len(accounts) == 1

        account = accounts[0]
        assert account.provider_account_id == "123456789"
        assert account.account_type == "checking"
        assert account.balance == Decimal("5432.10")
        assert account.currency == "USD"

    @pytest.mark.asyncio
    async def test_fetch_transactions_returns_provider_transaction_data(self):
        """Test fetch_transactions parses file and returns transactions."""
        # Arrange
        provider = ChaseFileProvider()
        credentials = {
            "file_content": SAMPLE_QFX_CHECKING,
            "file_format": "qfx",
            "file_name": "checking.qfx",
        }

        # Act
        result = await provider.fetch_transactions(
            credentials, provider_account_id="123456789"
        )

        # Assert
        assert isinstance(result, Success)
        transactions = result.value
        assert len(transactions) == 3

        # Verify transaction details
        fitids = {txn.provider_transaction_id for txn in transactions}
        assert "202412100001" in fitids
        assert "202412050001" in fitids
        assert "202412010001" in fitids

    @pytest.mark.asyncio
    async def test_fetch_transactions_wrong_account_returns_empty(self):
        """Test fetching transactions for non-existent account returns empty."""
        # Arrange
        provider = ChaseFileProvider()
        credentials = {
            "file_content": SAMPLE_QFX_CHECKING,
            "file_format": "qfx",
            "file_name": "checking.qfx",
        }

        # Act
        result = await provider.fetch_transactions(
            credentials, provider_account_id="wrong_account"
        )

        # Assert
        assert isinstance(result, Success)
        assert result.value == []


# =============================================================================
# Import Handler Integration Tests (with Database)
# =============================================================================


@pytest.mark.integration
class TestImportHandlerIntegration:
    """Test ImportFromFileHandler with real database operations."""

    @pytest.mark.asyncio
    async def test_import_creates_account_and_transactions(
        self, test_database, test_user, chase_provider
    ):
        """Test import creates account and transactions in database."""
        from src.application.commands.handlers.import_from_file_handler import (
            ImportFromFileHandler,
        )
        from src.application.commands.import_commands import ImportFromFile
        from src.core.container import get_event_bus

        async with test_database.get_session() as session:
            # Arrange
            connection_repo = ProviderConnectionRepository(session=session)
            account_repo = AccountRepository(session=session)
            transaction_repo = TransactionRepository(session=session)
            provider_repo = ProviderRepository(session=session)
            provider = ChaseFileProvider()
            event_bus = get_event_bus()

            handler = ImportFromFileHandler(
                connection_repo=connection_repo,
                account_repo=account_repo,
                transaction_repo=transaction_repo,
                provider_repo=provider_repo,
                provider_factory=create_mock_provider_factory(provider),
                event_bus=event_bus,
            )

            command = ImportFromFile(
                user_id=test_user,
                provider_slug="chase_file",
                file_content=SAMPLE_QFX_CHECKING,
                file_format="qfx",
                file_name="checking.qfx",
            )

            # Act
            result = await handler.handle(command)

            # Assert
            assert isinstance(result, Success)
            import_result = result.value

            assert import_result.accounts_created == 1
            assert import_result.accounts_updated == 0
            assert import_result.transactions_created == 3
            assert import_result.transactions_skipped == 0

            # Verify in database
            accounts = await account_repo.find_by_user_id(test_user)
            assert len(accounts) == 1
            assert accounts[0].provider_account_id == "123456789"
            assert accounts[0].account_type == AccountType.CHECKING
            assert accounts[0].balance.amount == Decimal("5432.10")

    @pytest.mark.asyncio
    async def test_reimport_same_file_skips_duplicates(
        self, test_database, test_user, chase_provider
    ):
        """Test re-importing same file skips duplicate transactions."""
        from src.application.commands.handlers.import_from_file_handler import (
            ImportFromFileHandler,
        )
        from src.application.commands.import_commands import ImportFromFile
        from src.core.container import get_event_bus

        async with test_database.get_session() as session:
            # Arrange
            connection_repo = ProviderConnectionRepository(session=session)
            account_repo = AccountRepository(session=session)
            transaction_repo = TransactionRepository(session=session)
            provider_repo = ProviderRepository(session=session)
            provider = ChaseFileProvider()
            event_bus = get_event_bus()

            handler = ImportFromFileHandler(
                connection_repo=connection_repo,
                account_repo=account_repo,
                transaction_repo=transaction_repo,
                provider_repo=provider_repo,
                provider_factory=create_mock_provider_factory(provider),
                event_bus=event_bus,
            )

            command = ImportFromFile(
                user_id=test_user,
                provider_slug="chase_file",
                file_content=SAMPLE_QFX_CHECKING,
                file_format="qfx",
                file_name="checking.qfx",
            )

            # Act - First import
            result1 = await handler.handle(command)

            # Force commit for second handler instance
            await session.commit()

        # Second import with new session
        async with test_database.get_session() as session2:
            connection_repo2 = ProviderConnectionRepository(session=session2)
            account_repo2 = AccountRepository(session=session2)
            transaction_repo2 = TransactionRepository(session=session2)
            provider_repo2 = ProviderRepository(session=session2)

            handler2 = ImportFromFileHandler(
                connection_repo=connection_repo2,
                account_repo=account_repo2,
                transaction_repo=transaction_repo2,
                provider_repo=provider_repo2,
                provider_factory=create_mock_provider_factory(provider),
                event_bus=event_bus,
            )

            # Act - Second import (same file)
            result2 = await handler2.handle(command)

            # Assert
            assert isinstance(result1, Success)
            assert isinstance(result2, Success)

            # First import created everything
            assert result1.value.accounts_created == 1
            assert result1.value.transactions_created == 3

            # Second import skipped duplicates
            assert result2.value.accounts_created == 0
            assert result2.value.accounts_updated == 1  # Existing account updated
            assert result2.value.transactions_created == 0
            assert result2.value.transactions_skipped == 3  # All duplicates

    @pytest.mark.asyncio
    async def test_import_multiple_files_same_user(
        self, test_database, test_user, chase_provider
    ):
        """Test importing multiple files for same user uses same connection."""
        from src.application.commands.handlers.import_from_file_handler import (
            ImportFromFileHandler,
        )
        from src.application.commands.import_commands import ImportFromFile
        from src.core.container import get_event_bus

        async with test_database.get_session() as session:
            # Arrange
            connection_repo = ProviderConnectionRepository(session=session)
            account_repo = AccountRepository(session=session)
            transaction_repo = TransactionRepository(session=session)
            provider_repo = ProviderRepository(session=session)
            provider = ChaseFileProvider()
            event_bus = get_event_bus()

            handler = ImportFromFileHandler(
                connection_repo=connection_repo,
                account_repo=account_repo,
                transaction_repo=transaction_repo,
                provider_repo=provider_repo,
                provider_factory=create_mock_provider_factory(provider),
                event_bus=event_bus,
            )

            # Act - Import checking account
            command1 = ImportFromFile(
                user_id=test_user,
                provider_slug="chase_file",
                file_content=SAMPLE_QFX_CHECKING,
                file_format="qfx",
                file_name="checking.qfx",
            )
            result1 = await handler.handle(command1)

            await session.commit()

        async with test_database.get_session() as session2:
            connection_repo2 = ProviderConnectionRepository(session=session2)
            account_repo2 = AccountRepository(session=session2)
            transaction_repo2 = TransactionRepository(session=session2)
            provider_repo2 = ProviderRepository(session=session2)

            handler2 = ImportFromFileHandler(
                connection_repo=connection_repo2,
                account_repo=account_repo2,
                transaction_repo=transaction_repo2,
                provider_repo=provider_repo2,
                provider_factory=create_mock_provider_factory(provider),
                event_bus=event_bus,
            )

            # Act - Import savings account
            command2 = ImportFromFile(
                user_id=test_user,
                provider_slug="chase_file",
                file_content=SAMPLE_QFX_SAVINGS,
                file_format="qfx",
                file_name="savings.qfx",
            )
            result2 = await handler2.handle(command2)

            # Assert
            assert isinstance(result1, Success)
            assert isinstance(result2, Success)

            # Same connection used for both
            assert result1.value.connection_id == result2.value.connection_id

            # Two accounts created total
            accounts = await account_repo2.find_by_user_id(test_user)
            assert len(accounts) == 2

            account_ids = {acc.provider_account_id for acc in accounts}
            assert "123456789" in account_ids  # Checking
            assert "987654321" in account_ids  # Savings
