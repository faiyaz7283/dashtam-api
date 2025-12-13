"""Account request and response schemas.

Pydantic schemas for account API endpoints. Includes:
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

from src.application.queries.handlers.get_account_handler import AccountResult
from src.application.queries.handlers.list_accounts_handler import AccountListResult
from src.schemas.common_schemas import SyncResponse


# =============================================================================
# Response Schemas
# =============================================================================


class AccountResponse(BaseModel):
    """Single account response.

    Attributes:
        id: Account unique identifier.
        connection_id: Provider connection FK.
        provider_account_id: Provider's identifier for this account.
        account_number_masked: Masked number for display (e.g., "****1234").
        name: Account name from provider.
        account_type: Type as string (e.g., "brokerage", "ira").
        currency: ISO 4217 currency code.
        balance_amount: Current balance.
        balance_currency: Balance currency code.
        available_balance_amount: Available balance (if different).
        available_balance_currency: Available balance currency.
        is_active: Whether account is active on provider.
        is_investment: Whether account is investment type.
        is_bank: Whether account is banking type.
        is_retirement: Whether account is retirement type.
        is_credit: Whether account is credit type.
        last_synced_at: Last successful sync timestamp.
        created_at: Record creation timestamp.
        updated_at: Last modification timestamp.
    """

    id: UUID = Field(..., description="Account unique identifier")
    connection_id: UUID = Field(..., description="Provider connection FK")
    provider_account_id: str = Field(..., description="Provider's account identifier")
    account_number_masked: str = Field(
        ..., description="Masked account number", examples=["****1234"]
    )
    name: str = Field(..., description="Account name from provider")
    account_type: str = Field(
        ..., description="Account type", examples=["brokerage", "ira", "checking"]
    )
    currency: str = Field(..., description="ISO 4217 currency code", examples=["USD"])
    balance_amount: Decimal = Field(..., description="Current balance")
    balance_currency: str = Field(..., description="Balance currency code")
    available_balance_amount: Decimal | None = Field(
        None, description="Available balance"
    )
    available_balance_currency: str | None = Field(
        None, description="Available balance currency"
    )
    is_active: bool = Field(..., description="Whether account is active")
    is_investment: bool = Field(..., description="Is investment account")
    is_bank: bool = Field(..., description="Is bank account")
    is_retirement: bool = Field(..., description="Is retirement account")
    is_credit: bool = Field(..., description="Is credit account")
    last_synced_at: datetime | None = Field(None, description="Last sync timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    @classmethod
    def from_dto(cls, dto: AccountResult) -> "AccountResponse":
        """Convert application DTO to response schema.

        Args:
            dto: AccountResult from handler.

        Returns:
            AccountResponse for API response.
        """
        return cls(
            id=dto.id,
            connection_id=dto.connection_id,
            provider_account_id=dto.provider_account_id,
            account_number_masked=dto.account_number_masked,
            name=dto.name,
            account_type=dto.account_type,
            currency=dto.currency,
            balance_amount=dto.balance_amount,
            balance_currency=dto.balance_currency,
            available_balance_amount=dto.available_balance_amount,
            available_balance_currency=dto.available_balance_currency,
            is_active=dto.is_active,
            is_investment=dto.is_investment,
            is_bank=dto.is_bank,
            is_retirement=dto.is_retirement,
            is_credit=dto.is_credit,
            last_synced_at=dto.last_synced_at,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class AccountListResponse(BaseModel):
    """Account list response with aggregates.

    Attributes:
        accounts: List of accounts.
        total_count: Total number of accounts.
        active_count: Number of active accounts.
        total_balance_by_currency: Aggregated balances by currency.
    """

    accounts: list[AccountResponse] = Field(..., description="List of accounts")
    total_count: int = Field(..., description="Total account count")
    active_count: int = Field(..., description="Active account count")
    total_balance_by_currency: dict[str, str] = Field(
        ..., description="Aggregated balances by currency"
    )

    @classmethod
    def from_dto(cls, dto: AccountListResult) -> "AccountListResponse":
        """Convert application DTO to response schema.

        Args:
            dto: AccountListResult from handler.

        Returns:
            AccountListResponse for API response.
        """
        return cls(
            accounts=[AccountResponse.from_dto(acc) for acc in dto.accounts],
            total_count=dto.total_count,
            active_count=dto.active_count,
            total_balance_by_currency=dto.total_balance_by_currency,
        )


class SyncAccountsResponse(SyncResponse):
    """Response for account sync operation.

    Extends SyncResponse with account-specific fields.

    Attributes:
        accounts_created: Number of new accounts created.
        accounts_updated: Number of existing accounts updated.
    """

    accounts_created: int = Field(0, description="New accounts created")
    accounts_updated: int = Field(0, description="Existing accounts updated")


# =============================================================================
# Request Schemas
# =============================================================================


class SyncAccountsRequest(BaseModel):
    """Request to sync accounts from provider.

    Attributes:
        connection_id: Provider connection to sync from.
        force: Force sync even if recently synced.
    """

    connection_id: UUID = Field(..., description="Provider connection to sync")
    force: bool = Field(False, description="Force sync even if recently synced")
