"""Commands - Write operations that change state.

Commands represent user intent to perform an action. They are immutable
dataclasses with imperative names (RegisterUser, UpdatePassword).

Each command has a corresponding handler that contains the business logic
to execute the command.
"""

from src.application.commands.auth_commands import (
    AuthenticateUser,
    AuthenticatedUser,
    ConfirmPasswordReset,
    LogoutUser,
    RefreshAccessToken,
    RegisterUser,
    RequestPasswordReset,
    VerifyEmail,
)
from src.application.commands.session_commands import (
    CreateSession,
    LinkRefreshTokenToSession,
    RecordProviderAccess,
    RevokeAllUserSessions,
    RevokeSession,
    UpdateSessionActivity,
)
from src.application.commands.token_commands import (
    AuthTokens,
    GenerateAuthTokens,
)

__all__ = [
    # Auth commands
    "AuthenticateUser",
    "AuthenticatedUser",
    "ConfirmPasswordReset",
    "LogoutUser",
    "RefreshAccessToken",
    "RegisterUser",
    "RequestPasswordReset",
    "VerifyEmail",
    # Session commands
    "CreateSession",
    "LinkRefreshTokenToSession",
    "RecordProviderAccess",
    "RevokeAllUserSessions",
    "RevokeSession",
    "UpdateSessionActivity",
    # Token commands
    "AuthTokens",
    "GenerateAuthTokens",
]
