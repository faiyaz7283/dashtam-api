"""GetHolding query handler.

Handles requests to retrieve a single holding.
Returns DTO (not domain entity) to prevent leaking domain to presentation.

Architecture:
- Application layer handler (orchestrates data retrieval)
- Returns Result[DTO, str] (explicit error handling)
- NO domain events (queries are side-effect free)
- Ownership verification: Holding->Account->ProviderConnection->User

Reference:
    - docs/architecture/cqrs.md
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from src.application.queries.holding_queries import GetHolding
from src.core.result import Failure, Result, Success
from src.domain.protocols.account_repository import AccountRepository
from src.domain.protocols.holding_repository import HoldingRepository
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)


@dataclass
class HoldingDetailResult:
    """Single holding result DTO.

    Represents a holding for API response. Money value objects converted
    to separate amount+currency fields for serialization.

    Attributes:
        id: Holding unique identifier.
        account_id: Account FK.
        provider_holding_id: Provider's unique ID.
        symbol: Security ticker symbol.
        security_name: Full security name.
        asset_type: Asset type as string (e.g., "equity", "option").
        quantity: Number of shares/units.
        cost_basis: Total cost basis amount.
        cost_basis_currency: Cost basis currency code.
        market_value: Current market value amount.
        market_value_currency: Market value currency code.
        average_price: Average cost per share or None.
        average_price_currency: Average price currency or None.
        current_price: Current market price per share or None.
        current_price_currency: Current price currency or None.
        unrealized_gain_loss: Unrealized gain/loss amount.
        unrealized_gain_loss_currency: Unrealized gain/loss currency.
        unrealized_gain_loss_percent: Gain/loss percentage or None.
        is_active: Whether position is active.
        is_profitable: Whether position is profitable.
        last_synced_at: Last provider sync timestamp or None.
        created_at: First sync timestamp.
        updated_at: Last update timestamp.
    """

    id: UUID
    account_id: UUID
    provider_holding_id: str
    symbol: str
    security_name: str
    asset_type: str
    quantity: Decimal
    cost_basis: Decimal
    cost_basis_currency: str
    market_value: Decimal
    market_value_currency: str
    average_price: Decimal | None
    average_price_currency: str | None
    current_price: Decimal | None
    current_price_currency: str | None
    unrealized_gain_loss: Decimal
    unrealized_gain_loss_currency: str
    unrealized_gain_loss_percent: Decimal | None
    is_active: bool
    is_profitable: bool
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GetHoldingError:
    """GetHolding-specific errors."""

    HOLDING_NOT_FOUND = "Holding not found"
    ACCOUNT_NOT_FOUND = "Account not found"
    CONNECTION_NOT_FOUND = "Provider connection not found"
    NOT_OWNED_BY_USER = "Holding not owned by user"


class GetHoldingHandler:
    """Handler for GetHolding query.

    Retrieves a single holding by ID with ownership verification.
    Ownership checked by verifying: Holding->Account->ProviderConnection->User

    Dependencies (injected via constructor):
        - HoldingRepository: For holding retrieval
        - AccountRepository: For account lookup (ownership chain)
        - ProviderConnectionRepository: For ownership verification
    """

    def __init__(
        self,
        holding_repo: HoldingRepository,
        account_repo: AccountRepository,
        connection_repo: ProviderConnectionRepository,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            holding_repo: Holding repository.
            account_repo: Account repository for ownership chain.
            connection_repo: Provider connection repository for ownership check.
        """
        self._holding_repo = holding_repo
        self._account_repo = account_repo
        self._connection_repo = connection_repo

    async def handle(self, query: GetHolding) -> Result[HoldingDetailResult, str]:
        """Handle GetHolding query.

        Retrieves holding, verifies ownership via Account->Connection chain,
        and maps to DTO.

        Args:
            query: GetHolding query with holding and user IDs.

        Returns:
            Success(HoldingDetailResult): Holding found and owned by user.
            Failure(error): Holding not found or not owned by user.
        """
        # Fetch holding
        holding = await self._holding_repo.find_by_id(query.holding_id)

        # Verify exists
        if holding is None:
            return Failure(error=GetHoldingError.HOLDING_NOT_FOUND)

        # Fetch account to get connection_id
        account = await self._account_repo.find_by_id(holding.account_id)

        if account is None:
            return Failure(error=GetHoldingError.ACCOUNT_NOT_FOUND)

        # Fetch connection to verify ownership
        connection = await self._connection_repo.find_by_id(account.connection_id)

        if connection is None:
            return Failure(error=GetHoldingError.CONNECTION_NOT_FOUND)

        # Verify ownership (connection belongs to user)
        if connection.user_id != query.user_id:
            return Failure(error=GetHoldingError.NOT_OWNED_BY_USER)

        # Map to DTO (Money -> amount+currency)
        dto = HoldingDetailResult(
            id=holding.id,
            account_id=holding.account_id,
            provider_holding_id=holding.provider_holding_id,
            symbol=holding.symbol,
            security_name=holding.security_name,
            asset_type=holding.asset_type.value,
            quantity=holding.quantity,
            cost_basis=holding.cost_basis.amount,
            cost_basis_currency=holding.cost_basis.currency,
            market_value=holding.market_value.amount,
            market_value_currency=holding.market_value.currency,
            average_price=(
                holding.average_price.amount if holding.average_price else None
            ),
            average_price_currency=(
                holding.average_price.currency if holding.average_price else None
            ),
            current_price=(
                holding.current_price.amount if holding.current_price else None
            ),
            current_price_currency=(
                holding.current_price.currency if holding.current_price else None
            ),
            unrealized_gain_loss=holding.unrealized_gain_loss.amount,
            unrealized_gain_loss_currency=holding.unrealized_gain_loss.currency,
            unrealized_gain_loss_percent=holding.unrealized_gain_loss_percent,
            is_active=holding.is_active,
            is_profitable=holding.is_profitable(),
            last_synced_at=holding.last_synced_at,
            created_at=holding.created_at,
            updated_at=holding.updated_at,
        )

        return Success(value=dto)
