"""Balance snapshot query handlers.

Handles requests to retrieve balance history and snapshots.
Returns DTOs for API responses.

Architecture:
- Application layer handlers (orchestrate data retrieval)
- Returns Result[DTO, str] (explicit error handling)
- NO domain events (queries are side-effect free)
- Account-scoped and user-scoped queries

Reference:
    - docs/architecture/cqrs-pattern.md
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from src.application.queries.balance_snapshot_queries import (
    GetBalanceHistory,
    GetLatestBalanceSnapshots,
    GetUserBalanceHistory,
    ListBalanceSnapshotsByAccount,
)
from src.core.result import Failure, Result, Success
from src.domain.entities.balance_snapshot import BalanceSnapshot
from src.domain.enums.snapshot_source import SnapshotSource
from src.domain.protocols.account_repository import AccountRepository
from src.domain.protocols.balance_snapshot_repository import BalanceSnapshotRepository
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)


@dataclass
class BalanceSnapshotResult:
    """Single balance snapshot DTO for API responses.

    Attributes:
        id: Snapshot ID.
        account_id: Account ID.
        balance: Total account balance.
        available_balance: Available balance (nullable).
        holdings_value: Total holdings value (nullable).
        cash_value: Cash balance (nullable).
        currency: ISO 4217 currency code.
        source: How snapshot was captured.
        captured_at: When balance was captured.
        created_at: Record creation timestamp.
        change_amount: Change from previous snapshot (nullable).
        change_percent: Percentage change (nullable).
    """

    id: UUID
    account_id: UUID
    balance: Decimal
    available_balance: Decimal | None
    holdings_value: Decimal | None
    cash_value: Decimal | None
    currency: str
    source: str
    captured_at: datetime
    created_at: datetime
    change_amount: Decimal | None = None
    change_percent: float | None = None


@dataclass
class BalanceHistoryResult:
    """List of balance snapshots for charting.

    Includes computed metrics for change tracking.

    Attributes:
        snapshots: List of snapshot DTOs (ordered by time).
        total_count: Total number of snapshots in range.
        start_balance: Balance at start of period.
        end_balance: Balance at end of period.
        total_change_amount: Change over period.
        total_change_percent: Percentage change over period.
        currency: Currency of the values.
    """

    snapshots: list[BalanceSnapshotResult]
    total_count: int
    start_balance: Decimal | None
    end_balance: Decimal | None
    total_change_amount: Decimal | None
    total_change_percent: float | None
    currency: str | None


@dataclass
class LatestSnapshotsResult:
    """Latest snapshots for all accounts.

    Used for portfolio summary dashboard.

    Attributes:
        snapshots: List of latest snapshot DTOs (one per account).
        total_count: Number of accounts with snapshots.
        total_balance: Aggregate balance across all accounts (by currency).
    """

    snapshots: list[BalanceSnapshotResult]
    total_count: int
    total_balance_by_currency: dict[str, str]


class BalanceSnapshotQueryError:
    """Balance snapshot query errors."""

    ACCOUNT_NOT_FOUND = "Account not found"
    CONNECTION_NOT_FOUND = "Provider connection not found"
    NOT_OWNED_BY_USER = "Account not owned by user"
    INVALID_DATE_RANGE = "Start date must be before end date"
    INVALID_SOURCE = "Invalid snapshot source"


class GetBalanceHistoryHandler:
    """Handler for GetBalanceHistory query.

    Retrieves balance history for an account within a date range.
    Returns snapshots ordered chronologically for charting.

    Dependencies:
        - BalanceSnapshotRepository: For snapshot retrieval
        - AccountRepository: For account lookup
        - ProviderConnectionRepository: For ownership verification
    """

    def __init__(
        self,
        snapshot_repo: BalanceSnapshotRepository,
        account_repo: AccountRepository,
        connection_repo: ProviderConnectionRepository,
    ) -> None:
        """Initialize handler with dependencies."""
        self._snapshot_repo = snapshot_repo
        self._account_repo = account_repo
        self._connection_repo = connection_repo

    async def handle(
        self, query: GetBalanceHistory
    ) -> Result[BalanceHistoryResult, str]:
        """Handle GetBalanceHistory query.

        Args:
            query: GetBalanceHistory query with account_id and date range.

        Returns:
            Success(BalanceHistoryResult): Snapshots found.
            Failure(error): Account not found, not owned, or invalid query.
        """
        # Validate date range
        if query.start_date >= query.end_date:
            return Failure(error=BalanceSnapshotQueryError.INVALID_DATE_RANGE)

        # Validate source if provided
        source: SnapshotSource | None = None
        if query.source is not None:
            try:
                source = SnapshotSource(query.source)
            except ValueError:
                return Failure(error=BalanceSnapshotQueryError.INVALID_SOURCE)

        # Verify ownership
        ownership_result = await self._verify_account_ownership(
            query.account_id, query.user_id
        )
        if isinstance(ownership_result, Failure):
            return ownership_result

        # Fetch snapshots
        snapshots = await self._snapshot_repo.find_by_account_id_in_range(
            account_id=query.account_id,
            start_date=query.start_date,
            end_date=query.end_date,
            source=source,
        )

        return Success(value=self._build_history_result(snapshots))

    async def _verify_account_ownership(
        self, account_id: UUID, user_id: UUID
    ) -> Result[None, str]:
        """Verify user owns the account."""
        account = await self._account_repo.find_by_id(account_id)
        if account is None:
            return Failure(error=BalanceSnapshotQueryError.ACCOUNT_NOT_FOUND)

        connection = await self._connection_repo.find_by_id(account.connection_id)
        if connection is None:
            return Failure(error=BalanceSnapshotQueryError.CONNECTION_NOT_FOUND)

        if connection.user_id != user_id:
            return Failure(error=BalanceSnapshotQueryError.NOT_OWNED_BY_USER)

        return Success(value=None)

    def _build_history_result(
        self, snapshots: list[BalanceSnapshot]
    ) -> BalanceHistoryResult:
        """Build BalanceHistoryResult from snapshots."""
        if not snapshots:
            return BalanceHistoryResult(
                snapshots=[],
                total_count=0,
                start_balance=None,
                end_balance=None,
                total_change_amount=None,
                total_change_percent=None,
                currency=None,
            )

        # Build DTOs with change calculations
        snapshot_dtos: list[BalanceSnapshotResult] = []
        prev_snapshot: BalanceSnapshot | None = None

        for snapshot in snapshots:
            dto = self._snapshot_to_dto(snapshot, prev_snapshot)
            snapshot_dtos.append(dto)
            prev_snapshot = snapshot

        # Compute period summary
        first = snapshots[0]
        last = snapshots[-1]
        total_change = last.balance - first.balance
        total_percent: float | None = None
        if first.balance.amount != 0:
            total_percent = float((total_change.amount / first.balance.amount) * 100)

        return BalanceHistoryResult(
            snapshots=snapshot_dtos,
            total_count=len(snapshots),
            start_balance=first.balance.amount,
            end_balance=last.balance.amount,
            total_change_amount=total_change.amount,
            total_change_percent=total_percent,
            currency=first.currency,
        )

    def _snapshot_to_dto(
        self,
        snapshot: BalanceSnapshot,
        prev_snapshot: BalanceSnapshot | None = None,
    ) -> BalanceSnapshotResult:
        """Convert snapshot entity to DTO with optional change calculation."""
        change_amount: Decimal | None = None
        change_percent: float | None = None

        if prev_snapshot is not None:
            result = snapshot.calculate_change_from(prev_snapshot)
            if result is not None:
                change_money, change_percent = result
                change_amount = change_money.amount

        return BalanceSnapshotResult(
            id=snapshot.id,
            account_id=snapshot.account_id,
            balance=snapshot.balance.amount,
            available_balance=(
                snapshot.available_balance.amount
                if snapshot.available_balance
                else None
            ),
            holdings_value=(
                snapshot.holdings_value.amount if snapshot.holdings_value else None
            ),
            cash_value=snapshot.cash_value.amount if snapshot.cash_value else None,
            currency=snapshot.currency,
            source=snapshot.source.value,
            captured_at=snapshot.captured_at,
            created_at=snapshot.created_at,
            change_amount=change_amount,
            change_percent=change_percent,
        )


class ListBalanceSnapshotsByAccountHandler:
    """Handler for ListBalanceSnapshotsByAccount query.

    Retrieves recent snapshots for an account.
    Returns snapshots ordered by captured_at descending (most recent first).

    Dependencies:
        - BalanceSnapshotRepository: For snapshot retrieval
        - AccountRepository: For account lookup
        - ProviderConnectionRepository: For ownership verification
    """

    def __init__(
        self,
        snapshot_repo: BalanceSnapshotRepository,
        account_repo: AccountRepository,
        connection_repo: ProviderConnectionRepository,
    ) -> None:
        """Initialize handler with dependencies."""
        self._snapshot_repo = snapshot_repo
        self._account_repo = account_repo
        self._connection_repo = connection_repo

    async def handle(
        self, query: ListBalanceSnapshotsByAccount
    ) -> Result[BalanceHistoryResult, str]:
        """Handle ListBalanceSnapshotsByAccount query.

        Args:
            query: ListBalanceSnapshotsByAccount query.

        Returns:
            Success(BalanceHistoryResult): Snapshots found.
            Failure(error): Account not found or not owned.
        """
        # Validate source if provided
        source: SnapshotSource | None = None
        if query.source is not None:
            try:
                source = SnapshotSource(query.source)
            except ValueError:
                return Failure(error=BalanceSnapshotQueryError.INVALID_SOURCE)

        # Verify ownership
        account = await self._account_repo.find_by_id(query.account_id)
        if account is None:
            return Failure(error=BalanceSnapshotQueryError.ACCOUNT_NOT_FOUND)

        connection = await self._connection_repo.find_by_id(account.connection_id)
        if connection is None:
            return Failure(error=BalanceSnapshotQueryError.CONNECTION_NOT_FOUND)

        if connection.user_id != query.user_id:
            return Failure(error=BalanceSnapshotQueryError.NOT_OWNED_BY_USER)

        # Fetch snapshots (already ordered by captured_at desc)
        snapshots = await self._snapshot_repo.find_by_account_id(
            account_id=query.account_id,
            source=source,
            limit=query.limit,
        )

        # Convert to DTOs (no change calculation for list view)
        snapshot_dtos = [self._snapshot_to_dto(s) for s in snapshots]

        # Build result
        currency = snapshots[0].currency if snapshots else None

        return Success(
            value=BalanceHistoryResult(
                snapshots=snapshot_dtos,
                total_count=len(snapshots),
                start_balance=None,
                end_balance=None,
                total_change_amount=None,
                total_change_percent=None,
                currency=currency,
            )
        )

    def _snapshot_to_dto(self, snapshot: BalanceSnapshot) -> BalanceSnapshotResult:
        """Convert snapshot entity to DTO."""
        return BalanceSnapshotResult(
            id=snapshot.id,
            account_id=snapshot.account_id,
            balance=snapshot.balance.amount,
            available_balance=(
                snapshot.available_balance.amount
                if snapshot.available_balance
                else None
            ),
            holdings_value=(
                snapshot.holdings_value.amount if snapshot.holdings_value else None
            ),
            cash_value=snapshot.cash_value.amount if snapshot.cash_value else None,
            currency=snapshot.currency,
            source=snapshot.source.value,
            captured_at=snapshot.captured_at,
            created_at=snapshot.created_at,
        )


class GetLatestBalanceSnapshotsHandler:
    """Handler for GetLatestBalanceSnapshots query.

    Retrieves the most recent snapshot for each of user's accounts.
    Used for portfolio summary dashboard.

    Dependencies:
        - BalanceSnapshotRepository: For snapshot retrieval
    """

    def __init__(self, snapshot_repo: BalanceSnapshotRepository) -> None:
        """Initialize handler with dependencies."""
        self._snapshot_repo = snapshot_repo

    async def handle(
        self, query: GetLatestBalanceSnapshots
    ) -> Result[LatestSnapshotsResult, str]:
        """Handle GetLatestBalanceSnapshots query.

        Args:
            query: GetLatestBalanceSnapshots query with user_id.

        Returns:
            Success(LatestSnapshotsResult): Latest snapshots for all accounts.
        """
        # Fetch latest snapshot per account
        snapshots = await self._snapshot_repo.find_latest_by_user_id(query.user_id)

        # Convert to DTOs
        snapshot_dtos = [self._snapshot_to_dto(s) for s in snapshots]

        # Aggregate by currency
        balance_by_currency: dict[str, Decimal] = {}
        for snapshot in snapshots:
            currency = snapshot.currency
            balance_by_currency[currency] = (
                balance_by_currency.get(currency, Decimal("0"))
                + snapshot.balance.amount
            )

        # Format as strings
        total_balance_by_currency = {
            currency: str(amount) for currency, amount in balance_by_currency.items()
        }

        return Success(
            value=LatestSnapshotsResult(
                snapshots=snapshot_dtos,
                total_count=len(snapshots),
                total_balance_by_currency=total_balance_by_currency,
            )
        )

    def _snapshot_to_dto(self, snapshot: BalanceSnapshot) -> BalanceSnapshotResult:
        """Convert snapshot entity to DTO."""
        return BalanceSnapshotResult(
            id=snapshot.id,
            account_id=snapshot.account_id,
            balance=snapshot.balance.amount,
            available_balance=(
                snapshot.available_balance.amount
                if snapshot.available_balance
                else None
            ),
            holdings_value=(
                snapshot.holdings_value.amount if snapshot.holdings_value else None
            ),
            cash_value=snapshot.cash_value.amount if snapshot.cash_value else None,
            currency=snapshot.currency,
            source=snapshot.source.value,
            captured_at=snapshot.captured_at,
            created_at=snapshot.created_at,
        )


class GetUserBalanceHistoryHandler:
    """Handler for GetUserBalanceHistory query.

    Retrieves balance history across all user accounts.
    Used for aggregate portfolio charting.

    Dependencies:
        - BalanceSnapshotRepository: For snapshot retrieval
    """

    def __init__(self, snapshot_repo: BalanceSnapshotRepository) -> None:
        """Initialize handler with dependencies."""
        self._snapshot_repo = snapshot_repo

    async def handle(
        self, query: GetUserBalanceHistory
    ) -> Result[BalanceHistoryResult, str]:
        """Handle GetUserBalanceHistory query.

        Args:
            query: GetUserBalanceHistory query with user_id and date range.

        Returns:
            Success(BalanceHistoryResult): Snapshots across all accounts.
            Failure(error): Invalid query parameters.
        """
        # Validate date range
        if query.start_date >= query.end_date:
            return Failure(error=BalanceSnapshotQueryError.INVALID_DATE_RANGE)

        # Validate source if provided
        source: SnapshotSource | None = None
        if query.source is not None:
            try:
                source = SnapshotSource(query.source)
            except ValueError:
                return Failure(error=BalanceSnapshotQueryError.INVALID_SOURCE)

        # Fetch snapshots across all accounts
        snapshots = await self._snapshot_repo.find_by_user_id_in_range(
            user_id=query.user_id,
            start_date=query.start_date,
            end_date=query.end_date,
            source=source,
        )

        # Convert to DTOs
        snapshot_dtos = [self._snapshot_to_dto(s) for s in snapshots]

        # Simple summary (no per-snapshot change for aggregate view)
        currency = snapshots[0].currency if snapshots else None

        return Success(
            value=BalanceHistoryResult(
                snapshots=snapshot_dtos,
                total_count=len(snapshots),
                start_balance=None,
                end_balance=None,
                total_change_amount=None,
                total_change_percent=None,
                currency=currency,
            )
        )

    def _snapshot_to_dto(self, snapshot: BalanceSnapshot) -> BalanceSnapshotResult:
        """Convert snapshot entity to DTO."""
        return BalanceSnapshotResult(
            id=snapshot.id,
            account_id=snapshot.account_id,
            balance=snapshot.balance.amount,
            available_balance=(
                snapshot.available_balance.amount
                if snapshot.available_balance
                else None
            ),
            holdings_value=(
                snapshot.holdings_value.amount if snapshot.holdings_value else None
            ),
            cash_value=snapshot.cash_value.amount if snapshot.cash_value else None,
            currency=snapshot.currency,
            source=snapshot.source.value,
            captured_at=snapshot.captured_at,
            created_at=snapshot.created_at,
        )
