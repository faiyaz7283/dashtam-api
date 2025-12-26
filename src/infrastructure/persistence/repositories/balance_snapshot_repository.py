"""BalanceSnapshotRepository - SQLAlchemy implementation.

Adapter for hexagonal architecture.
Maps between domain BalanceSnapshot entities and database BalanceSnapshotModel.

Reference:
    - docs/architecture/repository-pattern.md
    - src/domain/entities/balance_snapshot.py
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.balance_snapshot import BalanceSnapshot
from src.domain.enums.snapshot_source import SnapshotSource
from src.domain.value_objects.money import Money
from src.infrastructure.persistence.models.account import Account as AccountModel
from src.infrastructure.persistence.models.balance_snapshot import (
    BalanceSnapshot as BalanceSnapshotModel,
)
from src.infrastructure.persistence.models.provider_connection import (
    ProviderConnection as ProviderConnectionModel,
)


class BalanceSnapshotRepository:
    """SQLAlchemy implementation of BalanceSnapshotRepository protocol.

    This is an adapter that implements the BalanceSnapshotRepository port.
    It handles the mapping between domain BalanceSnapshot entities and
    database BalanceSnapshotModel.

    This class does NOT inherit from the protocol (Protocol uses structural typing).

    Note:
        Balance snapshots are immutable - no update methods are provided.
        The save() method only creates new records, never updates.

    Attributes:
        session: SQLAlchemy async session for database operations.

    Example:
        >>> async with get_session() as session:
        ...     repo = BalanceSnapshotRepository(session)
        ...     snapshots = await repo.find_by_account_id(account_id, limit=30)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def find_by_id(self, snapshot_id: UUID) -> BalanceSnapshot | None:
        """Find snapshot by ID.

        Args:
            snapshot_id: Snapshot's unique identifier.

        Returns:
            BalanceSnapshot if found, None otherwise.
        """
        stmt = select(BalanceSnapshotModel).where(
            BalanceSnapshotModel.id == snapshot_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def find_by_account_id(
        self,
        account_id: UUID,
        source: SnapshotSource | None = None,
        limit: int | None = None,
    ) -> list[BalanceSnapshot]:
        """Find all snapshots for an account.

        Results are ordered by captured_at descending (most recent first).

        Args:
            account_id: Account's unique identifier.
            source: Optional filter by snapshot source.
            limit: Optional maximum number of results.

        Returns:
            List of snapshots (empty if none found).
        """
        stmt = select(BalanceSnapshotModel).where(
            BalanceSnapshotModel.account_id == account_id
        )

        if source is not None:
            stmt = stmt.where(BalanceSnapshotModel.source == source.value)

        stmt = stmt.order_by(BalanceSnapshotModel.captured_at.desc())

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def find_by_account_id_in_range(
        self,
        account_id: UUID,
        start_date: datetime,
        end_date: datetime,
        source: SnapshotSource | None = None,
    ) -> list[BalanceSnapshot]:
        """Find snapshots for an account within date range.

        Results are ordered by captured_at ascending (oldest first) for charting.

        Args:
            account_id: Account's unique identifier.
            start_date: Start of date range (inclusive).
            end_date: End of date range (inclusive).
            source: Optional filter by snapshot source.

        Returns:
            List of snapshots within range (empty if none found).
        """
        stmt = select(BalanceSnapshotModel).where(
            BalanceSnapshotModel.account_id == account_id,
            BalanceSnapshotModel.captured_at >= start_date,
            BalanceSnapshotModel.captured_at <= end_date,
        )

        if source is not None:
            stmt = stmt.where(BalanceSnapshotModel.source == source.value)

        stmt = stmt.order_by(BalanceSnapshotModel.captured_at.asc())

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def find_latest_by_account_id(
        self,
        account_id: UUID,
    ) -> BalanceSnapshot | None:
        """Find most recent snapshot for an account.

        Args:
            account_id: Account's unique identifier.

        Returns:
            Most recent BalanceSnapshot if found, None otherwise.
        """
        stmt = (
            select(BalanceSnapshotModel)
            .where(BalanceSnapshotModel.account_id == account_id)
            .order_by(BalanceSnapshotModel.captured_at.desc())
            .limit(1)
        )

        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def find_by_user_id_in_range(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        source: SnapshotSource | None = None,
    ) -> list[BalanceSnapshot]:
        """Find snapshots across all accounts for a user within date range.

        Aggregates snapshots from all user's accounts.
        Results are ordered by captured_at ascending.

        Args:
            user_id: User's unique identifier.
            start_date: Start of date range (inclusive).
            end_date: End of date range (inclusive).
            source: Optional filter by snapshot source.

        Returns:
            List of snapshots across all accounts (empty if none found).
        """
        stmt = (
            select(BalanceSnapshotModel)
            .join(AccountModel)
            .join(ProviderConnectionModel)
            .where(
                ProviderConnectionModel.user_id == user_id,
                BalanceSnapshotModel.captured_at >= start_date,
                BalanceSnapshotModel.captured_at <= end_date,
            )
        )

        if source is not None:
            stmt = stmt.where(BalanceSnapshotModel.source == source.value)

        stmt = stmt.order_by(BalanceSnapshotModel.captured_at.asc())

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def find_latest_by_user_id(
        self,
        user_id: UUID,
    ) -> list[BalanceSnapshot]:
        """Find most recent snapshot for each of user's accounts.

        Uses a subquery to get the latest captured_at for each account,
        then retrieves those snapshots.

        Args:
            user_id: User's unique identifier.

        Returns:
            List of latest snapshots, one per account.
        """
        # Subquery: get max captured_at for each account owned by user
        subq = (
            select(
                BalanceSnapshotModel.account_id,
                func.max(BalanceSnapshotModel.captured_at).label("max_captured"),
            )
            .join(AccountModel)
            .join(ProviderConnectionModel)
            .where(ProviderConnectionModel.user_id == user_id)
            .group_by(BalanceSnapshotModel.account_id)
            .subquery()
        )

        # Main query: get snapshots matching the max captured_at per account
        stmt = select(BalanceSnapshotModel).join(
            subq,
            (BalanceSnapshotModel.account_id == subq.c.account_id)
            & (BalanceSnapshotModel.captured_at == subq.c.max_captured),
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def save(self, snapshot: BalanceSnapshot) -> None:
        """Create snapshot in database.

        Snapshots are immutable - this only creates, never updates.

        Args:
            snapshot: BalanceSnapshot entity to persist.
        """
        model = self._to_model(snapshot)
        self._session.add(model)
        await self._session.flush()

    async def delete(self, snapshot_id: UUID) -> None:
        """Remove snapshot from database.

        Hard delete - permanently removes the record.

        Args:
            snapshot_id: Snapshot's unique identifier.
        """
        stmt = delete(BalanceSnapshotModel).where(
            BalanceSnapshotModel.id == snapshot_id
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def count_by_account_id(self, account_id: UUID) -> int:
        """Count total snapshots for an account.

        Args:
            account_id: Account's unique identifier.

        Returns:
            Total number of snapshots.
        """
        stmt = (
            select(func.count())
            .select_from(BalanceSnapshotModel)
            .where(BalanceSnapshotModel.account_id == account_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # =========================================================================
    # Entity ↔ Model Mapping (Private Methods)
    # =========================================================================

    def _to_domain(self, model: BalanceSnapshotModel) -> BalanceSnapshot:
        """Convert database model to domain entity.

        Reconstructs Money value objects from separate amount/currency columns.
        Converts source string to SnapshotSource enum.

        Args:
            model: SQLAlchemy BalanceSnapshotModel instance.

        Returns:
            Domain BalanceSnapshot entity.
        """
        # Reconstruct Money for balance
        balance = Money(amount=model.balance_amount, currency=model.currency)

        # Reconstruct Money for optional fields
        available_balance: Money | None = None
        if model.available_balance_amount is not None:
            available_balance = Money(
                amount=model.available_balance_amount,
                currency=model.currency,
            )

        holdings_value: Money | None = None
        if model.holdings_value_amount is not None:
            holdings_value = Money(
                amount=model.holdings_value_amount,
                currency=model.currency,
            )

        cash_value: Money | None = None
        if model.cash_value_amount is not None:
            cash_value = Money(
                amount=model.cash_value_amount,
                currency=model.currency,
            )

        return BalanceSnapshot(
            id=model.id,
            account_id=model.account_id,
            balance=balance,
            currency=model.currency,
            source=SnapshotSource(model.source),
            available_balance=available_balance,
            holdings_value=holdings_value,
            cash_value=cash_value,
            provider_metadata=model.provider_metadata,
            captured_at=model.captured_at,
            created_at=model.created_at,
        )

    def _to_model(self, entity: BalanceSnapshot) -> BalanceSnapshotModel:
        """Convert domain entity to database model.

        Extracts amount from Money value objects.
        Converts SnapshotSource enum to string value.

        Args:
            entity: Domain BalanceSnapshot entity.

        Returns:
            SQLAlchemy BalanceSnapshotModel instance.
        """
        return BalanceSnapshotModel(
            id=entity.id,
            account_id=entity.account_id,
            balance_amount=entity.balance.amount,
            currency=entity.currency,
            source=entity.source.value,
            available_balance_amount=(
                entity.available_balance.amount
                if entity.available_balance is not None
                else None
            ),
            holdings_value_amount=(
                entity.holdings_value.amount
                if entity.holdings_value is not None
                else None
            ),
            cash_value_amount=(
                entity.cash_value.amount if entity.cash_value is not None else None
            ),
            provider_metadata=entity.provider_metadata,
            captured_at=entity.captured_at,
            created_at=entity.created_at,
        )
