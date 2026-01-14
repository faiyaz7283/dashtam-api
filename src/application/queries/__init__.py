"""Queries - Read operations that fetch data.

Queries represent a request for information. They are immutable dataclasses
with question-like names (GetUser, ListAccounts).

Each query has a corresponding handler that fetches and returns the requested
data. Queries NEVER change state.
"""

from src.application.queries.session_queries import GetSession, ListUserSessions
from src.application.queries.provider_queries import (
    GetProviderConnection,
    ListProviderConnections,
)
from src.application.queries.account_queries import (
    GetAccount,
    ListAccountsByConnection,
    ListAccountsByUser,
)
from src.application.queries.transaction_queries import (
    GetTransaction,
    ListSecurityTransactions,
    ListTransactionsByAccount,
    ListTransactionsByDateRange,
)
from src.application.queries.balance_snapshot_queries import (
    GetBalanceHistory,
    GetLatestBalanceSnapshots,
    GetUserBalanceHistory,
    ListBalanceSnapshotsByAccount,
)
from src.application.queries.holding_queries import (
    GetHolding,
    ListHoldingsByAccount,
    ListHoldingsByUser,
)

__all__ = [
    # Session queries
    "GetSession",
    "ListUserSessions",
    # Provider queries (F3.4)
    "GetProviderConnection",
    "ListProviderConnections",
    # Account queries (F3.5)
    "GetAccount",
    "ListAccountsByConnection",
    "ListAccountsByUser",
    # Transaction queries (F3.6)
    "GetTransaction",
    "ListTransactionsByAccount",
    "ListTransactionsByDateRange",
    "ListSecurityTransactions",
    # Balance snapshot queries (F3.7)
    "GetBalanceHistory",
    "GetLatestBalanceSnapshots",
    "GetUserBalanceHistory",
    "ListBalanceSnapshotsByAccount",
    # Holding queries (F3.8)
    "GetHolding",
    "ListHoldingsByAccount",
    "ListHoldingsByUser",
]
