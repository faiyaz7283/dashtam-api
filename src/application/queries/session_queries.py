"""Session queries (CQRS read operations).

Queries represent requests for session information. They are immutable
dataclasses with question-like names. Queries NEVER change state.

Pattern:
- Queries are data containers (no logic)
- Handlers fetch and return data
- Queries never change state
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class GetSession:
    """Get a single session by ID.

    Attributes:
        session_id: Session identifier.
        user_id: User identifier (for authorization check).

    Example:
        >>> query = GetSession(
        ...     session_id=UUID("abc123..."),
        ...     user_id=UUID("123e4567..."),
        ... )
        >>> result = await handler.handle(query)
    """

    session_id: UUID
    user_id: UUID


@dataclass(frozen=True, kw_only=True)
class ListUserSessions:
    """List all sessions for a user.

    Attributes:
        user_id: User identifier.
        active_only: If True, only return active (non-revoked, non-expired) sessions.
        current_session_id: Current session ID (to mark it in response).

    Example:
        >>> query = ListUserSessions(
        ...     user_id=UUID("123e4567..."),
        ...     active_only=True,
        ...     current_session_id=UUID("abc123..."),
        ... )
        >>> result = await handler.handle(query)
    """

    user_id: UUID
    active_only: bool = True
    current_session_id: UUID | None = None
