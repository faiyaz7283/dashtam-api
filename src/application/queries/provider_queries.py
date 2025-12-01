"""Provider queries (CQRS read operations).

Queries represent requests for provider connection data. They are
immutable dataclasses with question-like names. Queries NEVER change state.

Pattern:
- Queries are data containers (no logic)
- Handlers fetch and return data
- Queries never change state
- Queries do NOT emit domain events

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/provider-domain-model.md
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class GetProviderConnection:
    """Get a single provider connection by ID.

    Retrieves connection details for display or verification.
    Includes ownership check via user_id.

    Attributes:
        connection_id: Connection to retrieve.
        user_id: User requesting (for ownership verification).

    Example:
        >>> query = GetProviderConnection(
        ...     connection_id=connection_id,
        ...     user_id=user_id,
        ... )
        >>> result = await handler.handle(query)
    """

    connection_id: UUID
    user_id: UUID


@dataclass(frozen=True, kw_only=True)
class ListProviderConnections:
    """List all provider connections for a user.

    Retrieves all connections (or filtered to active only) for
    display in dashboard or settings.

    Attributes:
        user_id: User whose connections to list.
        active_only: If True, only return ACTIVE connections.
            Default False returns all statuses.

    Example:
        >>> query = ListProviderConnections(
        ...     user_id=user_id,
        ...     active_only=True,
        ... )
        >>> result = await handler.handle(query)
    """

    user_id: UUID
    active_only: bool = False
