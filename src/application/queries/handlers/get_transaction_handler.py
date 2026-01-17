"""GetTransaction query handler.

Handles requests to retrieve a single transaction.
Returns DTO (not domain entity) to prevent leaking domain to presentation.

Architecture:
- Application layer handler (orchestrates data retrieval)
- Returns Result[DTO, str] (explicit error handling)
- NO domain events (queries are side-effect free)
- Ownership verification: Transaction->Account->ProviderConnection->User

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/transaction-domain-model.md
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from src.application.queries.transaction_queries import GetTransaction
from src.application.services.ownership_verifier import (
    OwnershipErrorCode,
    OwnershipVerifier,
)
from src.core.result import Failure, Result, Success


@dataclass
class TransactionResult:
    """Single transaction result DTO.

    Represents a transaction for API response. Money value objects converted
    to separate amount+currency fields for serialization.

    Attributes:
        id: Transaction unique identifier.
        account_id: Account FK.
        provider_transaction_id: Provider's unique ID.
        transaction_type: Type as string (e.g., "trade", "transfer").
        subtype: Subtype as string (e.g., "buy", "deposit").
        status: Status as string (e.g., "settled", "pending").
        amount_value: Transaction amount as Decimal.
        amount_currency: Amount currency code.
        description: Human-readable description.
        asset_type: Asset type as string (e.g., "equity", "option") or None.
        symbol: Security ticker (e.g., "AAPL") or None.
        security_name: Full security name or None.
        quantity: Share/unit quantity or None.
        unit_price_amount: Price per share/unit or None.
        unit_price_currency: Unit price currency or None.
        commission_amount: Trading commission or None.
        commission_currency: Commission currency or None.
        transaction_date: Date transaction occurred.
        settlement_date: Date funds/securities settled or None.
        is_trade: Whether transaction is a trade.
        is_transfer: Whether transaction is a transfer.
        is_income: Whether transaction is income.
        is_fee: Whether transaction is a fee.
        is_debit: Whether transaction debits account (negative).
        is_credit: Whether transaction credits account (positive).
        is_settled: Whether transaction has settled.
        created_at: First sync timestamp.
        updated_at: Last sync timestamp.
    """

    id: UUID
    account_id: UUID
    provider_transaction_id: str
    transaction_type: str
    subtype: str
    status: str
    amount_value: Decimal
    amount_currency: str
    description: str
    asset_type: str | None
    symbol: str | None
    security_name: str | None
    quantity: Decimal | None
    unit_price_amount: Decimal | None
    unit_price_currency: str | None
    commission_amount: Decimal | None
    commission_currency: str | None
    transaction_date: date
    settlement_date: date | None
    is_trade: bool
    is_transfer: bool
    is_income: bool
    is_fee: bool
    is_debit: bool
    is_credit: bool
    is_settled: bool
    created_at: datetime
    updated_at: datetime


class GetTransactionError:
    """GetTransaction-specific errors."""

    TRANSACTION_NOT_FOUND = "Transaction not found"
    ACCOUNT_NOT_FOUND = "Account not found"
    CONNECTION_NOT_FOUND = "Provider connection not found"
    NOT_OWNED_BY_USER = "Transaction not owned by user"


class GetTransactionHandler:
    """Handler for GetTransaction query.

    Retrieves a single transaction by ID with ownership verification.
    Uses OwnershipVerifier to verify: Transaction->Account->ProviderConnection->User

    Dependencies (injected via constructor):
        - OwnershipVerifier: For transaction retrieval with ownership verification
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

    async def handle(self, query: GetTransaction) -> Result[TransactionResult, str]:
        """Handle GetTransaction query.

        Retrieves transaction, verifies ownership via Account->Connection chain,
        and maps to DTO.

        Args:
            query: GetTransaction query with transaction and user IDs.

        Returns:
            Success(TransactionResult): Transaction found and owned by user.
            Failure(error): Transaction not found or not owned by user.
        """
        # Verify ownership and get transaction
        result = await self._verifier.verify_transaction_ownership(
            query.transaction_id, query.user_id
        )

        if isinstance(result, Failure):
            # Map OwnershipError to handler-specific error string
            error_map = {
                OwnershipErrorCode.TRANSACTION_NOT_FOUND: GetTransactionError.TRANSACTION_NOT_FOUND,
                OwnershipErrorCode.ACCOUNT_NOT_FOUND: GetTransactionError.ACCOUNT_NOT_FOUND,
                OwnershipErrorCode.CONNECTION_NOT_FOUND: GetTransactionError.CONNECTION_NOT_FOUND,
                OwnershipErrorCode.NOT_OWNED_BY_USER: GetTransactionError.NOT_OWNED_BY_USER,
            }
            return Failure(
                error=error_map.get(
                    result.error.code, GetTransactionError.NOT_OWNED_BY_USER
                )
            )

        transaction = result.value

        # Map to DTO (Money -> amount+currency)
        dto = TransactionResult(
            id=transaction.id,
            account_id=transaction.account_id,
            provider_transaction_id=transaction.provider_transaction_id,
            transaction_type=transaction.transaction_type.value,
            subtype=transaction.subtype.value,
            status=transaction.status.value,
            amount_value=transaction.amount.amount,
            amount_currency=transaction.amount.currency,
            description=transaction.description,
            asset_type=(
                transaction.asset_type.value if transaction.asset_type else None
            ),
            symbol=transaction.symbol,
            security_name=transaction.security_name,
            quantity=transaction.quantity,
            unit_price_amount=(
                transaction.unit_price.amount if transaction.unit_price else None
            ),
            unit_price_currency=(
                transaction.unit_price.currency if transaction.unit_price else None
            ),
            commission_amount=(
                transaction.commission.amount if transaction.commission else None
            ),
            commission_currency=(
                transaction.commission.currency if transaction.commission else None
            ),
            transaction_date=transaction.transaction_date,
            settlement_date=transaction.settlement_date,
            is_trade=transaction.is_trade(),
            is_transfer=transaction.is_transfer(),
            is_income=transaction.is_income(),
            is_fee=transaction.is_fee(),
            is_debit=transaction.is_debit(),
            is_credit=transaction.is_credit(),
            is_settled=transaction.is_settled(),
            created_at=transaction.created_at,
            updated_at=transaction.updated_at,
        )

        return Success(value=dto)
