"""Balance snapshot request and response schemas.

Pydantic schemas for balance snapshot API endpoints. Includes:
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

from src.application.queries.handlers.balance_snapshot_handlers import (
    BalanceHistoryResult,
    BalanceSnapshotResult,
    LatestSnapshotsResult,
)


# =============================================================================
# Response Schemas
# =============================================================================


class BalanceSnapshotResponse(BaseModel):
    """Single balance snapshot response.

    Attributes:
        id: Snapshot unique identifier.
        account_id: Account FK.
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

    id: UUID = Field(..., description="Snapshot unique identifier")
    account_id: UUID = Field(..., description="Account FK")
    balance: Decimal = Field(..., description="Total account balance")
    available_balance: Decimal | None = Field(
        None, description="Available balance (may differ from total)"
    )
    holdings_value: Decimal | None = Field(
        None, description="Total market value of holdings"
    )
    cash_value: Decimal | None = Field(None, description="Cash/money market balance")
    currency: str = Field(..., description="ISO 4217 currency code", examples=["USD"])
    source: str = Field(
        ...,
        description="How snapshot was captured",
        examples=["account_sync", "manual_sync", "scheduled_sync"],
    )
    captured_at: datetime = Field(..., description="When balance was captured")
    created_at: datetime = Field(..., description="Record creation timestamp")
    change_amount: Decimal | None = Field(
        None, description="Change from previous snapshot"
    )
    change_percent: float | None = Field(
        None, description="Percentage change from previous"
    )

    @classmethod
    def from_dto(cls, dto: BalanceSnapshotResult) -> "BalanceSnapshotResponse":
        """Convert application DTO to response schema.

        Args:
            dto: BalanceSnapshotResult from handler.

        Returns:
            BalanceSnapshotResponse for API response.
        """
        return cls(
            id=dto.id,
            account_id=dto.account_id,
            balance=dto.balance,
            available_balance=dto.available_balance,
            holdings_value=dto.holdings_value,
            cash_value=dto.cash_value,
            currency=dto.currency,
            source=dto.source,
            captured_at=dto.captured_at,
            created_at=dto.created_at,
            change_amount=dto.change_amount,
            change_percent=dto.change_percent,
        )


class BalanceHistoryResponse(BaseModel):
    """Balance history response for charting.

    Includes computed metrics for change tracking.

    Attributes:
        snapshots: List of snapshot responses (ordered by time).
        total_count: Total number of snapshots in range.
        start_balance: Balance at start of period (nullable).
        end_balance: Balance at end of period (nullable).
        total_change_amount: Change over period (nullable).
        total_change_percent: Percentage change over period (nullable).
        currency: Currency of the values (nullable).
    """

    snapshots: list[BalanceSnapshotResponse] = Field(
        ..., description="List of balance snapshots"
    )
    total_count: int = Field(..., description="Total snapshot count")
    start_balance: Decimal | None = Field(
        None, description="Balance at start of period"
    )
    end_balance: Decimal | None = Field(None, description="Balance at end of period")
    total_change_amount: Decimal | None = Field(
        None, description="Total change over period"
    )
    total_change_percent: float | None = Field(
        None, description="Percentage change over period"
    )
    currency: str | None = Field(None, description="Currency of values")

    @classmethod
    def from_dto(cls, dto: BalanceHistoryResult) -> "BalanceHistoryResponse":
        """Convert application DTO to response schema.

        Args:
            dto: BalanceHistoryResult from handler.

        Returns:
            BalanceHistoryResponse for API response.
        """
        return cls(
            snapshots=[BalanceSnapshotResponse.from_dto(s) for s in dto.snapshots],
            total_count=dto.total_count,
            start_balance=dto.start_balance,
            end_balance=dto.end_balance,
            total_change_amount=dto.total_change_amount,
            total_change_percent=dto.total_change_percent,
            currency=dto.currency,
        )


class LatestSnapshotsResponse(BaseModel):
    """Latest snapshots response for portfolio summary.

    Attributes:
        snapshots: List of latest snapshot responses (one per account).
        total_count: Number of accounts with snapshots.
        total_balance_by_currency: Aggregate balance by currency.
    """

    snapshots: list[BalanceSnapshotResponse] = Field(
        ..., description="Latest snapshot per account"
    )
    total_count: int = Field(..., description="Number of accounts with snapshots")
    total_balance_by_currency: dict[str, str] = Field(
        ..., description="Aggregate balance by currency"
    )

    @classmethod
    def from_dto(cls, dto: LatestSnapshotsResult) -> "LatestSnapshotsResponse":
        """Convert application DTO to response schema.

        Args:
            dto: LatestSnapshotsResult from handler.

        Returns:
            LatestSnapshotsResponse for API response.
        """
        return cls(
            snapshots=[BalanceSnapshotResponse.from_dto(s) for s in dto.snapshots],
            total_count=dto.total_count,
            total_balance_by_currency=dto.total_balance_by_currency,
        )


# =============================================================================
# Request Schemas
# =============================================================================


class BalanceHistoryRequest(BaseModel):
    """Request parameters for balance history query.

    Attributes:
        start_date: Start of date range (inclusive).
        end_date: End of date range (inclusive).
        source: Optional filter by snapshot source.
    """

    start_date: datetime = Field(..., description="Start of date range")
    end_date: datetime = Field(..., description="End of date range")
    source: str | None = Field(
        None,
        description="Filter by snapshot source",
        examples=["account_sync", "manual_sync"],
    )
