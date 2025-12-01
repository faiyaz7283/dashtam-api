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

__all__ = [
    # Session queries
    "GetSession",
    "ListUserSessions",
    # Provider queries (F3.4)
    "GetProviderConnection",
    "ListProviderConnections",
]
