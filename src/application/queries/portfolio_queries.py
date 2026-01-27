"""Portfolio queries (CQRS read operations).

Queries for portfolio-level data (net worth, aggregated balances, etc.).
These are immutable dataclasses for explicit client requests.

Pattern:
- Queries are data containers (no logic)
- Handlers fetch and return data
- Queries never change state
- Queries do NOT emit domain events

Reference:
    - docs/architecture/cqrs-pattern.md
    - Implementation Plan: Issue #257, Phase 7
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class GetUserNetWorth:
    """Get aggregated net worth for a user.

    Calculates total balance across all active accounts.
    Used for explicit client requests (e.g., dashboard load).

    Note: Real-time updates use SSE events (portfolio.networth.updated),
    not polling this query.

    Attributes:
        user_id: User whose net worth to calculate.

    Example:
        >>> query = GetUserNetWorth(user_id=user_id)
        >>> result = await handler.handle(query)
        >>> net_worth = result.value.net_worth
    """

    user_id: UUID
