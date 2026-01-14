"""Token generation commands (CQRS write operations).

Commands represent user intent to generate authentication tokens.
All commands are immutable (frozen=True) and use keyword-only arguments (kw_only=True).

Pattern:
- Commands are data containers (no logic)
- Handlers execute business logic
- Commands don't return values (handlers return Result types)
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class GenerateAuthTokens:
    """Generate JWT access token and opaque refresh token.

    Single responsibility: Token generation and persistence only.
    Called after authentication and session creation.

    Attributes:
        user_id: User's unique identifier.
        email: User's email address (included in JWT payload).
        roles: User's roles for authorization (included in JWT payload).
        session_id: Session identifier (links refresh token to session).

    Example:
        >>> command = GenerateAuthTokens(
        ...     user_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        ...     email="user@example.com",
        ...     roles=["user"],
        ...     session_id=UUID("abc123..."),
        ... )
        >>> result = await handler.handle(command)
        >>> # Returns Success(AuthTokens) or Failure(error)
    """

    user_id: UUID
    email: str
    roles: list[str]
    session_id: UUID
