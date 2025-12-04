"""Transaction request and response schemas.

Pydantic schemas for transaction API endpoints. Includes:
- Request schemas (client → API)
- Response schemas (API → client)
- DTO-to-schema conversion methods

Reference:
    - docs/architecture/api-design-patterns.md
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from src.application.queries.handlers.get_transaction_handler import TransactionResult
from src.application.queries.handlers.list_transactions_handler import (
    TransactionListResult,
)
from src.schemas.common_schemas import SyncResponse


# =============================================================================
# Response Schemas
# =============================================================================


class TransactionResponse(BaseModel):
    """Single transaction response.

    Attributes:
        id: Transaction unique identifier.
        account_id: Account FK.
        provider_transaction_id: Provider's unique ID.
        transaction_type: Type (e.g., "trade", "transfer").
        subtype: Subtype (e.g., "buy", "deposit").
        status: Status (e.g., "settled", "pending").
        amount_value: Transaction amount.
        amount_currency: Amount currency code.
        description: Human-readable description.
        asset_type: Asset type or None.
        symbol: Security ticker or None.
        security_name: Full security name or None.
        quantity: Share/unit quantity or None.
        unit_price_amount: Price per share/unit or None.
        unit_price_currency: Unit price currency or None.
        commission_amount: Trading commission or None.
        commission_currency: Commission currency or None.
        transaction_date: Date transaction occurred.
        settlement_date: Date settled or None.
        is_trade: Whether transaction is a trade.
        is_transfer: Whether transaction is a transfer.
        is_income: Whether transaction is income.
        is_fee: Whether transaction is a fee.
        is_debit: Whether debits account.
        is_credit: Whether credits account.
        is_settled: Whether settled.
        created_at: First sync timestamp.
        updated_at: Last sync timestamp.
    """

    id: UUID = Field(..., description="Transaction unique identifier")
    account_id: UUID = Field(..., description="Account FK")
    provider_transaction_id: str = Field(..., description="Provider's unique ID")
    transaction_type: str = Field(
        ..., description="Transaction type", examples=["trade", "transfer", "income"]
    )
    subtype: str = Field(
        ..., description="Transaction subtype", examples=["buy", "sell", "deposit"]
    )
    status: str = Field(
        ..., description="Transaction status", examples=["settled", "pending"]
    )
    amount_value: Decimal = Field(..., description="Transaction amount")
    amount_currency: str = Field(..., description="Amount currency code")
    description: str = Field(..., description="Human-readable description")
    asset_type: str | None = Field(
        None, description="Asset type", examples=["equity", "option", "crypto"]
    )
    symbol: str | None = Field(
        None, description="Security ticker", examples=["AAPL", "TSLA"]
    )
    security_name: str | None = Field(None, description="Full security name")
    quantity: Decimal | None = Field(None, description="Share/unit quantity")
    unit_price_amount: Decimal | None = Field(None, description="Price per share/unit")
    unit_price_currency: str | None = Field(None, description="Unit price currency")
    commission_amount: Decimal | None = Field(None, description="Trading commission")
    commission_currency: str | None = Field(None, description="Commission currency")
    transaction_date: date = Field(..., description="Date transaction occurred")
    settlement_date: date | None = Field(None, description="Date settled")
    is_trade: bool = Field(..., description="Is a trade")
    is_transfer: bool = Field(..., description="Is a transfer")
    is_income: bool = Field(..., description="Is income")
    is_fee: bool = Field(..., description="Is a fee")
    is_debit: bool = Field(..., description="Debits account (negative)")
    is_credit: bool = Field(..., description="Credits account (positive)")
    is_settled: bool = Field(..., description="Has settled")
    created_at: datetime = Field(..., description="First sync timestamp")
    updated_at: datetime = Field(..., description="Last sync timestamp")

    @classmethod
    def from_dto(cls, dto: TransactionResult) -> "TransactionResponse":
        """Convert application DTO to response schema.

        Args:
            dto: TransactionResult from handler.

        Returns:
            TransactionResponse for API response.
        """
        return cls(
            id=dto.id,
            account_id=dto.account_id,
            provider_transaction_id=dto.provider_transaction_id,
            transaction_type=dto.transaction_type,
            subtype=dto.subtype,
            status=dto.status,
            amount_value=dto.amount_value,
            amount_currency=dto.amount_currency,
            description=dto.description,
            asset_type=dto.asset_type,
            symbol=dto.symbol,
            security_name=dto.security_name,
            quantity=dto.quantity,
            unit_price_amount=dto.unit_price_amount,
            unit_price_currency=dto.unit_price_currency,
            commission_amount=dto.commission_amount,
            commission_currency=dto.commission_currency,
            transaction_date=dto.transaction_date,
            settlement_date=dto.settlement_date,
            is_trade=dto.is_trade,
            is_transfer=dto.is_transfer,
            is_income=dto.is_income,
            is_fee=dto.is_fee,
            is_debit=dto.is_debit,
            is_credit=dto.is_credit,
            is_settled=dto.is_settled,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class TransactionListResponse(BaseModel):
    """Transaction list response with pagination.

    Attributes:
        transactions: List of transactions.
        total_count: Total count of transactions.
        has_more: Whether more results are available.
    """

    transactions: list[TransactionResponse] = Field(
        ..., description="List of transactions"
    )
    total_count: int = Field(..., description="Total transaction count")
    has_more: bool = Field(..., description="Whether more results available")

    @classmethod
    def from_dto(cls, dto: TransactionListResult) -> "TransactionListResponse":
        """Convert application DTO to response schema.

        Args:
            dto: TransactionListResult from handler.

        Returns:
            TransactionListResponse for API response.
        """
        return cls(
            transactions=[TransactionResponse.from_dto(t) for t in dto.transactions],
            total_count=dto.total_count,
            has_more=dto.has_more,
        )


class SyncTransactionsResponse(SyncResponse):
    """Response for transaction sync operation.

    Extends SyncResponse with transaction-specific fields.

    Attributes:
        transactions_created: Number of new transactions created.
        transactions_updated: Number of existing transactions updated.
    """

    transactions_created: int = Field(0, description="New transactions created")
    transactions_updated: int = Field(0, description="Existing transactions updated")


# =============================================================================
# Request Schemas
# =============================================================================


class SyncTransactionsRequest(BaseModel):
    """Request to sync transactions from provider.

    Attributes:
        connection_id: Provider connection to sync from.
        account_id: Optional specific account to sync (all if None).
        start_date: Optional start date for sync range.
        end_date: Optional end date for sync range.
        force: Force sync even if recently synced.
    """

    connection_id: UUID = Field(..., description="Provider connection to sync")
    account_id: UUID | None = Field(
        None, description="Specific account to sync (all if None)"
    )
    start_date: date | None = Field(None, description="Start date for sync range")
    end_date: date | None = Field(None, description="End date for sync range")
    force: bool = Field(False, description="Force sync even if recently synced")
