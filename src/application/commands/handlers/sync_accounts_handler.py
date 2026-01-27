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

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from uuid_extensions import uuid7

from src.application.commands.sync_commands import SyncAccounts
from src.application.dtos import BalanceChange, SyncAccountsResult
from src.core.result import Failure, Result, Success
from src.domain.entities.account import Account
from src.domain.enums.account_type import AccountType
from src.domain.events.data_events import (
    AccountSyncAttempted,
    AccountSyncFailed,
    AccountSyncSucceeded,
)
from src.domain.events.portfolio_events import AccountBalanceUpdated
from src.domain.protocols.account_repository import AccountRepository
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)
from src.domain.protocols.provider_factory_protocol import ProviderFactoryProtocol
from src.domain.protocols.provider_protocol import ProviderAccountData
from src.domain.protocols.encryption_protocol import EncryptionProtocol
from src.domain.value_objects.money import Money


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
        - ProviderFactoryProtocol: Factory for runtime provider resolution
        - EventBus: For domain events
    """

    def __init__(
        self,
        connection_repo: ProviderConnectionRepository,
        account_repo: AccountRepository,
        encryption_service: EncryptionProtocol,
        provider_factory: ProviderFactoryProtocol,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            connection_repo: Provider connection repository.
            account_repo: Account repository.
            encryption_service: For decrypting credentials.
            provider_factory: Factory for runtime provider resolution.
            event_bus: For publishing domain events.
        """
        self._connection_repo = connection_repo
        self._account_repo = account_repo
        self._encryption_service = encryption_service
        self._provider_factory = provider_factory
        self._event_bus = event_bus

    async def handle(self, command: SyncAccounts) -> Result[SyncAccountsResult, str]:
        """Handle SyncAccounts command.

        Args:
            command: SyncAccounts command with connection_id and user_id.

        Returns:
            Success(SyncAccountsResult): Sync completed with counts.
            Failure(error): Connection not found, not owned, or provider error.
        """
        # 1. Emit ATTEMPTED event
        await self._event_bus.publish(
            AccountSyncAttempted(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                connection_id=command.connection_id,
                user_id=command.user_id,
            )
        )

        # 2. Fetch connection
        connection = await self._connection_repo.find_by_id(command.connection_id)

        if connection is None:
            await self._event_bus.publish(
                AccountSyncFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    connection_id=command.connection_id,
                    user_id=command.user_id,
                    reason="connection_not_found",
                )
            )
            return cast(
                Result[SyncAccountsResult, str],
                Failure(error=SyncAccountsError.CONNECTION_NOT_FOUND),
            )

        # 3. Verify ownership
        if connection.user_id != command.user_id:
            await self._event_bus.publish(
                AccountSyncFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    connection_id=command.connection_id,
                    user_id=command.user_id,
                    reason="not_owned_by_user",
                )
            )
            return cast(
                Result[SyncAccountsResult, str],
                Failure(error=SyncAccountsError.NOT_OWNED_BY_USER),
            )

        # 4. Verify connection is active
        if not connection.is_connected():
            await self._event_bus.publish(
                AccountSyncFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    connection_id=command.connection_id,
                    user_id=command.user_id,
                    reason="connection_not_active",
                )
            )
            return cast(
                Result[SyncAccountsResult, str],
                Failure(error=SyncAccountsError.CONNECTION_NOT_ACTIVE),
            )

        # 5. Check if recently synced (unless force=True)
        if not command.force and connection.last_sync_at:
            time_since_sync = datetime.now(UTC) - connection.last_sync_at
            if time_since_sync < MIN_SYNC_INTERVAL:
                await self._event_bus.publish(
                    AccountSyncFailed(
                        event_id=uuid7(),
                        occurred_at=datetime.now(UTC),
                        connection_id=command.connection_id,
                        user_id=command.user_id,
                        reason="recently_synced",
                    )
                )
                return cast(
                    Result[SyncAccountsResult, str],
                    Failure(error=SyncAccountsError.RECENTLY_SYNCED),
                )

        # 6. Get and decrypt credentials
        if connection.credentials is None:
            await self._event_bus.publish(
                AccountSyncFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    connection_id=command.connection_id,
                    user_id=command.user_id,
                    reason="credentials_invalid",
                )
            )
            return cast(
                Result[SyncAccountsResult, str],
                Failure(error=SyncAccountsError.CREDENTIALS_INVALID),
            )

        decrypt_result = self._encryption_service.decrypt(
            connection.credentials.encrypted_data
        )

        if isinstance(decrypt_result, Failure):
            await self._event_bus.publish(
                AccountSyncFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    connection_id=command.connection_id,
                    user_id=command.user_id,
                    reason="credentials_decryption_failed",
                )
            )
            return cast(
                Result[SyncAccountsResult, str],
                Failure(error=SyncAccountsError.CREDENTIALS_DECRYPTION_FAILED),
            )

        credentials_data = decrypt_result.value

        # 7. Resolve provider from connection slug
        provider = self._provider_factory.get_provider(connection.provider_slug)

        # 8. Fetch accounts from provider (pass full credentials dict)
        # Provider extracts what it needs (access_token for OAuth, api_key for API Key, etc.)
        fetch_result = await provider.fetch_accounts(credentials_data)

        if isinstance(fetch_result, Failure):
            await self._event_bus.publish(
                AccountSyncFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    connection_id=command.connection_id,
                    user_id=command.user_id,
                    reason=f"provider_error:{fetch_result.error.message}",
                )
            )
            return Failure(
                error=f"{SyncAccountsError.PROVIDER_ERROR}: {fetch_result.error.message}"
            )

        provider_accounts = fetch_result.value

        # 9. Sync accounts to repository
        sync_result = await self._sync_accounts_to_repository(
            connection_id=connection.id,
            provider_accounts=provider_accounts,
        )

        # 10. Update connection last_sync_at
        connection.record_sync()
        await self._connection_repo.save(connection)

        # 11. Emit SUCCEEDED event
        total_accounts = (
            sync_result.created + sync_result.updated + sync_result.unchanged
        )
        await self._event_bus.publish(
            AccountSyncSucceeded(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                connection_id=command.connection_id,
                user_id=command.user_id,
                account_count=total_accounts,
            )
        )

        # 12. Emit balance change events for portfolio notifications
        for balance_change in sync_result.balance_changes:
            await self._event_bus.publish(
                AccountBalanceUpdated(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    user_id=command.user_id,
                    account_id=balance_change.account_id,
                    previous_balance=balance_change.previous,
                    new_balance=balance_change.current,
                    delta=balance_change.current - balance_change.previous,
                    currency=balance_change.currency,
                )
            )

        return Success(value=sync_result)

    async def _sync_accounts_to_repository(
        self,
        connection_id: UUID,
        provider_accounts: list[ProviderAccountData],
    ) -> SyncAccountsResult:
        """Sync provider accounts to repository using upsert logic.

        Tracks balance changes for portfolio notifications.

        Args:
            connection_id: Provider connection ID.
            provider_accounts: Accounts fetched from provider.

        Returns:
            SyncAccountsResult with counts and balance changes.
        """
        created = 0
        updated = 0
        unchanged = 0
        errors = 0
        balance_changes: list[BalanceChange] = []

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
                    # New account - balance went from 0 to new_balance
                    if provider_account.balance != 0:
                        balance_changes.append(
                            BalanceChange(
                                account_id=account.id,
                                previous=provider_account.balance.__class__(0),
                                current=provider_account.balance,
                                currency=provider_account.currency,
                            )
                        )
                else:
                    # Track previous balance before update
                    previous_balance = existing.balance.amount

                    # Update existing account
                    was_updated = self._update_account_from_provider_data(
                        account=existing,
                        data=provider_account,
                    )
                    if was_updated:
                        await self._account_repo.save(existing)
                        updated += 1
                        # Check if balance changed
                        if previous_balance != provider_account.balance:
                            balance_changes.append(
                                BalanceChange(
                                    account_id=existing.id,
                                    previous=previous_balance,
                                    current=provider_account.balance,
                                    currency=provider_account.currency,
                                )
                            )
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
            balance_changes=balance_changes,
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
