"""ImportFromFile command handler.

Handles file-based data imports for providers like Chase QFX.
Creates provider connection, accounts, and transactions from uploaded file.

Architecture:
    - Application layer handler
    - Orchestrates: parse file → create/find connection → upsert accounts → upsert transactions
    - Uses file-based provider (ChaseFileProvider) that parses file content
    - Emits domain events for SSE progress streaming (Issue #256)

Flow:
    1. Emit FileImportAttempted event
    2. Get or create provider connection for user
    3. Parse file via provider.fetch_accounts() (credentials = file content)
    4. Upsert accounts to repository
    5. Fetch transactions via provider.fetch_transactions()
    6. Upsert transactions to repository (with duplicate detection by FITID)
    7. Emit FileImportProgress events during transaction processing
    8. Emit FileImportSucceeded or FileImportFailed event
    9. Return import results

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/sse-architecture.md (Section 3.2, Import Events)
"""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from uuid_extensions import uuid7

from src.application.commands.import_commands import ImportFromFile
from src.application.dtos import ImportResult
from src.core.result import Failure, Result, Success
from src.domain.entities.account import Account
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.entities.transaction import Transaction
from src.domain.enums.account_type import AccountType
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.enums.credential_type import CredentialType
from src.domain.enums.transaction_subtype import TransactionSubtype
from src.domain.enums.transaction_status import TransactionStatus
from src.domain.enums.transaction_type import TransactionType
from src.domain.protocols.account_repository import AccountRepository
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)
from src.domain.protocols.provider_factory_protocol import ProviderFactoryProtocol
from src.domain.protocols.provider_protocol import (
    ProviderAccountData,
    ProviderTransactionData,
)
from src.domain.protocols.provider_repository import ProviderRepository
from src.domain.protocols.transaction_repository import TransactionRepository
from src.domain.value_objects.money import Money
from src.domain.value_objects.provider_credentials import ProviderCredentials
from src.domain.events.data_events import (
    FileImportAttempted,
    FileImportFailed,
    FileImportProgress,
    FileImportSucceeded,
)


class ImportFromFileError:
    """ImportFromFile-specific errors."""

    PROVIDER_NOT_FOUND = "Provider not found or not configured"
    INVALID_FILE = "Invalid or unparseable file"
    NO_ACCOUNTS = "File contains no account data"
    IMPORT_FAILED = "Import failed"


# Progress emission interval: emit every N records or N% progress
_PROGRESS_RECORD_INTERVAL = 100  # Emit every 100 records
_PROGRESS_PERCENT_INTERVAL = 5  # Or every 5% progress


class ImportFromFileHandler:
    """Handler for ImportFromFile command.

    Imports financial data from uploaded files (QFX, OFX, CSV).
    Creates provider connection and syncs accounts/transactions.

    Dependencies (injected via constructor):
        - ProviderConnectionRepository: For connection management
        - AccountRepository: For account persistence
        - TransactionRepository: For transaction persistence
        - ProviderRepository: For looking up provider by slug
        - ProviderFactoryProtocol: Factory for runtime provider resolution
        - EventBus: For domain events
    """

    def __init__(
        self,
        connection_repo: ProviderConnectionRepository,
        account_repo: AccountRepository,
        transaction_repo: TransactionRepository,
        provider_repo: ProviderRepository,
        provider_factory: ProviderFactoryProtocol,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            connection_repo: Provider connection repository.
            account_repo: Account repository.
            transaction_repo: Transaction repository.
            provider_repo: Provider repository for slug lookups.
            provider_factory: Factory for runtime provider resolution.
            event_bus: For publishing domain events.
        """
        self._connection_repo = connection_repo
        self._account_repo = account_repo
        self._transaction_repo = transaction_repo
        self._provider_repo = provider_repo
        self._provider_factory = provider_factory
        self._event_bus = event_bus

    async def handle(self, command: ImportFromFile) -> Result[ImportResult, str]:
        """Handle ImportFromFile command.

        Args:
            command: ImportFromFile command with file data.

        Returns:
            Success(ImportResult): Import completed with counts.
            Failure(error): Invalid file or import failed.
        """
        # 1. Emit FileImportAttempted event
        await self._event_bus.publish(
            FileImportAttempted(
                user_id=command.user_id,
                provider_slug=command.provider_slug,
                file_name=command.file_name,
                file_format=command.file_format,
            )
        )

        # 2. Resolve provider from command slug
        provider = self._provider_factory.get_provider(command.provider_slug)

        # Build credentials dict with file data
        credentials_data: dict[str, Any] = {
            "file_content": command.file_content,
            "file_format": command.file_format,
            "file_name": command.file_name,
        }

        # 3. Parse file via provider.fetch_accounts()
        accounts_result = await provider.fetch_accounts(credentials_data)

        if isinstance(accounts_result, Failure):
            error_msg = (
                f"{ImportFromFileError.INVALID_FILE}: {accounts_result.error.message}"
            )
            await self._emit_failed_event(command, error_msg)
            return Failure(error=error_msg)

        provider_accounts = accounts_result.value

        if not provider_accounts:
            await self._emit_failed_event(command, ImportFromFileError.NO_ACCOUNTS)
            return cast(
                Result[ImportResult, str],
                Failure(error=ImportFromFileError.NO_ACCOUNTS),
            )

        # 4. Look up provider to get provider_id
        provider_entity = await self._provider_repo.find_by_slug(command.provider_slug)
        if provider_entity is None:
            error_msg = (
                f"{ImportFromFileError.PROVIDER_NOT_FOUND}: {command.provider_slug}"
            )
            await self._emit_failed_event(command, error_msg)
            return Failure(error=error_msg)

        # 5. Get or create provider connection
        connection = await self._get_or_create_connection(
            user_id=command.user_id,
            provider_slug=command.provider_slug,
            provider_id=provider_entity.id,
        )

        # 6. Import accounts
        accounts_created = 0
        accounts_updated = 0
        account_map: dict[str, UUID] = {}  # provider_account_id -> account.id

        for provider_account in provider_accounts:
            account, was_created = await self._upsert_account(
                connection_id=connection.id,
                data=provider_account,
            )
            account_map[provider_account.provider_account_id] = account.id

            if was_created:
                accounts_created += 1
            else:
                accounts_updated += 1

        # 7. Collect all transactions to get total count for progress
        all_transactions: list[tuple[UUID, ProviderTransactionData]] = []
        for provider_account in provider_accounts:
            account_id = account_map[provider_account.provider_account_id]
            txn_result = await provider.fetch_transactions(
                credentials_data,
                provider_account_id=provider_account.provider_account_id,
            )
            if isinstance(txn_result, Success):
                for txn in txn_result.value:
                    all_transactions.append((account_id, txn))

        total_records = len(all_transactions)

        # 8. Import transactions with progress events
        transactions_created = 0
        transactions_skipped = 0
        last_progress_percent = 0

        for i, (account_id, provider_txn) in enumerate(all_transactions):
            was_created = await self._upsert_transaction(
                account_id=account_id,
                data=provider_txn,
            )
            if was_created:
                transactions_created += 1
            else:
                transactions_skipped += 1

            # Emit progress event at intervals
            records_processed = i + 1
            progress_percent = (
                (records_processed * 100) // total_records if total_records > 0 else 100
            )

            # Emit if: every N records OR crossed a percent threshold
            should_emit = (
                records_processed % _PROGRESS_RECORD_INTERVAL == 0
                or progress_percent
                >= last_progress_percent + _PROGRESS_PERCENT_INTERVAL
            )

            if should_emit and records_processed < total_records:
                await self._event_bus.publish(
                    FileImportProgress(
                        user_id=command.user_id,
                        provider_slug=command.provider_slug,
                        file_name=command.file_name,
                        file_format=command.file_format,
                        progress_percent=progress_percent,
                        records_processed=records_processed,
                        total_records=total_records,
                    )
                )
                last_progress_percent = progress_percent

        # 9. Update connection last_sync_at
        connection.record_sync()
        await self._connection_repo.save(connection)

        # 10. Emit FileImportSucceeded event
        await self._event_bus.publish(
            FileImportSucceeded(
                user_id=command.user_id,
                provider_slug=command.provider_slug,
                file_name=command.file_name,
                file_format=command.file_format,
                account_count=accounts_created + accounts_updated,
                transaction_count=transactions_created,
            )
        )

        # Build result
        message = (
            f"Imported from {command.file_name}: "
            f"{accounts_created} accounts created, {accounts_updated} updated, "
            f"{transactions_created} transactions imported, {transactions_skipped} skipped"
        )

        result = ImportResult(
            connection_id=connection.id,
            accounts_created=accounts_created,
            accounts_updated=accounts_updated,
            transactions_created=transactions_created,
            transactions_skipped=transactions_skipped,
            message=message,
        )

        return Success(value=result)

    async def _emit_failed_event(
        self,
        command: ImportFromFile,
        reason: str,
    ) -> None:
        """Emit FileImportFailed event.

        Args:
            command: Original import command.
            reason: Failure reason.
        """
        await self._event_bus.publish(
            FileImportFailed(
                user_id=command.user_id,
                provider_slug=command.provider_slug,
                file_name=command.file_name,
                file_format=command.file_format,
                reason=reason,
            )
        )

    async def _get_or_create_connection(
        self,
        user_id: UUID,
        provider_slug: str,
        provider_id: UUID,
    ) -> ProviderConnection:
        """Get existing connection or create new one for file imports.

        File-based providers use a single connection per user - all files
        are imported into the same connection.

        Args:
            user_id: User ID.
            provider_slug: Provider slug (e.g., "chase_file").
            provider_id: Provider ID from providers table.

        Returns:
            Existing or new ProviderConnection.
        """
        # Check for existing connection
        connections = await self._connection_repo.find_by_user_id(user_id)
        for conn in connections:
            if conn.provider_slug == provider_slug:
                return conn

        # Create new connection for file imports
        # File imports don't store credentials (file is processed immediately)
        connection = ProviderConnection(
            id=uuid7(),
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            status=ConnectionStatus.ACTIVE,
            credentials=ProviderCredentials(
                # Placeholder bytes - file imports don't persist credentials
                # ProviderCredentials requires non-empty data for validation
                encrypted_data=b"file_import_placeholder",
                credential_type=CredentialType.FILE_IMPORT,
                expires_at=None,  # File imports don't expire
            ),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        await self._connection_repo.save(connection)

        return connection

    async def _upsert_account(
        self,
        connection_id: UUID,
        data: ProviderAccountData,
    ) -> tuple[Account, bool]:
        """Upsert account from provider data.

        Args:
            connection_id: Provider connection ID.
            data: Account data from provider.

        Returns:
            Tuple of (Account, was_created).
        """
        # Check if account exists
        existing = await self._account_repo.find_by_provider_account_id(
            connection_id=connection_id,
            provider_account_id=data.provider_account_id,
        )

        if existing is None:
            # Create new account
            account = self._create_account(connection_id, data)
            await self._account_repo.save(account)
            return account, True
        else:
            # Update existing account
            self._update_account(existing, data)
            await self._account_repo.save(existing)
            return existing, False

    def _create_account(
        self,
        connection_id: UUID,
        data: ProviderAccountData,
    ) -> Account:
        """Create Account entity from provider data."""
        try:
            account_type = AccountType(data.account_type)
        except ValueError:
            account_type = AccountType.OTHER

        balance = Money(amount=data.balance, currency=data.currency)
        available_balance = None
        if data.available_balance is not None:
            available_balance = Money(
                amount=data.available_balance,
                currency=data.currency,
            )

        return Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id=data.provider_account_id,
            account_number_masked=data.account_number_masked,
            name=data.name,
            account_type=account_type,
            balance=balance,
            currency=data.currency,
            available_balance=available_balance,
            is_active=data.is_active,
            last_synced_at=datetime.now(UTC),
            provider_metadata=data.raw_data,
        )

    def _update_account(self, account: Account, data: ProviderAccountData) -> None:
        """Update existing Account from provider data."""
        new_balance = Money(amount=data.balance, currency=data.currency)
        available_balance = None
        if data.available_balance is not None:
            available_balance = Money(
                amount=data.available_balance,
                currency=data.currency,
            )

        if account.balance != new_balance:
            account.update_balance(
                balance=new_balance, available_balance=available_balance
            )

        if account.name != data.name:
            account.update_from_provider(name=data.name)

        if data.raw_data:
            account.update_from_provider(provider_metadata=data.raw_data)

        account.mark_synced()

    async def _upsert_transaction(
        self,
        account_id: UUID,
        data: ProviderTransactionData,
    ) -> bool:
        """Upsert transaction from provider data.

        Uses provider_transaction_id (FITID) for duplicate detection.

        Args:
            account_id: Account ID.
            data: Transaction data from provider.

        Returns:
            True if created, False if skipped (duplicate).
        """
        # Check for duplicate by provider_transaction_id
        existing = await self._transaction_repo.find_by_provider_transaction_id(
            account_id=account_id,
            provider_transaction_id=data.provider_transaction_id,
        )

        if existing is not None:
            # Duplicate - skip
            return False

        # Create new transaction
        transaction = self._create_transaction(account_id, data)
        await self._transaction_repo.save(transaction)
        return True

    def _create_transaction(
        self,
        account_id: UUID,
        data: ProviderTransactionData,
    ) -> Transaction:
        """Create Transaction entity from provider data."""
        # Map transaction type
        try:
            txn_type = TransactionType(data.transaction_type)
        except ValueError:
            txn_type = TransactionType.OTHER

        # Map subtype
        try:
            subtype = (
                TransactionSubtype(data.subtype)
                if data.subtype
                else TransactionSubtype.UNKNOWN
            )
        except ValueError:
            subtype = TransactionSubtype.UNKNOWN

        # Map status
        try:
            status = TransactionStatus(data.status)
        except ValueError:
            status = TransactionStatus.SETTLED

        amount = Money(amount=data.amount, currency=data.currency)

        now = datetime.now(UTC)

        return Transaction(
            id=uuid7(),
            account_id=account_id,
            provider_transaction_id=data.provider_transaction_id,
            transaction_type=txn_type,
            subtype=subtype,
            amount=amount,
            description=data.description,
            transaction_date=data.transaction_date,
            settlement_date=data.settlement_date,
            status=status,
            provider_metadata=data.raw_data,
            created_at=now,
            updated_at=now,
        )
