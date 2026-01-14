"""Authentication DTOs (Data Transfer Objects).

Response/result dataclasses for authentication command handlers.
These carry data from handlers back to the presentation layer.

DTOs:
    - AuthenticatedUser: Result from AuthenticateUser command
    - AuthTokens: Result from GenerateAuthTokens command
    - GlobalRotationResult: Result from TriggerGlobalTokenRotation command
    - UserRotationResult: Result from TriggerUserTokenRotation command

Reference:
    - docs/architecture/cqrs.md (DTOs section)
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class AuthenticatedUser:
    """Response from successful authentication.

    Contains user data needed for session creation and token generation.

    Attributes:
        user_id: User's unique identifier.
        email: User's email address (normalized).
        roles: User's roles for authorization.
    """

    user_id: UUID
    email: str
    roles: list[str]


@dataclass(frozen=True, kw_only=True)
class AuthTokens:
    """Response from successful token generation.

    Contains the authentication tokens to return to the client.

    Attributes:
        access_token: JWT access token (short-lived, 15 minutes).
        refresh_token: Opaque refresh token (long-lived, 30 days).
        token_type: Token type (always "bearer").
        expires_in: Access token expiration in seconds.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes in seconds


@dataclass(frozen=True, kw_only=True)
class GlobalRotationResult:
    """Response from successful global rotation.

    Attributes:
        previous_version: Version before rotation.
        new_version: Version after rotation.
        grace_period_seconds: Time window where old tokens still work.
    """

    previous_version: int
    new_version: int
    grace_period_seconds: int


@dataclass(frozen=True, kw_only=True)
class UserRotationResult:
    """Response from successful per-user rotation.

    Attributes:
        user_id: User whose tokens were rotated.
        previous_version: Version before rotation.
        new_version: Version after rotation.
    """

    user_id: UUID
    previous_version: int
    new_version: int
