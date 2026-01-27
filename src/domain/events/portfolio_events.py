"""Portfolio domain events (Issue #257).

These are OPERATIONAL events for real-time portfolio value notifications.
They are NOT part of a 3-state workflow (ATTEMPT → OUTCOME) since sync operations
already handle that pattern. These events represent computed changes that SSE
clients need to know about.

Events:
1. AccountBalanceUpdated - Balance changed during sync
2. AccountHoldingsUpdated - Holdings changed during sync
3. PortfolioNetWorthRecalculated - Net worth changed (aggregated)

Handlers:
- LoggingEventHandler: ALL events (DEBUG level)
- SSEEventHandler: ALL events (broadcast to client)

Note:
    These events don't require audit since the underlying sync operations
    already have full audit coverage (AccountSyncSucceeded, etc.).
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from src.domain.events.base_event import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class AccountBalanceUpdated(DomainEvent):
    """Emitted after account balance changes during sync.

    This is an OPERATIONAL event for real-time SSE notifications.
    Allows clients to update UI without polling.

    Triggers:
    - LoggingEventHandler: Log balance change (DEBUG)
    - SSEEventHandler: Broadcast via SSE (portfolio.balance.updated)

    Attributes:
        user_id: User who owns the account.
        account_id: Account whose balance changed.
        previous_balance: Balance before sync.
        new_balance: Balance after sync.
        delta: Change amount (new_balance - previous_balance).
        currency: Currency code (e.g., "USD").
    """

    user_id: UUID
    account_id: UUID
    previous_balance: Decimal
    new_balance: Decimal
    delta: Decimal
    currency: str


@dataclass(frozen=True, kw_only=True, slots=True)
class AccountHoldingsUpdated(DomainEvent):
    """Emitted after holdings change during sync.

    This is an OPERATIONAL event for real-time SSE notifications.
    Allows clients to update UI without polling.

    Triggers:
    - LoggingEventHandler: Log holdings change (DEBUG)
    - SSEEventHandler: Broadcast via SSE (portfolio.holdings.updated)

    Attributes:
        user_id: User who owns the account.
        account_id: Account whose holdings changed.
        holdings_count: Total holdings after sync.
        created_count: New holdings created.
        updated_count: Existing holdings updated.
        deactivated_count: Holdings marked inactive.
    """

    user_id: UUID
    account_id: UUID
    holdings_count: int
    created_count: int
    updated_count: int
    deactivated_count: int


@dataclass(frozen=True, kw_only=True, slots=True)
class PortfolioNetWorthRecalculated(DomainEvent):
    """Emitted after net worth is recalculated.

    This is an OPERATIONAL event for real-time SSE notifications.
    Triggered by PortfolioEventHandler after balance/holdings changes.

    Triggers:
    - LoggingEventHandler: Log net worth change (INFO)
    - SSEEventHandler: Broadcast via SSE (portfolio.networth.updated)

    Attributes:
        user_id: User whose net worth changed.
        previous_net_worth: Net worth before change.
        new_net_worth: Net worth after change.
        delta: Change amount (new - previous).
        currency: Base currency for calculation (e.g., "USD").
        account_count: Number of active accounts in calculation.
    """

    user_id: UUID
    previous_net_worth: Decimal
    new_net_worth: Decimal
    delta: Decimal
    currency: str
    account_count: int
