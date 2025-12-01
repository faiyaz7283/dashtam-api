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
]
