"""SyncHoldings command handler.

Handles blocking holdings (positions) synchronization from provider connections.
Fetches holdings data from provider API and upserts to repository.

Architecture:
    - Application layer handler (orchestrates sync)
    - Blocking operation (not background job)
    - Uses provider adapter for external API calls
    - Syncs holdings for a specific account

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/api-design-patterns.md
"""

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from uuid_extensions import uuid7

from src.application.commands.sync_commands import SyncHoldings
from src.application.dtos import SyncHoldingsResult
from src.core.result import Failure, Result, Success
from src.domain.entities.holding import Holding
from src.domain.enums.asset_type import AssetType
from src.domain.events.data_events import (
    HoldingsSyncAttempted,
    HoldingsSyncFailed,
    HoldingsSyncSucceeded,
)
from src.domain.protocols.account_repository import AccountRepository
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.holding_repository import HoldingRepository
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)
from src.domain.protocols.provider_factory_protocol import ProviderFactoryProtocol
from src.domain.protocols.provider_protocol import ProviderHoldingData
from src.domain.protocols.encryption_protocol import EncryptionProtocol
from src.domain.value_objects.money import Money


class SyncHoldingsError:
    """SyncHoldings-specific errors."""

    ACCOUNT_NOT_FOUND = "Account not found"
    CONNECTION_NOT_FOUND = "Provider connection not found"
    NOT_OWNED_BY_USER = "Account not owned by user"
    CONNECTION_NOT_ACTIVE = "Provider connection is not active"
    CREDENTIALS_INVALID = "Provider credentials are invalid"
    CREDENTIALS_DECRYPTION_FAILED = "Failed to decrypt provider credentials"
    PROVIDER_ERROR = "Provider API error"
    RECENTLY_SYNCED = "Holdings were recently synced"


# Minimum time between syncs (unless force=True)
MIN_SYNC_INTERVAL = timedelta(minutes=5)


class SyncHoldingsHandler:
    """Handler for SyncHoldings command.

    Synchronizes holdings data from provider to local repository.
    Blocking operation - waits for provider API response.

    Flow:
        1. Verify account exists and is owned by user
        2. Get provider connection and verify it's active
        3. Check if sync is needed (unless force=True)
        4. Decrypt provider credentials
        5. Call provider.fetch_holdings()
        6. Upsert holdings to repository
        7. Deactivate holdings no longer in provider
        8. Update account last_sync_at

    Dependencies (injected via constructor):
        - AccountRepository: For account lookup
        - ProviderConnectionRepository: For connection lookup
        - HoldingRepository: For holding persistence
        - EncryptionService: For credential decryption
        - ProviderFactoryProtocol: Factory for runtime provider resolution
        - EventBus: For domain events
    """

    def __init__(
        self,
        account_repo: AccountRepository,
        connection_repo: ProviderConnectionRepository,
        holding_repo: HoldingRepository,
        encryption_service: EncryptionProtocol,
        provider_factory: ProviderFactoryProtocol,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            account_repo: Account repository.
            connection_repo: Provider connection repository.
            holding_repo: Holding repository.
            encryption_service: For decrypting credentials.
            provider_factory: Factory for runtime provider resolution.
            event_bus: For publishing domain events.
        """
        self._account_repo = account_repo
        self._connection_repo = connection_repo
        self._holding_repo = holding_repo
        self._encryption_service = encryption_service
        self._provider_factory = provider_factory
        self._event_bus = event_bus

    async def handle(self, command: SyncHoldings) -> Result[SyncHoldingsResult, str]:
        """Handle SyncHoldings command.

        Args:
            command: SyncHoldings command with account_id and user_id.

        Returns:
            Success(SyncHoldingsResult): Sync completed with counts.
            Failure(error): Account not found, not owned, or provider error.
        """
        # 1. Emit ATTEMPTED event
        await self._event_bus.publish(
            HoldingsSyncAttempted(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                account_id=command.account_id,
                user_id=command.user_id,
            )
        )

        # 2. Fetch account
        account = await self._account_repo.find_by_id(command.account_id)

        if account is None:
            await self._event_bus.publish(
                HoldingsSyncFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    account_id=command.account_id,
                    user_id=command.user_id,
                    reason="account_not_found",
                )
            )
            return cast(
                Result[SyncHoldingsResult, str],
                Failure(error=SyncHoldingsError.ACCOUNT_NOT_FOUND),
            )

        # 3. Fetch connection
        connection = await self._connection_repo.find_by_id(account.connection_id)

        if connection is None:
            await self._event_bus.publish(
                HoldingsSyncFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    account_id=command.account_id,
                    user_id=command.user_id,
                    reason="connection_not_found",
                )
            )
            return cast(
                Result[SyncHoldingsResult, str],
                Failure(error=SyncHoldingsError.CONNECTION_NOT_FOUND),
            )

        # 4. Verify ownership
        if connection.user_id != command.user_id:
            await self._event_bus.publish(
                HoldingsSyncFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    account_id=command.account_id,
                    user_id=command.user_id,
                    reason="not_owned_by_user",
                )
            )
            return cast(
                Result[SyncHoldingsResult, str],
                Failure(error=SyncHoldingsError.NOT_OWNED_BY_USER),
            )

        # 5. Verify connection is active
        if not connection.is_connected():
            await self._event_bus.publish(
                HoldingsSyncFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    account_id=command.account_id,
                    user_id=command.user_id,
                    reason="connection_not_active",
                )
            )
            return cast(
                Result[SyncHoldingsResult, str],
                Failure(error=SyncHoldingsError.CONNECTION_NOT_ACTIVE),
            )

        # 6. Check if recently synced (unless force=True)
        if not command.force and account.last_synced_at:
            time_since_sync = datetime.now(UTC) - account.last_synced_at
            if time_since_sync < MIN_SYNC_INTERVAL:
                await self._event_bus.publish(
                    HoldingsSyncFailed(
                        event_id=uuid7(),
                        occurred_at=datetime.now(UTC),
                        account_id=command.account_id,
                        user_id=command.user_id,
                        reason="recently_synced",
                    )
                )
                return cast(
                    Result[SyncHoldingsResult, str],
                    Failure(error=SyncHoldingsError.RECENTLY_SYNCED),
                )

        # 7. Get and decrypt credentials
        if connection.credentials is None:
            await self._event_bus.publish(
                HoldingsSyncFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    account_id=command.account_id,
                    user_id=command.user_id,
                    reason="credentials_invalid",
                )
            )
            return cast(
                Result[SyncHoldingsResult, str],
                Failure(error=SyncHoldingsError.CREDENTIALS_INVALID),
            )

        decrypt_result = self._encryption_service.decrypt(
            connection.credentials.encrypted_data
        )

        if isinstance(decrypt_result, Failure):
            await self._event_bus.publish(
                HoldingsSyncFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    account_id=command.account_id,
                    user_id=command.user_id,
                    reason="credentials_decryption_failed",
                )
            )
            return cast(
                Result[SyncHoldingsResult, str],
                Failure(error=SyncHoldingsError.CREDENTIALS_DECRYPTION_FAILED),
            )

        credentials_data = decrypt_result.value

        # 8. Resolve provider from connection slug
        provider = self._provider_factory.get_provider(connection.provider_slug)

        # 9. Fetch holdings from provider (pass full credentials dict)
        # Provider extracts what it needs (access_token for OAuth, api_key for API Key, etc.)
        fetch_result = await provider.fetch_holdings(
            credentials=credentials_data,
            provider_account_id=account.provider_account_id,
        )

        if isinstance(fetch_result, Failure):
            await self._event_bus.publish(
                HoldingsSyncFailed(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    account_id=command.account_id,
                    user_id=command.user_id,
                    reason=f"provider_error:{fetch_result.error.message}",
                )
            )
            return Failure(
                error=f"{SyncHoldingsError.PROVIDER_ERROR}: {fetch_result.error.message}"
            )

        provider_holdings = fetch_result.value

        # 10. Sync holdings to repository
        sync_result = await self._sync_holdings_to_repository(
            account_id=account.id,
            provider_holdings=provider_holdings,
        )

        # 11. Update account last_sync_at
        account.mark_synced()
        await self._account_repo.save(account)

        # 12. Emit SUCCEEDED event
        total_holdings = (
            sync_result.created + sync_result.updated + sync_result.unchanged
        )
        await self._event_bus.publish(
            HoldingsSyncSucceeded(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                account_id=command.account_id,
                user_id=command.user_id,
                holding_count=total_holdings,
            )
        )

        return Success(value=sync_result)

    async def _sync_holdings_to_repository(
        self,
        account_id: UUID,
        provider_holdings: list[ProviderHoldingData],
    ) -> SyncHoldingsResult:
        """Sync provider holdings to repository using upsert logic.

        Also deactivates holdings that are no longer in the provider response.

        Args:
            account_id: Account ID.
            provider_holdings: Holdings fetched from provider.

        Returns:
            SyncHoldingsResult with counts.
        """
        created = 0
        updated = 0
        unchanged = 0
        deactivated = 0
        errors = 0

        # Track which provider_holding_ids we see
        seen_provider_ids: set[str] = set()

        for provider_holding in provider_holdings:
            try:
                seen_provider_ids.add(provider_holding.provider_holding_id)

                # Check if holding exists
                existing = await self._holding_repo.find_by_provider_holding_id(
                    account_id=account_id,
                    provider_holding_id=provider_holding.provider_holding_id,
                )

                if existing is None:
                    # Create new holding
                    holding = self._create_holding_from_provider_data(
                        account_id=account_id,
                        data=provider_holding,
                    )
                    await self._holding_repo.save(holding)
                    created += 1
                else:
                    # Update existing holding
                    was_updated = self._update_holding_from_provider_data(
                        holding=existing,
                        data=provider_holding,
                    )
                    if was_updated:
                        await self._holding_repo.save(existing)
                        updated += 1
                    else:
                        unchanged += 1

            except Exception:
                # Log error but continue with other holdings
                errors += 1

        # Deactivate holdings no longer in provider response
        existing_holdings = await self._holding_repo.list_by_account(
            account_id=account_id,
            active_only=True,
        )

        for holding in existing_holdings:
            if holding.provider_holding_id not in seen_provider_ids:
                try:
                    holding.deactivate()
                    await self._holding_repo.save(holding)
                    deactivated += 1
                except Exception:
                    errors += 1

        total = created + updated + unchanged
        message = (
            f"Synced {total} holdings: "
            f"{created} created, {updated} updated, {unchanged} unchanged"
        )
        if deactivated > 0:
            message += f", {deactivated} deactivated"
        if errors > 0:
            message += f", {errors} errors"

        return SyncHoldingsResult(
            created=created,
            updated=updated,
            unchanged=unchanged,
            deactivated=deactivated,
            errors=errors,
            message=message,
        )

    def _create_holding_from_provider_data(
        self,
        account_id: UUID,
        data: ProviderHoldingData,
    ) -> Holding:
        """Create Holding entity from provider data.

        Args:
            account_id: Account ID.
            data: Holding data from provider.

        Returns:
            New Holding entity.
        """
        # Convert asset_type string to AssetType enum
        asset_type = AssetType(data.asset_type)

        # Convert Decimal values to Money
        cost_basis = Money(amount=data.cost_basis, currency=data.currency)
        market_value = Money(amount=data.market_value, currency=data.currency)
        average_price = (
            Money(amount=data.average_price, currency=data.currency)
            if data.average_price is not None
            else None
        )
        current_price = (
            Money(amount=data.current_price, currency=data.currency)
            if data.current_price is not None
            else None
        )

        return Holding(
            id=uuid7(),
            account_id=account_id,
            provider_holding_id=data.provider_holding_id,
            symbol=data.symbol,
            security_name=data.security_name,
            asset_type=asset_type,
            quantity=data.quantity,
            cost_basis=cost_basis,
            market_value=market_value,
            currency=data.currency,
            average_price=average_price,
            current_price=current_price,
            is_active=True,
            last_synced_at=datetime.now(UTC),
            provider_metadata=data.raw_data,
        )

    def _update_holding_from_provider_data(
        self,
        holding: Holding,
        data: ProviderHoldingData,
    ) -> bool:
        """Update existing Holding from provider data.

        Args:
            holding: Existing holding entity.
            data: Fresh data from provider.

        Returns:
            True if holding was modified, False if unchanged.
        """
        # Convert Decimal values to Money
        cost_basis = Money(amount=data.cost_basis, currency=holding.currency)
        market_value = Money(amount=data.market_value, currency=holding.currency)
        current_price = (
            Money(amount=data.current_price, currency=holding.currency)
            if data.current_price is not None
            else None
        )

        # Use the entity's update_from_sync method
        holding.update_from_sync(
            quantity=data.quantity,
            cost_basis=cost_basis,
            market_value=market_value,
            current_price=current_price,
            provider_metadata=data.raw_data,
        )

        # Mark as synced
        holding.mark_synced()

        # Always return True since update_from_sync always marks as updated
        return True
