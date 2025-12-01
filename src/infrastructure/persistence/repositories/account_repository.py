"""AccountRepository - SQLAlchemy implementation of AccountRepository protocol.

Adapter for hexagonal architecture.
Maps between domain Account entities and database AccountModel.

Reference:
    - docs/architecture/repository-pattern.md
    - docs/architecture/account-domain-model.md
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.account import Account
from src.domain.enums.account_type import AccountType
from src.domain.value_objects.money import Money
from src.infrastructure.persistence.models.account import Account as AccountModel
from src.infrastructure.persistence.models.provider_connection import (
    ProviderConnection as ProviderConnectionModel,
)


class AccountRepository:
    """SQLAlchemy implementation of AccountRepository protocol.

    This is an adapter that implements the AccountRepository port.
    It handles the mapping between domain Account entities and
    database AccountModel.

    This class does NOT inherit from the protocol (Protocol uses structural typing).

    Attributes:
        session: SQLAlchemy async session for database operations.

    Example:
        >>> async with get_session() as session:
        ...     repo = AccountRepository(session)
        ...     account = await repo.find_by_id(account_id)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def find_by_id(self, account_id: UUID) -> Account | None:
        """Find account by ID.

        Args:
            account_id: Account's unique identifier.

        Returns:
            Domain Account entity if found, None otherwise.
        """
        stmt = select(AccountModel).where(AccountModel.id == account_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def find_by_connection_id(
        self, connection_id: UUID, active_only: bool = False
    ) -> list[Account]:
        """Find all accounts for a provider connection.

        A connection can have multiple accounts (e.g., IRA and brokerage
        at same provider).

        Args:
            connection_id: ProviderConnection's unique identifier.
            active_only: If True, return only active accounts. Default False.

        Returns:
            List of accounts (empty if none found).
        """
        stmt = select(AccountModel).where(AccountModel.connection_id == connection_id)
        if active_only:
            stmt = stmt.where(AccountModel.is_active == True)  # noqa: E712
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def find_by_user_id(
        self,
        user_id: UUID,
        active_only: bool = False,
        account_type: AccountType | None = None,
    ) -> list[Account]:
        """Find all accounts across all connections for a user.

        Aggregates accounts from all provider connections by joining
        through the provider_connections table.

        Args:
            user_id: User's unique identifier.
            active_only: If True, return only active accounts. Default False.
            account_type: Optional filter by account type.

        Returns:
            List of accounts (empty if none found).
        """
        stmt = (
            select(AccountModel)
            .join(ProviderConnectionModel)
            .where(ProviderConnectionModel.user_id == user_id)
        )
        if active_only:
            stmt = stmt.where(AccountModel.is_active == True)  # noqa: E712
        if account_type is not None:
            stmt = stmt.where(AccountModel.account_type == account_type)
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def find_by_provider_account_id(
        self,
        connection_id: UUID,
        provider_account_id: str,
    ) -> Account | None:
        """Find account by provider's identifier.

        Used during sync to match provider data with existing accounts.
        Provider account ID is unique within a connection.

        Args:
            connection_id: ProviderConnection's unique identifier.
            provider_account_id: Provider's unique account identifier.

        Returns:
            Account if found, None otherwise.
        """
        stmt = select(AccountModel).where(
            AccountModel.connection_id == connection_id,
            AccountModel.provider_account_id == provider_account_id,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def find_active_by_user(self, user_id: UUID) -> list[Account]:
        """Find all active accounts for a user.

        Only returns accounts with is_active=True by joining
        through the provider_connections table.

        Args:
            user_id: User's unique identifier.

        Returns:
            List of active accounts (empty if none found).
        """
        stmt = (
            select(AccountModel)
            .join(ProviderConnectionModel)
            .where(
                ProviderConnectionModel.user_id == user_id,
                AccountModel.is_active == True,  # noqa: E712
            )
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def find_needing_sync(self, threshold: timedelta) -> list[Account]:
        """Find accounts not synced within threshold.

        Used by background job to identify stale accounts.
        Returns accounts where last_synced_at is NULL or older than threshold.

        Args:
            threshold: Maximum time since last sync.

        Returns:
            List of accounts needing sync (empty if none found).
        """
        cutoff = datetime.now(UTC) - threshold
        stmt = select(AccountModel).where(
            (AccountModel.last_synced_at == None)  # noqa: E711
            | (AccountModel.last_synced_at < cutoff)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def save(self, account: Account) -> None:
        """Create or update account in database.

        Uses merge semantics - creates if not exists, updates if exists.

        Args:
            account: Account entity to persist.
        """
        # Check if exists
        stmt = select(AccountModel).where(AccountModel.id == account.id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            # Create new
            model = self._to_model(account)
            self.session.add(model)
        else:
            # Update existing
            self._update_model(existing, account)

        await self.session.commit()

    async def delete(self, account_id: UUID) -> None:
        """Remove account from database.

        Hard delete - permanently removes the record.

        Args:
            account_id: Account's unique identifier.

        Raises:
            NoResultFound: If account doesn't exist.
        """
        stmt = select(AccountModel).where(AccountModel.id == account_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one()  # Raises NoResultFound if not found

        await self.session.delete(model)
        await self.session.commit()

    # =========================================================================
    # Entity ↔ Model Mapping (Private Methods)
    # =========================================================================

    def _to_domain(self, model: AccountModel) -> Account:
        """Convert database model to domain entity.

        Reconstructs Money value objects from separate balance/currency columns.
        Converts account_type string to AccountType enum.

        Args:
            model: SQLAlchemy AccountModel instance.

        Returns:
            Domain Account entity.
        """
        # Reconstruct Money for balance
        balance = Money(amount=model.balance, currency=model.currency)

        # Reconstruct Money for available_balance if present
        available_balance: Money | None = None
        if model.available_balance is not None:
            available_balance = Money(
                amount=model.available_balance,
                currency=model.currency,
            )

        return Account(
            id=model.id,
            connection_id=model.connection_id,
            provider_account_id=model.provider_account_id,
            account_number_masked=model.account_number_masked,
            name=model.name,
            account_type=AccountType(model.account_type),
            balance=balance,
            currency=model.currency,
            available_balance=available_balance,
            is_active=model.is_active,
            last_synced_at=model.last_synced_at,
            provider_metadata=model.provider_metadata,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Account) -> AccountModel:
        """Convert domain entity to database model.

        Extracts amount from Money value objects.
        Converts AccountType enum to string value.

        Args:
            entity: Domain Account entity.

        Returns:
            SQLAlchemy AccountModel instance.
        """
        return AccountModel(
            id=entity.id,
            connection_id=entity.connection_id,
            provider_account_id=entity.provider_account_id,
            account_number_masked=entity.account_number_masked,
            name=entity.name,
            account_type=entity.account_type.value,
            balance=entity.balance.amount,
            currency=entity.currency,
            available_balance=(
                entity.available_balance.amount
                if entity.available_balance is not None
                else None
            ),
            is_active=entity.is_active,
            last_synced_at=entity.last_synced_at,
            provider_metadata=entity.provider_metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def _update_model(self, model: AccountModel, entity: Account) -> None:
        """Update existing model from entity (for upsert).

        Only updates mutable fields. Does not update:
        - id (immutable)
        - connection_id (immutable - account belongs to one connection)
        - provider_account_id (immutable - provider's identifier)
        - created_at (immutable)

        Args:
            model: Existing SQLAlchemy model to update.
            entity: Domain entity with new values.
        """
        model.account_number_masked = entity.account_number_masked
        model.name = entity.name
        model.account_type = entity.account_type.value
        model.balance = entity.balance.amount
        model.currency = entity.currency
        model.available_balance = (
            entity.available_balance.amount
            if entity.available_balance is not None
            else None
        )
        model.is_active = entity.is_active
        model.last_synced_at = entity.last_synced_at
        model.provider_metadata = entity.provider_metadata
        model.updated_at = datetime.now(UTC)
