"""TransactionRepository - SQLAlchemy implementation of TransactionRepository protocol.

Adapter for hexagonal architecture.
Maps between domain Transaction entities and database TransactionModel.

Reference:
    - docs/architecture/repository-pattern.md
    - src/domain/entities/transaction.py
"""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.transaction import Transaction
from src.domain.enums.asset_type import AssetType
from src.domain.enums.transaction_status import TransactionStatus
from src.domain.enums.transaction_subtype import TransactionSubtype
from src.domain.enums.transaction_type import TransactionType
from src.domain.value_objects.money import Money
from src.infrastructure.persistence.models.transaction import (
    Transaction as TransactionModel,
)


class TransactionRepository:
    """SQLAlchemy implementation of TransactionRepository protocol.

    This is an adapter that implements the TransactionRepository port.
    It handles the mapping between domain Transaction entities and
    database TransactionModel.

    This class does NOT inherit from the protocol (Protocol uses structural typing).

    Attributes:
        session: SQLAlchemy async session for database operations.

    Example:
        >>> async with get_session() as session:
        ...     repo = TransactionRepository(session)
        ...     transaction = await repo.find_by_id(transaction_id)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def find_by_id(self, transaction_id: UUID) -> Transaction | None:
        """Find transaction by ID.

        Args:
            transaction_id: Transaction's unique identifier.

        Returns:
            Domain Transaction entity if found, None otherwise.
        """
        stmt = select(TransactionModel).where(TransactionModel.id == transaction_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def find_by_account_id(
        self,
        account_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Transaction]:
        """Find all transactions for an account with pagination.

        Returns transactions ordered by transaction_date DESC (most recent first).

        Args:
            account_id: Account identifier to query.
            limit: Maximum number of transactions to return.
            offset: Number of transactions to skip.

        Returns:
            List of transactions (empty if none found).
        """
        stmt = (
            select(TransactionModel)
            .where(TransactionModel.account_id == account_id)
            .order_by(TransactionModel.transaction_date.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def find_by_account_and_type(
        self,
        account_id: UUID,
        transaction_type: TransactionType,
        limit: int = 50,
    ) -> list[Transaction]:
        """Find transactions by account and type.

        Args:
            account_id: Account identifier to query.
            transaction_type: Type of transactions to retrieve.
            limit: Maximum number of transactions to return.

        Returns:
            List of transactions matching the type (empty if none found).
            Ordered by transaction_date DESC.
        """
        stmt = (
            select(TransactionModel)
            .where(
                TransactionModel.account_id == account_id,
                TransactionModel.transaction_type == transaction_type.value,
            )
            .order_by(TransactionModel.transaction_date.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def find_by_date_range(
        self,
        account_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[Transaction]:
        """Find transactions within a date range.

        Queries by transaction_date (not created_at).

        Args:
            account_id: Account identifier to query.
            start_date: Start of date range (inclusive).
            end_date: End of date range (inclusive).

        Returns:
            List of transactions within date range (empty if none found).
            Ordered by transaction_date ASC (chronological).
        """
        stmt = (
            select(TransactionModel)
            .where(
                TransactionModel.account_id == account_id,
                TransactionModel.transaction_date >= start_date,
                TransactionModel.transaction_date <= end_date,
            )
            .order_by(TransactionModel.transaction_date.asc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def find_by_provider_transaction_id(
        self,
        account_id: UUID,
        provider_transaction_id: str,
    ) -> Transaction | None:
        """Find transaction by provider's unique ID.

        Used for deduplication during sync operations.

        Args:
            account_id: Account identifier (scope to account).
            provider_transaction_id: Provider's unique transaction identifier.

        Returns:
            Transaction entity if found, None otherwise.
        """
        stmt = select(TransactionModel).where(
            TransactionModel.account_id == account_id,
            TransactionModel.provider_transaction_id == provider_transaction_id,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def find_security_transactions(
        self,
        account_id: UUID,
        symbol: str,
        limit: int = 50,
    ) -> list[Transaction]:
        """Find all transactions for a specific security.

        Queries TRADE transactions only (filters by symbol field).

        Args:
            account_id: Account identifier to query.
            symbol: Security ticker symbol.
            limit: Maximum number of transactions to return.

        Returns:
            List of trade transactions for the symbol (empty if none found).
            Ordered by transaction_date DESC.
        """
        stmt = (
            select(TransactionModel)
            .where(
                TransactionModel.account_id == account_id,
                TransactionModel.symbol == symbol,
            )
            .order_by(TransactionModel.transaction_date.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def save(self, transaction: Transaction) -> None:
        """Save a single transaction.

        Creates new transaction or updates existing (based on provider_transaction_id).

        Args:
            transaction: Transaction entity to save.
        """
        # Check if exists
        stmt = select(TransactionModel).where(TransactionModel.id == transaction.id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            # Create new
            model = self._to_model(transaction)
            self.session.add(model)
        else:
            # Update existing
            self._update_model(existing, transaction)

        await self.session.commit()

    async def save_many(self, transactions: list[Transaction]) -> None:
        """Save multiple transactions in bulk.

        Efficient for provider sync operations that fetch many transactions at once.
        Uses bulk insert/upsert to minimize database round-trips.

        Args:
            transactions: List of transaction entities to save.
        """
        if not transactions:
            return

        # Get all existing transaction IDs
        transaction_ids = [t.id for t in transactions]
        stmt = select(TransactionModel).where(TransactionModel.id.in_(transaction_ids))
        result = await self.session.execute(stmt)
        existing_models = {model.id: model for model in result.scalars().all()}

        # Separate into new and updates
        for transaction in transactions:
            if transaction.id in existing_models:
                # Update existing
                self._update_model(existing_models[transaction.id], transaction)
            else:
                # Create new
                model = self._to_model(transaction)
                self.session.add(model)

        await self.session.commit()

    async def delete(self, transaction_id: UUID) -> None:
        """Delete a transaction.

        Hard delete - permanently removes the record.

        Args:
            transaction_id: Transaction's unique identifier.

        Raises:
            NoResultFound: If transaction doesn't exist.
        """
        stmt = select(TransactionModel).where(TransactionModel.id == transaction_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one()  # Raises NoResultFound if not found

        await self.session.delete(model)
        await self.session.commit()

    # =========================================================================
    # Entity ↔ Model Mapping (Private Methods)
    # =========================================================================

    def _to_domain(self, model: TransactionModel) -> Transaction:
        """Convert database model to domain entity.

        Reconstructs Money value objects from separate amount/currency columns.
        Converts enum strings back to domain enums.

        Args:
            model: SQLAlchemy TransactionModel instance.

        Returns:
            Domain Transaction entity.
        """
        # Reconstruct Money for amount (required)
        amount = Money(amount=model.amount, currency=model.currency)

        # Reconstruct Money for unit_price if present
        unit_price: Money | None = None
        if model.unit_price_amount is not None:
            unit_price = Money(
                amount=model.unit_price_amount,
                currency=model.currency,
            )

        # Reconstruct Money for commission if present
        commission: Money | None = None
        if model.commission_amount is not None:
            commission = Money(
                amount=model.commission_amount,
                currency=model.currency,
            )

        # Convert asset_type string to enum if present
        asset_type: AssetType | None = None
        if model.asset_type is not None:
            asset_type = AssetType(model.asset_type)

        return Transaction(
            id=model.id,
            account_id=model.account_id,
            provider_transaction_id=model.provider_transaction_id,
            transaction_type=TransactionType(model.transaction_type),
            subtype=TransactionSubtype(model.subtype),
            status=TransactionStatus(model.status),
            amount=amount,
            description=model.description,
            asset_type=asset_type,
            symbol=model.symbol,
            security_name=model.security_name,
            quantity=model.quantity,
            unit_price=unit_price,
            commission=commission,
            transaction_date=model.transaction_date,
            settlement_date=model.settlement_date,
            provider_metadata=model.provider_metadata,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Transaction) -> TransactionModel:
        """Convert domain entity to database model.

        Extracts amounts from Money value objects.
        Converts enums to lowercase string values.

        Args:
            entity: Domain Transaction entity.

        Returns:
            SQLAlchemy TransactionModel instance.
        """
        return TransactionModel(
            id=entity.id,
            account_id=entity.account_id,
            provider_transaction_id=entity.provider_transaction_id,
            transaction_type=entity.transaction_type.value,
            subtype=entity.subtype.value,
            status=entity.status.value,
            amount=entity.amount.amount,
            currency=entity.amount.currency,
            description=entity.description,
            asset_type=entity.asset_type.value if entity.asset_type else None,
            symbol=entity.symbol,
            security_name=entity.security_name,
            quantity=entity.quantity,
            unit_price_amount=(
                entity.unit_price.amount if entity.unit_price is not None else None
            ),
            commission_amount=(
                entity.commission.amount if entity.commission is not None else None
            ),
            transaction_date=entity.transaction_date,
            settlement_date=entity.settlement_date,
            provider_metadata=entity.provider_metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def _update_model(self, model: TransactionModel, entity: Transaction) -> None:
        """Update existing model with entity data.

        Used for upsert operations (update existing records).

        Args:
            model: Existing SQLAlchemy TransactionModel instance.
            entity: Domain Transaction entity with new data.
        """
        model.account_id = entity.account_id
        model.provider_transaction_id = entity.provider_transaction_id
        model.transaction_type = entity.transaction_type.value
        model.subtype = entity.subtype.value
        model.status = entity.status.value
        model.amount = entity.amount.amount
        model.currency = entity.amount.currency
        model.description = entity.description
        model.asset_type = entity.asset_type.value if entity.asset_type else None
        model.symbol = entity.symbol
        model.security_name = entity.security_name
        model.quantity = entity.quantity
        model.unit_price_amount = (
            entity.unit_price.amount if entity.unit_price is not None else None
        )
        model.commission_amount = (
            entity.commission.amount if entity.commission is not None else None
        )
        model.transaction_date = entity.transaction_date
        model.settlement_date = entity.settlement_date
        model.provider_metadata = entity.provider_metadata
        model.updated_at = entity.updated_at
