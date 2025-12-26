"""Holding request and response schemas.

Pydantic schemas for holding API endpoints. Includes:
- Request schemas (client → API)
- Response schemas (API → client)
- DTO-to-schema conversion methods

Reference:
    - docs/architecture/api-design-patterns.md
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from src.application.queries.handlers.list_holdings_handler import (
    HoldingListResult,
    HoldingResult,
)
from src.schemas.common_schemas import SyncResponse


# =============================================================================
# Response Schemas
# =============================================================================


class HoldingResponse(BaseModel):
    """Single holding response.

    Attributes:
        id: Holding unique identifier.
        account_id: Account FK.
        provider_holding_id: Provider's unique ID for position.
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

    id: UUID = Field(..., description="Holding unique identifier")
    account_id: UUID = Field(..., description="Account FK")
    provider_holding_id: str = Field(
        ..., description="Provider's unique ID for position"
    )
    symbol: str = Field(..., description="Security ticker symbol", examples=["AAPL"])
    security_name: str = Field(
        ..., description="Full security name", examples=["Apple Inc."]
    )
    asset_type: str = Field(
        ...,
        description="Asset type",
        examples=["equity", "etf", "option", "mutual_fund"],
    )
    quantity: Decimal = Field(..., description="Number of shares/units")
    cost_basis: Decimal = Field(..., description="Total cost paid")
    market_value: Decimal = Field(..., description="Current market value")
    currency: str = Field(..., description="ISO 4217 currency code", examples=["USD"])
    average_price: Decimal | None = Field(None, description="Average cost per share")
    current_price: Decimal | None = Field(
        None, description="Current market price per share"
    )
    unrealized_gain_loss: Decimal | None = Field(
        None, description="Computed unrealized gain/loss"
    )
    unrealized_gain_loss_percent: Decimal | None = Field(
        None, description="Computed gain/loss percentage"
    )
    is_active: bool = Field(..., description="Whether position is active")
    is_profitable: bool = Field(..., description="Whether position is profitable")
    last_synced_at: datetime | None = Field(None, description="Last sync timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    @classmethod
    def from_dto(cls, dto: HoldingResult) -> "HoldingResponse":
        """Convert application DTO to response schema.

        Args:
            dto: HoldingResult from handler.

        Returns:
            HoldingResponse for API response.
        """
        return cls(
            id=dto.id,
            account_id=dto.account_id,
            provider_holding_id=dto.provider_holding_id,
            symbol=dto.symbol,
            security_name=dto.security_name,
            asset_type=dto.asset_type,
            quantity=dto.quantity,
            cost_basis=dto.cost_basis,
            market_value=dto.market_value,
            currency=dto.currency,
            average_price=dto.average_price,
            current_price=dto.current_price,
            unrealized_gain_loss=dto.unrealized_gain_loss,
            unrealized_gain_loss_percent=dto.unrealized_gain_loss_percent,
            is_active=dto.is_active,
            is_profitable=dto.is_profitable,
            last_synced_at=dto.last_synced_at,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class HoldingListResponse(BaseModel):
    """Holding list response with aggregates.

    Attributes:
        holdings: List of holdings.
        total_count: Total number of holdings.
        active_count: Number of active holdings.
        total_market_value_by_currency: Aggregated market values.
        total_cost_basis_by_currency: Aggregated cost basis.
        total_unrealized_gain_loss_by_currency: Aggregated gain/loss.
    """

    holdings: list[HoldingResponse] = Field(..., description="List of holdings")
    total_count: int = Field(..., description="Total holding count")
    active_count: int = Field(..., description="Active holding count")
    total_market_value_by_currency: dict[str, str] = Field(
        ..., description="Aggregated market values by currency"
    )
    total_cost_basis_by_currency: dict[str, str] = Field(
        ..., description="Aggregated cost basis by currency"
    )
    total_unrealized_gain_loss_by_currency: dict[str, str] = Field(
        ..., description="Aggregated unrealized gain/loss by currency"
    )

    @classmethod
    def from_dto(cls, dto: HoldingListResult) -> "HoldingListResponse":
        """Convert application DTO to response schema.

        Args:
            dto: HoldingListResult from handler.

        Returns:
            HoldingListResponse for API response.
        """
        return cls(
            holdings=[HoldingResponse.from_dto(h) for h in dto.holdings],
            total_count=dto.total_count,
            active_count=dto.active_count,
            total_market_value_by_currency=dto.total_market_value_by_currency,
            total_cost_basis_by_currency=dto.total_cost_basis_by_currency,
            total_unrealized_gain_loss_by_currency=dto.total_unrealized_gain_loss_by_currency,
        )


class SyncHoldingsResponse(SyncResponse):
    """Response for holdings sync operation.

    Extends SyncResponse with holdings-specific fields.

    Attributes:
        holdings_created: Number of new holdings created.
        holdings_updated: Number of existing holdings updated.
        holdings_deactivated: Number of holdings deactivated.
    """

    holdings_created: int = Field(0, description="New holdings created")
    holdings_updated: int = Field(0, description="Existing holdings updated")
    holdings_deactivated: int = Field(0, description="Holdings deactivated (sold)")


# =============================================================================
# Request Schemas
# =============================================================================


class SyncHoldingsRequest(BaseModel):
    """Request to sync holdings from provider.

    Attributes:
        force: Force sync even if recently synced.
    """

    force: bool = Field(False, description="Force sync even if recently synced")
