"""HoldingRepository - SQLAlchemy implementation of HoldingRepository protocol.

Adapter for hexagonal architecture.
Maps between domain Holding entities and database HoldingModel.

Reference:
    - docs/architecture/repository-pattern.md
    - src/domain/entities/holding.py
"""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.holding import Holding
from src.domain.enums.asset_type import AssetType
from src.domain.value_objects.money import Money
from src.infrastructure.persistence.models.account import Account as AccountModel
from src.infrastructure.persistence.models.holding import Holding as HoldingModel
from src.infrastructure.persistence.models.provider_connection import (
    ProviderConnection as ProviderConnectionModel,
)


class HoldingRepository:
    """SQLAlchemy implementation of HoldingRepository protocol.

    This is an adapter that implements the HoldingRepository port.
    It handles the mapping between domain Holding entities and
    database HoldingModel.

    This class does NOT inherit from the protocol (Protocol uses structural typing).

    Attributes:
        session: SQLAlchemy async session for database operations.

    Example:
        >>> async with get_session() as session:
        ...     repo = HoldingRepository(session)
        ...     holdings = await repo.list_by_account(account_id)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def find_by_id(self, holding_id: UUID) -> Holding | None:
        """Find holding by ID.

        Args:
            holding_id: Unique holding identifier.

        Returns:
            Holding entity if found, None otherwise.
        """
        stmt = select(HoldingModel).where(HoldingModel.id == holding_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def find_by_account_and_symbol(
        self, account_id: UUID, symbol: str
    ) -> Holding | None:
        """Find holding by account and symbol.

        Args:
            account_id: Account identifier.
            symbol: Security symbol (e.g., "AAPL").

        Returns:
            Holding entity if found, None otherwise.
        """
        stmt = select(HoldingModel).where(
            HoldingModel.account_id == account_id,
            HoldingModel.symbol == symbol,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def find_by_provider_holding_id(
        self, account_id: UUID, provider_holding_id: str
    ) -> Holding | None:
        """Find holding by provider's unique identifier.

        Used for deduplication during sync operations.

        Args:
            account_id: Account identifier.
            provider_holding_id: Provider's unique holding identifier.

        Returns:
            Holding entity if found, None otherwise.
        """
        stmt = select(HoldingModel).where(
            HoldingModel.account_id == account_id,
            HoldingModel.provider_holding_id == provider_holding_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def list_by_account(
        self, account_id: UUID, *, active_only: bool = True
    ) -> list[Holding]:
        """List holdings for an account.

        Args:
            account_id: Account identifier.
            active_only: If True, only return active holdings (quantity > 0).

        Returns:
            List of holdings for the account.
        """
        stmt = select(HoldingModel).where(HoldingModel.account_id == account_id)

        if active_only:
            stmt = stmt.where(HoldingModel.is_active == True)  # noqa: E712

        stmt = stmt.order_by(HoldingModel.symbol)
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def list_by_user(
        self, user_id: UUID, *, active_only: bool = True
    ) -> list[Holding]:
        """List all holdings across all accounts for a user.

        Requires joining through account -> connection -> user.

        Args:
            user_id: User identifier.
            active_only: If True, only return active holdings.

        Returns:
            List of all holdings for the user.
        """
        stmt = (
            select(HoldingModel)
            .join(AccountModel)
            .join(ProviderConnectionModel)
            .where(ProviderConnectionModel.user_id == user_id)
        )

        if active_only:
            stmt = stmt.where(HoldingModel.is_active == True)  # noqa: E712

        stmt = stmt.order_by(HoldingModel.symbol)
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def save(self, holding: Holding) -> None:
        """Save a holding (create or update).

        Creates new holding if ID doesn't exist, updates if it does.

        Args:
            holding: Holding entity to save.
        """
        # Check if exists
        stmt = select(HoldingModel).where(HoldingModel.id == holding.id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            # Create new
            model = self._to_model(holding)
            self._session.add(model)
        else:
            # Update existing
            self._update_model(existing, holding)

        await self._session.flush()

    async def save_many(self, holdings: list[Holding]) -> None:
        """Save multiple holdings in batch.

        Optimized for sync operations. Uses upsert logic:
        - Creates new holdings if they don't exist
        - Updates existing holdings if they do

        Args:
            holdings: List of holdings to save.
        """
        for holding in holdings:
            await self.save(holding)

        await self._session.flush()

    async def delete(self, holding_id: UUID) -> None:
        """Delete a holding.

        Args:
            holding_id: Holding ID to delete.
        """
        stmt = delete(HoldingModel).where(HoldingModel.id == holding_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def delete_by_account(self, account_id: UUID) -> int:
        """Delete all holdings for an account.

        Used when account is disconnected or for cleanup.

        Args:
            account_id: Account identifier.

        Returns:
            Number of holdings deleted.
        """
        stmt = delete(HoldingModel).where(HoldingModel.account_id == account_id)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return cast(Any, result).rowcount or 0

    # =========================================================================
    # Entity ↔ Model Mapping (Private Methods)
    # =========================================================================

    def _to_domain(self, model: HoldingModel) -> Holding:
        """Convert database model to domain entity.

        Reconstructs Money value objects from separate amount/currency columns.
        Converts asset_type string to AssetType enum.

        Args:
            model: SQLAlchemy HoldingModel instance.

        Returns:
            Domain Holding entity.
        """
        # Reconstruct Money for cost_basis
        cost_basis = Money(amount=model.cost_basis_amount, currency=model.currency)

        # Reconstruct Money for market_value
        market_value = Money(amount=model.market_value_amount, currency=model.currency)

        # Reconstruct Money for average_price if present
        average_price: Money | None = None
        if model.average_price_amount is not None:
            average_price = Money(
                amount=model.average_price_amount,
                currency=model.currency,
            )

        # Reconstruct Money for current_price if present
        current_price: Money | None = None
        if model.current_price_amount is not None:
            current_price = Money(
                amount=model.current_price_amount,
                currency=model.currency,
            )

        return Holding(
            id=model.id,
            account_id=model.account_id,
            provider_holding_id=model.provider_holding_id,
            symbol=model.symbol,
            security_name=model.security_name,
            asset_type=AssetType(model.asset_type),
            quantity=model.quantity,
            cost_basis=cost_basis,
            market_value=market_value,
            currency=model.currency,
            average_price=average_price,
            current_price=current_price,
            is_active=model.is_active,
            last_synced_at=model.last_synced_at,
            provider_metadata=model.provider_metadata,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Holding) -> HoldingModel:
        """Convert domain entity to database model.

        Extracts amount from Money value objects.
        Converts AssetType enum to string value.

        Args:
            entity: Domain Holding entity.

        Returns:
            SQLAlchemy HoldingModel instance.
        """
        return HoldingModel(
            id=entity.id,
            account_id=entity.account_id,
            provider_holding_id=entity.provider_holding_id,
            symbol=entity.symbol,
            security_name=entity.security_name,
            asset_type=entity.asset_type.value,
            quantity=entity.quantity,
            cost_basis_amount=entity.cost_basis.amount,
            market_value_amount=entity.market_value.amount,
            currency=entity.currency,
            average_price_amount=(
                entity.average_price.amount
                if entity.average_price is not None
                else None
            ),
            current_price_amount=(
                entity.current_price.amount
                if entity.current_price is not None
                else None
            ),
            is_active=entity.is_active,
            last_synced_at=entity.last_synced_at,
            provider_metadata=entity.provider_metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def _update_model(self, model: HoldingModel, entity: Holding) -> None:
        """Update existing model from entity (for upsert).

        Only updates mutable fields. Does not update:
        - id (immutable)
        - account_id (immutable - holding belongs to one account)
        - provider_holding_id (immutable - provider's identifier)
        - created_at (immutable)

        Args:
            model: Existing SQLAlchemy model to update.
            entity: Domain entity with new values.
        """
        model.symbol = entity.symbol
        model.security_name = entity.security_name
        model.asset_type = entity.asset_type.value
        model.quantity = entity.quantity
        model.cost_basis_amount = entity.cost_basis.amount
        model.market_value_amount = entity.market_value.amount
        model.currency = entity.currency
        model.average_price_amount = (
            entity.average_price.amount if entity.average_price is not None else None
        )
        model.current_price_amount = (
            entity.current_price.amount if entity.current_price is not None else None
        )
        model.is_active = entity.is_active
        model.last_synced_at = entity.last_synced_at
        model.provider_metadata = entity.provider_metadata
        model.updated_at = datetime.now(UTC)
