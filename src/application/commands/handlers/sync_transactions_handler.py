"""SyncTransactions command handler.

Handles blocking transaction synchronization from provider connections.
Fetches transaction data from provider API and upserts to repository.

Architecture:
    - Application layer handler (orchestrates sync)
    - Blocking operation (not background job)
    - Uses provider adapter for external API calls
    - Syncs transactions for all accounts under a connection

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/api-design-patterns.md
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from uuid_extensions import uuid7

from src.application.commands.sync_commands import SyncTransactions
from src.core.result import Failure, Result, Success
from src.domain.entities.transaction import Transaction
from src.domain.enums.asset_type import AssetType
from src.domain.enums.transaction_status import TransactionStatus
from src.domain.enums.transaction_subtype import TransactionSubtype
from src.domain.enums.transaction_type import TransactionType
from src.domain.protocols.account_repository import AccountRepository
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)
from src.domain.protocols.provider_protocol import (
    ProviderProtocol,
    ProviderTransactionData,
)
from src.domain.protocols.transaction_repository import TransactionRepository
from src.domain.value_objects.money import Money
from src.infrastructure.providers.encryption_service import EncryptionService


@dataclass
class SyncTransactionsResult:
    """Result of transaction sync operation.

    Attributes:
        created: Number of new transactions created.
        updated: Number of existing transactions updated.
        unchanged: Number of transactions unchanged.
        errors: Number of transactions that failed to sync.
        accounts_synced: Number of accounts processed.
        message: Human-readable summary.
    """

    created: int
    updated: int
    unchanged: int
    errors: int
    accounts_synced: int
    message: str


class SyncTransactionsError:
    """SyncTransactions-specific errors."""

    CONNECTION_NOT_FOUND = "Provider connection not found"
    NOT_OWNED_BY_USER = "Provider connection not owned by user"
    CONNECTION_NOT_ACTIVE = "Provider connection is not active"
    ACCOUNT_NOT_FOUND = "Account not found"
    ACCOUNT_NOT_OWNED = "Account not owned by connection"
    CREDENTIALS_INVALID = "Provider credentials are invalid"
    CREDENTIALS_DECRYPTION_FAILED = "Failed to decrypt provider credentials"
    PROVIDER_ERROR = "Provider API error"
    NO_ACCOUNTS = "No accounts found for connection"


# Default date range for transaction sync (30 days)
DEFAULT_SYNC_DAYS = 30


class SyncTransactionsHandler:
    """Handler for SyncTransactions command.

    Synchronizes transaction data from provider to local repository.
    Blocking operation - waits for provider API response.

    Flow:
        1. Verify connection exists and is owned by user
        2. Decrypt provider credentials
        3. Get accounts for connection (or specific account)
        4. For each account: call provider.fetch_transactions()
        5. Upsert transactions to repository

    Dependencies (injected via constructor):
        - ProviderConnectionRepository: For connection lookup
        - AccountRepository: For account lookup
        - TransactionRepository: For transaction persistence
        - EncryptionService: For credential decryption
        - ProviderProtocol: Provider adapter (factory-created)
        - EventBus: For domain events

    Returns:
        Result[SyncTransactionsResult, str]: Success(result) or Failure(error)
    """

    def __init__(
        self,
        connection_repo: ProviderConnectionRepository,
        account_repo: AccountRepository,
        transaction_repo: TransactionRepository,
        encryption_service: EncryptionService,
        provider: ProviderProtocol,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            connection_repo: Provider connection repository.
            account_repo: Account repository.
            transaction_repo: Transaction repository.
            encryption_service: For decrypting credentials.
            provider: Provider adapter for API calls.
            event_bus: For publishing domain events.
        """
        self._connection_repo = connection_repo
        self._account_repo = account_repo
        self._transaction_repo = transaction_repo
        self._encryption_service = encryption_service
        self._provider = provider
        self._event_bus = event_bus

    async def handle(
        self, command: SyncTransactions
    ) -> Result[SyncTransactionsResult, str]:
        """Handle SyncTransactions command.

        Args:
            command: SyncTransactions command with connection_id, user_id, and date range.

        Returns:
            Success(SyncTransactionsResult): Sync completed with counts.
            Failure(error): Connection not found, not owned, or provider error.
        """
        # 1. Fetch connection
        connection = await self._connection_repo.find_by_id(command.connection_id)

        if connection is None:
            return Failure(error=SyncTransactionsError.CONNECTION_NOT_FOUND)

        # 2. Verify ownership
        if connection.user_id != command.user_id:
            return Failure(error=SyncTransactionsError.NOT_OWNED_BY_USER)

        # 3. Verify connection is active
        if not connection.is_connected():
            return Failure(error=SyncTransactionsError.CONNECTION_NOT_ACTIVE)

        # 4. Get and decrypt credentials
        if connection.credentials is None:
            return Failure(error=SyncTransactionsError.CREDENTIALS_INVALID)

        decrypt_result = self._encryption_service.decrypt(
            connection.credentials.encrypted_data
        )

        if isinstance(decrypt_result, Failure):
            return Failure(error=SyncTransactionsError.CREDENTIALS_DECRYPTION_FAILED)

        credentials_data = decrypt_result.value

        # 5. Get accounts to sync
        if command.account_id:
            # Sync specific account
            account = await self._account_repo.find_by_id(command.account_id)
            if account is None:
                return Failure(error=SyncTransactionsError.ACCOUNT_NOT_FOUND)
            if account.connection_id != connection.id:
                return Failure(error=SyncTransactionsError.ACCOUNT_NOT_OWNED)
            accounts = [account]
        else:
            # Sync all accounts for connection
            accounts = await self._account_repo.find_by_connection_id(
                connection_id=connection.id,
                active_only=True,
            )

        if not accounts:
            return Failure(error=SyncTransactionsError.NO_ACCOUNTS)

        # 6. Determine date range
        end_date = command.end_date or date.today()
        start_date = command.start_date or (
            end_date - timedelta(days=DEFAULT_SYNC_DAYS)
        )

        # 7. Sync transactions for each account
        total_created = 0
        total_updated = 0
        total_unchanged = 0
        total_errors = 0
        accounts_synced = 0

        for account in accounts:
            # Fetch transactions from provider (pass full credentials dict)
            # Provider extracts what it needs (access_token for OAuth, api_key for API Key, etc.)
            fetch_result = await self._provider.fetch_transactions(
                credentials=credentials_data,
                provider_account_id=account.provider_account_id,
                start_date=start_date,
                end_date=end_date,
            )

            if isinstance(fetch_result, Failure):
                # Log error but continue with other accounts
                total_errors += 1
                continue

            provider_transactions = fetch_result.value

            # Sync to repository
            sync_result = await self._sync_transactions_to_repository(
                account_id=account.id,
                provider_transactions=provider_transactions,
            )

            total_created += sync_result["created"]
            total_updated += sync_result["updated"]
            total_unchanged += sync_result["unchanged"]
            total_errors += sync_result["errors"]
            accounts_synced += 1

            # Mark account as synced
            account.mark_synced()
            await self._account_repo.save(account)

        total = total_created + total_updated + total_unchanged
        message = (
            f"Synced {total} transactions from {accounts_synced} accounts: "
            f"{total_created} created, {total_updated} updated, "
            f"{total_unchanged} unchanged"
        )
        if total_errors > 0:
            message += f", {total_errors} errors"

        return Success(
            value=SyncTransactionsResult(
                created=total_created,
                updated=total_updated,
                unchanged=total_unchanged,
                errors=total_errors,
                accounts_synced=accounts_synced,
                message=message,
            )
        )

    async def _sync_transactions_to_repository(
        self,
        account_id: UUID,
        provider_transactions: list[ProviderTransactionData],
    ) -> dict[str, int]:
        """Sync provider transactions to repository.

        Args:
            account_id: Account ID to associate transactions with.
            provider_transactions: Transactions fetched from provider.

        Returns:
            Dict with counts: created, updated, unchanged, errors.
        """
        created = 0
        updated = 0
        unchanged = 0
        errors = 0

        for provider_txn in provider_transactions:
            try:
                # Check if transaction exists
                existing = await self._transaction_repo.find_by_provider_transaction_id(
                    account_id=account_id,
                    provider_transaction_id=provider_txn.provider_transaction_id,
                )

                if existing is None:
                    # Create new transaction
                    transaction = self._create_transaction_from_provider_data(
                        account_id=account_id,
                        data=provider_txn,
                    )
                    await self._transaction_repo.save(transaction)
                    created += 1
                else:
                    # Transaction exists - check if status changed
                    # Transactions are immutable except status can change from PENDING → SETTLED
                    new_status = self._map_status(provider_txn.status)
                    if existing.status != new_status:
                        # Status changed - create updated transaction (immutable, so save as new version)
                        # For now, we don't update transactions since they're immutable
                        # A proper implementation would mark old as superseded
                        unchanged += 1
                    else:
                        unchanged += 1

            except Exception:
                # Log error but continue with other transactions
                errors += 1

        return {
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "errors": errors,
        }

    def _create_transaction_from_provider_data(
        self,
        account_id: UUID,
        data: ProviderTransactionData,
    ) -> Transaction:
        """Create Transaction entity from provider data.

        Args:
            account_id: Account ID to associate with.
            data: Transaction data from provider.

        Returns:
            New Transaction entity.
        """
        now = datetime.now(UTC)

        # Map transaction type
        transaction_type = self._map_transaction_type(data.transaction_type)

        # Map subtype
        subtype = self._map_subtype(data.subtype, transaction_type)

        # Map status
        status = self._map_status(data.status)

        # Map asset type (for trades)
        asset_type = None
        if data.asset_type:
            asset_type = self._map_asset_type(data.asset_type)

        # Create amount Money object
        amount = Money(amount=data.amount, currency=data.currency)

        # Create unit price if present
        unit_price = None
        if data.unit_price is not None:
            unit_price = Money(amount=data.unit_price, currency=data.currency)

        # Create commission if present
        commission = None
        if data.commission is not None:
            commission = Money(amount=data.commission, currency=data.currency)

        return Transaction(
            id=uuid7(),
            account_id=account_id,
            provider_transaction_id=data.provider_transaction_id,
            transaction_type=transaction_type,
            subtype=subtype,
            status=status,
            amount=amount,
            description=data.description,
            asset_type=asset_type,
            symbol=data.symbol,
            security_name=data.security_name,
            quantity=data.quantity,
            unit_price=unit_price,
            commission=commission,
            transaction_date=data.transaction_date,
            settlement_date=data.settlement_date,
            provider_metadata=data.raw_data,
            created_at=now,
            updated_at=now,
        )

    def _map_transaction_type(self, provider_type: str) -> TransactionType:
        """Map provider transaction type to domain enum.

        Args:
            provider_type: Transaction type string from provider.

        Returns:
            TransactionType enum value.
        """
        type_upper = provider_type.upper()

        # Trade-related types
        if type_upper in (
            "TRADE",
            "BUY",
            "SELL",
            "SHORT",
            "COVER",
            "OPTION",
            "EXERCISE",
        ):
            return TransactionType.TRADE

        # Transfer types
        if type_upper in (
            "TRANSFER",
            "DEPOSIT",
            "WITHDRAWAL",
            "ACH",
            "WIRE",
            "JOURNAL",
        ):
            return TransactionType.TRANSFER

        # Income types
        if type_upper in ("DIVIDEND", "INTEREST", "CAPITAL_GAIN", "DISTRIBUTION"):
            return TransactionType.INCOME

        # Fee types
        if type_upper in ("FEE", "COMMISSION", "MARGIN_INTEREST", "MANAGEMENT_FEE"):
            return TransactionType.FEE

        return TransactionType.OTHER

    def _map_subtype(
        self, provider_subtype: str | None, transaction_type: TransactionType
    ) -> TransactionSubtype:
        """Map provider subtype to domain enum.

        Args:
            provider_subtype: Subtype string from provider.
            transaction_type: Already-mapped transaction type.

        Returns:
            TransactionSubtype enum value.
        """
        if not provider_subtype:
            # Default subtypes based on type
            if transaction_type == TransactionType.TRADE:
                return TransactionSubtype.BUY
            if transaction_type == TransactionType.TRANSFER:
                return TransactionSubtype.DEPOSIT
            if transaction_type == TransactionType.INCOME:
                return TransactionSubtype.DIVIDEND
            if transaction_type == TransactionType.FEE:
                return TransactionSubtype.ACCOUNT_FEE
            return TransactionSubtype.UNKNOWN

        subtype_upper = provider_subtype.upper()

        # Trade subtypes
        if subtype_upper in ("BUY", "PURCHASE"):
            return TransactionSubtype.BUY
        if subtype_upper in ("SELL", "SALE"):
            return TransactionSubtype.SELL
        if subtype_upper == "SHORT_SELL":
            return TransactionSubtype.SHORT_SELL
        if subtype_upper == "BUY_TO_COVER":
            return TransactionSubtype.BUY_TO_COVER

        # Transfer subtypes
        if subtype_upper in ("DEPOSIT", "ACH_IN", "WIRE_IN"):
            return TransactionSubtype.DEPOSIT
        if subtype_upper in ("WITHDRAWAL", "ACH_OUT", "WIRE_OUT"):
            return TransactionSubtype.WITHDRAWAL
        if subtype_upper in ("TRANSFER_IN", "JOURNAL_IN"):
            return TransactionSubtype.TRANSFER_IN
        if subtype_upper in ("TRANSFER_OUT", "JOURNAL_OUT"):
            return TransactionSubtype.TRANSFER_OUT

        # Income subtypes
        if subtype_upper == "DIVIDEND":
            return TransactionSubtype.DIVIDEND
        if subtype_upper == "INTEREST":
            return TransactionSubtype.INTEREST
        if subtype_upper in ("CAPITAL_GAIN", "CAP_GAIN"):
            return TransactionSubtype.CAPITAL_GAIN

        # Fee subtypes
        if subtype_upper in ("COMMISSION", "TRADE_FEE"):
            return TransactionSubtype.COMMISSION
        if subtype_upper in ("MARGIN_INTEREST", "MARGIN"):
            return TransactionSubtype.MARGIN_INTEREST
        if subtype_upper in ("FEE", "ACCOUNT_FEE"):
            return TransactionSubtype.ACCOUNT_FEE

        return TransactionSubtype.UNKNOWN

    def _map_status(self, provider_status: str) -> TransactionStatus:
        """Map provider status to domain enum.

        Args:
            provider_status: Status string from provider.

        Returns:
            TransactionStatus enum value.
        """
        status_upper = provider_status.upper()

        if status_upper in ("SETTLED", "EXECUTED", "COMPLETE", "COMPLETED"):
            return TransactionStatus.SETTLED
        if status_upper in ("PENDING", "PROCESSING", "IN_PROGRESS"):
            return TransactionStatus.PENDING
        if status_upper in ("FAILED", "REJECTED", "ERROR"):
            return TransactionStatus.FAILED
        if status_upper in ("CANCELLED", "CANCELED", "VOIDED"):
            return TransactionStatus.CANCELLED

        # Default to settled for historical transactions
        return TransactionStatus.SETTLED

    def _map_asset_type(self, provider_asset_type: str) -> AssetType:
        """Map provider asset type to domain enum.

        Args:
            provider_asset_type: Asset type string from provider.

        Returns:
            AssetType enum value.
        """
        type_upper = provider_asset_type.upper()

        if type_upper in ("EQUITY", "STOCK", "COMMON_STOCK"):
            return AssetType.EQUITY
        if type_upper in ("OPTION", "CALL", "PUT"):
            return AssetType.OPTION
        if type_upper == "ETF":
            return AssetType.ETF
        if type_upper in ("MUTUAL_FUND", "FUND"):
            return AssetType.MUTUAL_FUND
        if type_upper in ("FIXED_INCOME", "BOND"):
            return AssetType.FIXED_INCOME
        if type_upper in ("CASH", "MONEY_MARKET"):
            return AssetType.CASH_EQUIVALENT
        if type_upper in ("CRYPTO", "CRYPTOCURRENCY"):
            return AssetType.CRYPTOCURRENCY

        return AssetType.OTHER
