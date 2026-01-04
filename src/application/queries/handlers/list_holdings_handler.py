"""ListHoldings query handlers.

Handles requests to list holdings by account or by user.
Returns DTOs with aggregated value information.

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

from src.application.queries.holding_queries import (
    ListHoldingsByAccount,
    ListHoldingsByUser,
)
from src.core.result import Failure, Result, Success
from src.domain.entities.holding import Holding
from src.domain.protocols.account_repository import AccountRepository
from src.domain.protocols.holding_repository import HoldingRepository
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)


@dataclass
class HoldingResult:
    """Single holding DTO for API responses.

    Attributes:
        id: Holding ID.
        account_id: Account ID.
        provider_holding_id: Provider's unique identifier.
        symbol: Security ticker symbol.
        security_name: Full security name.
        asset_type: Asset type (equity, etf, option, etc.).
        quantity: Number of shares/units.
        cost_basis: Total cost paid.
        market_value: Current market value.
        currency: ISO 4217 currency code.
        average_price: Average cost per share.
        current_price: Current market price per share.
        unrealized_gain_loss: Computed gain/loss.
        unrealized_gain_loss_percent: Computed gain/loss percentage.
        is_active: Whether position is active.
        is_profitable: Whether position is profitable.
        last_synced_at: Last sync timestamp.
        created_at: Creation timestamp.
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
    market_value: Decimal
    currency: str
    average_price: Decimal | None
    current_price: Decimal | None
    unrealized_gain_loss: Decimal | None
    unrealized_gain_loss_percent: Decimal | None
    is_active: bool
    is_profitable: bool
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass
class HoldingListResult:
    """List of holdings with aggregated information.

    Attributes:
        holdings: List of holding DTOs.
        total_count: Total number of holdings.
        active_count: Number of active holdings.
        total_market_value_by_currency: Aggregated market values.
        total_cost_basis_by_currency: Aggregated cost basis.
        total_unrealized_gain_loss_by_currency: Aggregated gain/loss.
    """

    holdings: list[HoldingResult]
    total_count: int
    active_count: int
    total_market_value_by_currency: dict[str, str]
    total_cost_basis_by_currency: dict[str, str]
    total_unrealized_gain_loss_by_currency: dict[str, str]


class ListHoldingsByAccountError:
    """ListHoldingsByAccount-specific errors."""

    ACCOUNT_NOT_FOUND = "Account not found"
    CONNECTION_NOT_FOUND = "Provider connection not found"
    NOT_OWNED_BY_USER = "Account not owned by user"


class ListHoldingsByAccountHandler:
    """Handler for ListHoldingsByAccount query.

    Retrieves holdings for a specific account.
    Ownership checked by verifying the account's connection belongs to the user.

    Dependencies (injected via constructor):
        - HoldingRepository: For holding retrieval
        - AccountRepository: For account lookup
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
            account_repo: Account repository.
            connection_repo: Provider connection repository for ownership check.
        """
        self._holding_repo = holding_repo
        self._account_repo = account_repo
        self._connection_repo = connection_repo

    async def handle(
        self, query: ListHoldingsByAccount
    ) -> Result[HoldingListResult, str]:
        """Handle ListHoldingsByAccount query.

        Retrieves holdings for account, verifies ownership, and maps to DTOs.

        Args:
            query: ListHoldingsByAccount query.

        Returns:
            Success(HoldingListResult): Holdings found and owned by user.
            Failure(error): Account not found or not owned by user.
        """
        # Fetch account to get connection_id
        account = await self._account_repo.find_by_id(query.account_id)

        if account is None:
            return Failure(error=ListHoldingsByAccountError.ACCOUNT_NOT_FOUND)

        # Fetch connection to verify ownership
        connection = await self._connection_repo.find_by_id(account.connection_id)

        if connection is None:
            return Failure(error=ListHoldingsByAccountError.CONNECTION_NOT_FOUND)

        # Verify ownership
        if connection.user_id != query.user_id:
            return Failure(error=ListHoldingsByAccountError.NOT_OWNED_BY_USER)

        # Fetch holdings for account
        holdings = await self._holding_repo.list_by_account(
            account_id=query.account_id,
            active_only=query.active_only,
        )

        # Apply client-side filtering if asset_type specified
        if query.asset_type:
            holdings = [h for h in holdings if h.asset_type.value == query.asset_type]

        # Map to DTOs and compute aggregates
        return Success(value=self._build_result(holdings))

    def _build_result(self, holdings: list[Holding]) -> HoldingListResult:
        """Build HoldingListResult from holding entities.

        Args:
            holdings: List of Holding entities.

        Returns:
            HoldingListResult with DTOs and aggregates.
        """
        holding_dtos = []
        market_value_by_currency: dict[str, Decimal] = {}
        cost_basis_by_currency: dict[str, Decimal] = {}
        gain_loss_by_currency: dict[str, Decimal] = {}

        for holding in holdings:
            # Extract Decimal values from Money objects
            cost_basis_amount = holding.cost_basis.amount
            market_value_amount = holding.market_value.amount
            average_price_amount = (
                holding.average_price.amount if holding.average_price else None
            )
            current_price_amount = (
                holding.current_price.amount if holding.current_price else None
            )
            unrealized_gain_loss_amount = holding.unrealized_gain_loss.amount

            # Build DTO
            dto = HoldingResult(
                id=holding.id,
                account_id=holding.account_id,
                provider_holding_id=holding.provider_holding_id,
                symbol=holding.symbol,
                security_name=holding.security_name,
                asset_type=holding.asset_type.value,
                quantity=holding.quantity,
                cost_basis=cost_basis_amount,
                market_value=market_value_amount,
                currency=holding.currency,
                average_price=average_price_amount,
                current_price=current_price_amount,
                unrealized_gain_loss=unrealized_gain_loss_amount,
                unrealized_gain_loss_percent=holding.unrealized_gain_loss_percent,
                is_active=holding.is_active,
                is_profitable=holding.is_profitable(),
                last_synced_at=holding.last_synced_at,
                created_at=holding.created_at,
                updated_at=holding.updated_at,
            )
            holding_dtos.append(dto)

            # Aggregate by currency
            currency = holding.currency
            market_value_by_currency[currency] = (
                market_value_by_currency.get(currency, Decimal("0"))
                + market_value_amount
            )
            cost_basis_by_currency[currency] = (
                cost_basis_by_currency.get(currency, Decimal("0")) + cost_basis_amount
            )
            gain_loss_by_currency[currency] = (
                gain_loss_by_currency.get(currency, Decimal("0"))
                + unrealized_gain_loss_amount
            )

        # Convert Decimals to strings
        total_market_value = {c: str(v) for c, v in market_value_by_currency.items()}
        total_cost_basis = {c: str(v) for c, v in cost_basis_by_currency.items()}
        total_gain_loss = {c: str(v) for c, v in gain_loss_by_currency.items()}

        return HoldingListResult(
            holdings=holding_dtos,
            total_count=len(holdings),
            active_count=sum(1 for h in holdings if h.is_active),
            total_market_value_by_currency=total_market_value,
            total_cost_basis_by_currency=total_cost_basis,
            total_unrealized_gain_loss_by_currency=total_gain_loss,
        )


class ListHoldingsByUserHandler:
    """Handler for ListHoldingsByUser query.

    Retrieves all holdings for a user across all accounts.

    Dependencies (injected via constructor):
        - HoldingRepository: For holding retrieval
    """

    def __init__(
        self,
        holding_repo: HoldingRepository,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            holding_repo: Holding repository.
        """
        self._holding_repo = holding_repo

    async def handle(self, query: ListHoldingsByUser) -> Result[HoldingListResult, str]:
        """Handle ListHoldingsByUser query.

        Retrieves holdings across all user's accounts and maps to DTOs.

        Args:
            query: ListHoldingsByUser query.

        Returns:
            Success(HoldingListResult): All holdings for user.
        """
        # Fetch all holdings for user
        holdings = await self._holding_repo.list_by_user(
            user_id=query.user_id,
            active_only=query.active_only,
        )

        # Apply client-side filtering if asset_type or symbol specified
        if query.asset_type:
            holdings = [h for h in holdings if h.asset_type.value == query.asset_type]
        if query.symbol:
            holdings = [h for h in holdings if h.symbol.upper() == query.symbol.upper()]

        # Use same builder as ListHoldingsByAccountHandler
        return Success(value=self._build_result(holdings))

    def _build_result(self, holdings: list[Holding]) -> HoldingListResult:
        """Build HoldingListResult from holding entities.

        Args:
            holdings: List of Holding entities.

        Returns:
            HoldingListResult with DTOs and aggregates.
        """
        holding_dtos = []
        market_value_by_currency: dict[str, Decimal] = {}
        cost_basis_by_currency: dict[str, Decimal] = {}
        gain_loss_by_currency: dict[str, Decimal] = {}

        for holding in holdings:
            # Extract Decimal values from Money objects
            cost_basis_amount = holding.cost_basis.amount
            market_value_amount = holding.market_value.amount
            average_price_amount = (
                holding.average_price.amount if holding.average_price else None
            )
            current_price_amount = (
                holding.current_price.amount if holding.current_price else None
            )
            unrealized_gain_loss_amount = holding.unrealized_gain_loss.amount

            # Build DTO
            dto = HoldingResult(
                id=holding.id,
                account_id=holding.account_id,
                provider_holding_id=holding.provider_holding_id,
                symbol=holding.symbol,
                security_name=holding.security_name,
                asset_type=holding.asset_type.value,
                quantity=holding.quantity,
                cost_basis=cost_basis_amount,
                market_value=market_value_amount,
                currency=holding.currency,
                average_price=average_price_amount,
                current_price=current_price_amount,
                unrealized_gain_loss=unrealized_gain_loss_amount,
                unrealized_gain_loss_percent=holding.unrealized_gain_loss_percent,
                is_active=holding.is_active,
                is_profitable=holding.is_profitable(),
                last_synced_at=holding.last_synced_at,
                created_at=holding.created_at,
                updated_at=holding.updated_at,
            )
            holding_dtos.append(dto)

            # Aggregate by currency
            currency = holding.currency
            market_value_by_currency[currency] = (
                market_value_by_currency.get(currency, Decimal("0"))
                + market_value_amount
            )
            cost_basis_by_currency[currency] = (
                cost_basis_by_currency.get(currency, Decimal("0")) + cost_basis_amount
            )
            gain_loss_by_currency[currency] = (
                gain_loss_by_currency.get(currency, Decimal("0"))
                + unrealized_gain_loss_amount
            )

        # Convert Decimals to strings
        total_market_value = {c: str(v) for c, v in market_value_by_currency.items()}
        total_cost_basis = {c: str(v) for c, v in cost_basis_by_currency.items()}
        total_gain_loss = {c: str(v) for c, v in gain_loss_by_currency.items()}

        return HoldingListResult(
            holdings=holding_dtos,
            total_count=len(holdings),
            active_count=sum(1 for h in holdings if h.is_active),
            total_market_value_by_currency=total_market_value,
            total_cost_basis_by_currency=total_cost_basis,
            total_unrealized_gain_loss_by_currency=total_gain_loss,
        )
