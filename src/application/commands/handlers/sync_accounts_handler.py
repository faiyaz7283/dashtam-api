"""SyncAccounts command handler.

Handles blocking account synchronization from provider connections.
Fetches account data from provider API and upserts to repository.

Architecture:
    - Application layer handler (orchestrates sync)
    - Blocking operation (not background job)
    - Uses provider adapter for external API calls
    - Publishes domain events for audit/observability

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/api-design-patterns.md
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from uuid_extensions import uuid7

from src.application.commands.sync_commands import SyncAccounts
from src.core.result import Failure, Result, Success
from src.domain.entities.account import Account
from src.domain.enums.account_type import AccountType
from src.domain.protocols.account_repository import AccountRepository
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)
from src.domain.protocols.provider_protocol import ProviderAccountData, ProviderProtocol
from src.domain.value_objects.money import Money
from src.infrastructure.providers.encryption_service import EncryptionService


@dataclass
class SyncAccountsResult:
    """Result of account sync operation.

    Attributes:
        created: Number of new accounts created.
        updated: Number of existing accounts updated.
        unchanged: Number of accounts unchanged.
        errors: Number of accounts that failed to sync.
        message: Human-readable summary.
    """

    created: int
    updated: int
    unchanged: int
    errors: int
    message: str


class SyncAccountsError:
    """SyncAccounts-specific errors."""

    CONNECTION_NOT_FOUND = "Provider connection not found"
    NOT_OWNED_BY_USER = "Provider connection not owned by user"
    CONNECTION_NOT_ACTIVE = "Provider connection is not active"
    CREDENTIALS_INVALID = "Provider credentials are invalid"
    CREDENTIALS_DECRYPTION_FAILED = "Failed to decrypt provider credentials"
    PROVIDER_ERROR = "Provider API error"
    RECENTLY_SYNCED = "Accounts were recently synced"


# Minimum time between syncs (unless force=True)
MIN_SYNC_INTERVAL = timedelta(minutes=5)


class SyncAccountsHandler:
    """Handler for SyncAccounts command.

    Synchronizes account data from provider to local repository.
    Blocking operation - waits for provider API response.

    Flow:
        1. Verify connection exists and is owned by user
        2. Check if sync is needed (unless force=True)
        3. Decrypt provider credentials
        4. Call provider.fetch_accounts()
        5. Upsert accounts to repository
        6. Update connection last_sync_at

    Dependencies (injected via constructor):
        - ProviderConnectionRepository: For connection lookup
        - AccountRepository: For account persistence
        - EncryptionService: For credential decryption
        - ProviderProtocol: Provider adapter (factory-created)
        - EventBus: For domain events
    """

    def __init__(
        self,
        connection_repo: ProviderConnectionRepository,
        account_repo: AccountRepository,
        encryption_service: EncryptionService,
        provider: ProviderProtocol,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            connection_repo: Provider connection repository.
            account_repo: Account repository.
            encryption_service: For decrypting credentials.
            provider: Provider adapter for API calls.
            event_bus: For publishing domain events.
        """
        self._connection_repo = connection_repo
        self._account_repo = account_repo
        self._encryption_service = encryption_service
        self._provider = provider
        self._event_bus = event_bus

    async def handle(self, command: SyncAccounts) -> Result[SyncAccountsResult, str]:
        """Handle SyncAccounts command.

        Args:
            command: SyncAccounts command with connection_id and user_id.

        Returns:
            Success(SyncAccountsResult): Sync completed with counts.
            Failure(error): Connection not found, not owned, or provider error.
        """
        # 1. Fetch connection
        connection = await self._connection_repo.find_by_id(command.connection_id)

        if connection is None:
            return cast(
                Result[SyncAccountsResult, str],
                Failure(error=SyncAccountsError.CONNECTION_NOT_FOUND),
            )

        # 2. Verify ownership
        if connection.user_id != command.user_id:
            return cast(
                Result[SyncAccountsResult, str],
                Failure(error=SyncAccountsError.NOT_OWNED_BY_USER),
            )

        # 3. Verify connection is active
        if not connection.is_connected():
            return cast(
                Result[SyncAccountsResult, str],
                Failure(error=SyncAccountsError.CONNECTION_NOT_ACTIVE),
            )

        # 4. Check if recently synced (unless force=True)
        if not command.force and connection.last_sync_at:
            time_since_sync = datetime.now(UTC) - connection.last_sync_at
            if time_since_sync < MIN_SYNC_INTERVAL:
                return cast(
                    Result[SyncAccountsResult, str],
                    Failure(error=SyncAccountsError.RECENTLY_SYNCED),
                )

        # 5. Get and decrypt credentials
        if connection.credentials is None:
            return cast(
                Result[SyncAccountsResult, str],
                Failure(error=SyncAccountsError.CREDENTIALS_INVALID),
            )

        decrypt_result = self._encryption_service.decrypt(
            connection.credentials.encrypted_data
        )

        if isinstance(decrypt_result, Failure):
            return cast(
                Result[SyncAccountsResult, str],
                Failure(error=SyncAccountsError.CREDENTIALS_DECRYPTION_FAILED),
            )

        credentials_data = decrypt_result.value

        # 6. Fetch accounts from provider (pass full credentials dict)
        # Provider extracts what it needs (access_token for OAuth, api_key for API Key, etc.)
        fetch_result = await self._provider.fetch_accounts(credentials_data)

        if isinstance(fetch_result, Failure):
            return Failure(
                error=f"{SyncAccountsError.PROVIDER_ERROR}: {fetch_result.error.message}"
            )

        provider_accounts = fetch_result.value

        # 7. Sync accounts to repository
        sync_result = await self._sync_accounts_to_repository(
            connection_id=connection.id,
            provider_accounts=provider_accounts,
        )

        # 8. Update connection last_sync_at
        connection.record_sync()
        await self._connection_repo.save(connection)

        return Success(value=sync_result)

    async def _sync_accounts_to_repository(
        self,
        connection_id: UUID,
        provider_accounts: list[ProviderAccountData],
    ) -> SyncAccountsResult:
        """Sync provider accounts to repository using upsert logic.

        Args:
            connection_id: Provider connection ID.
            provider_accounts: Accounts fetched from provider.

        Returns:
            SyncAccountsResult with counts.
        """
        created = 0
        updated = 0
        unchanged = 0
        errors = 0

        for provider_account in provider_accounts:
            try:
                # Check if account exists
                existing = await self._account_repo.find_by_provider_account_id(
                    connection_id=connection_id,
                    provider_account_id=provider_account.provider_account_id,
                )

                if existing is None:
                    # Create new account
                    account = self._create_account_from_provider_data(
                        connection_id=connection_id,
                        data=provider_account,
                    )
                    await self._account_repo.save(account)
                    created += 1
                else:
                    # Update existing account
                    was_updated = self._update_account_from_provider_data(
                        account=existing,
                        data=provider_account,
                    )
                    if was_updated:
                        await self._account_repo.save(existing)
                        updated += 1
                    else:
                        unchanged += 1

            except Exception:
                # Log error but continue with other accounts
                errors += 1

        total = created + updated + unchanged
        message = (
            f"Synced {total} accounts: "
            f"{created} created, {updated} updated, {unchanged} unchanged"
        )
        if errors > 0:
            message += f", {errors} errors"

        return SyncAccountsResult(
            created=created,
            updated=updated,
            unchanged=unchanged,
            errors=errors,
            message=message,
        )

    def _create_account_from_provider_data(
        self,
        connection_id: UUID,
        data: ProviderAccountData,
    ) -> Account:
        """Create Account entity from provider data.

        Args:
            connection_id: Provider connection ID.
            data: Account data from provider.

        Returns:
            New Account entity.
        """
        # Map account type string to enum
        try:
            account_type = AccountType(data.account_type)
        except ValueError:
            account_type = AccountType.OTHER

        # Create balance Money object
        balance = Money(amount=data.balance, currency=data.currency)

        # Create available balance if present
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

    def _update_account_from_provider_data(
        self,
        account: Account,
        data: ProviderAccountData,
    ) -> bool:
        """Update existing Account from provider data.

        Args:
            account: Existing account entity.
            data: Fresh data from provider.

        Returns:
            True if account was modified, False if unchanged.
        """
        changed = False

        # Check balance change
        new_balance = Money(amount=data.balance, currency=data.currency)
        if account.balance != new_balance:
            account.update_balance(
                balance=new_balance,
                available_balance=(
                    Money(amount=data.available_balance, currency=data.currency)
                    if data.available_balance is not None
                    else None
                ),
            )
            changed = True

        # Check name change
        if account.name != data.name:
            account.update_from_provider(name=data.name)
            changed = True

        # Check active status change
        if account.is_active != data.is_active:
            if data.is_active:
                account.activate()
            else:
                account.deactivate()
            changed = True

        # Update metadata
        if data.raw_data and account.provider_metadata != data.raw_data:
            account.update_from_provider(provider_metadata=data.raw_data)
            changed = True

        # Always mark as synced
        account.mark_synced()

        return changed
