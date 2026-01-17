"""GetAccount query handler.

Handles requests to retrieve a single account.
Returns DTO (not domain entity) to prevent leaking domain to presentation.

Architecture:
- Application layer handler (orchestrates data retrieval)
- Returns Result[DTO, str] (explicit error handling)
- NO domain events (queries are side-effect free)

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/account-domain-model.md
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from src.application.queries.account_queries import GetAccount
from src.application.services.ownership_verifier import (
    OwnershipErrorCode,
    OwnershipVerifier,
)
from src.core.result import Failure, Result, Success


@dataclass
class AccountResult:
    """Single account result DTO.

    Represents an account for API response. Does NOT include sensitive data.
    Money value objects converted to separate amount+currency fields.

    Attributes:
        id: Account unique identifier.
        connection_id: Provider connection FK.
        provider_account_id: Provider's identifier for this account.
        account_number_masked: Masked number for display (e.g., "****1234").
        name: Account name from provider.
        account_type: Type as string (e.g., "brokerage", "ira").
        currency: ISO 4217 currency code.
        balance_amount: Current balance as Decimal.
        balance_currency: Balance currency code (matches currency).
        available_balance_amount: Available balance (if different from balance).
        available_balance_currency: Available balance currency (if present).
        is_active: Whether account is active on provider.
        is_investment: Whether account is investment type.
        is_bank: Whether account is banking type.
        is_retirement: Whether account is retirement type.
        is_credit: Whether account is credit type.
        last_synced_at: Last successful sync timestamp.
        created_at: Record creation timestamp.
        updated_at: Last modification timestamp.
    """

    id: UUID
    connection_id: UUID
    provider_account_id: str
    account_number_masked: str
    name: str
    account_type: str
    currency: str
    balance_amount: Decimal
    balance_currency: str
    available_balance_amount: Decimal | None
    available_balance_currency: str | None
    is_active: bool
    is_investment: bool
    is_bank: bool
    is_retirement: bool
    is_credit: bool
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GetAccountError:
    """GetAccount-specific errors."""

    ACCOUNT_NOT_FOUND = "Account not found"
    CONNECTION_NOT_FOUND = "Provider connection not found"
    NOT_OWNED_BY_USER = "Account not owned by user"


class GetAccountHandler:
    """Handler for GetAccount query.

    Retrieves a single account by ID with ownership verification.
    Uses OwnershipVerifier to verify the user owns the account via connection.

    Dependencies (injected via constructor):
        - OwnershipVerifier: For account retrieval with ownership verification
    """

    def __init__(
        self,
        ownership_verifier: OwnershipVerifier,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            ownership_verifier: Service for ownership verification.
        """
        self._verifier = ownership_verifier

    async def handle(self, query: GetAccount) -> Result[AccountResult, str]:
        """Handle GetAccount query.

        Retrieves account, verifies ownership via connection, and maps to DTO.

        Args:
            query: GetAccount query with account and user IDs.

        Returns:
            Success(AccountResult): Account found and owned by user.
            Failure(error): Account not found or not owned by user.
        """
        # Verify ownership and get account
        result = await self._verifier.verify_account_ownership(
            query.account_id, query.user_id
        )

        if isinstance(result, Failure):
            # Map OwnershipError to handler-specific error string
            error_map = {
                OwnershipErrorCode.ACCOUNT_NOT_FOUND: GetAccountError.ACCOUNT_NOT_FOUND,
                OwnershipErrorCode.CONNECTION_NOT_FOUND: GetAccountError.CONNECTION_NOT_FOUND,
                OwnershipErrorCode.NOT_OWNED_BY_USER: GetAccountError.NOT_OWNED_BY_USER,
            }
            return Failure(
                error=error_map.get(
                    result.error.code, GetAccountError.NOT_OWNED_BY_USER
                )
            )

        account = result.value

        # Map to DTO (Money -> amount+currency)
        dto = AccountResult(
            id=account.id,
            connection_id=account.connection_id,
            provider_account_id=account.provider_account_id,
            account_number_masked=account.account_number_masked,
            name=account.name,
            account_type=account.account_type.value,
            currency=account.currency,
            balance_amount=account.balance.amount,
            balance_currency=account.balance.currency,
            available_balance_amount=(
                account.available_balance.amount if account.available_balance else None
            ),
            available_balance_currency=(
                account.available_balance.currency
                if account.available_balance
                else None
            ),
            is_active=account.is_active,
            is_investment=account.is_investment_account(),
            is_bank=account.is_bank_account(),
            is_retirement=account.is_retirement_account(),
            is_credit=account.is_credit_account(),
            last_synced_at=account.last_synced_at,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )

        return Success(value=dto)
