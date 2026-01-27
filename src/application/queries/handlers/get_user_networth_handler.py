"""GetUserNetWorth query handler.

Handles requests to calculate user's aggregated net worth.
Returns DTO with total balance across all active accounts.

Architecture:
- Application layer handler (orchestrates data retrieval)
- Returns Result[DTO, str] (explicit error handling)
- NO domain events (queries are side-effect free)

Reference:
    - docs/architecture/cqrs-pattern.md
    - Implementation Plan: Issue #257, Phase 7
"""

from dataclasses import dataclass
from decimal import Decimal

from src.application.queries.portfolio_queries import GetUserNetWorth
from src.core.result import Result, Success
from src.domain.protocols.account_repository import AccountRepository


@dataclass
class NetWorthResult:
    """Net worth result DTO.

    Represents aggregated portfolio value for API response.

    Attributes:
        net_worth: Total balance across all active accounts.
        account_count: Number of active accounts included in calculation.
        currency: Base currency for calculation (currently always USD).
    """

    net_worth: Decimal
    account_count: int
    currency: str


class GetUserNetWorthHandler:
    """Handler for GetUserNetWorth query.

    Calculates total balance across all active accounts for a user.
    Uses AccountRepository aggregate methods.

    Dependencies (injected via constructor):
        - AccountRepository: For querying account balances
    """

    def __init__(
        self,
        account_repo: AccountRepository,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            account_repo: Repository for account balance queries.
        """
        self._account_repo = account_repo

    async def handle(self, query: GetUserNetWorth) -> Result[NetWorthResult, str]:
        """Handle GetUserNetWorth query.

        Calculates net worth by summing all active account balances.

        Args:
            query: GetUserNetWorth query with user_id.

        Returns:
            Success(NetWorthResult): Net worth calculated successfully.

        Note:
            This query always succeeds - returns 0 if user has no accounts.
            No failure cases since we're just summing balances.
        """
        # Query aggregated balance and account count
        total = await self._account_repo.sum_balances_for_user(query.user_id)
        count = await self._account_repo.count_for_user(query.user_id)

        # Map to DTO
        dto = NetWorthResult(
            net_worth=total,
            account_count=count,
            currency="USD",  # TODO: Get user's base currency from settings
        )

        return Success(value=dto)
