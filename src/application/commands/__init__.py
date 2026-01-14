"""Commands - Write operations that change state.

Commands represent user intent to perform an action. They are immutable
dataclasses with imperative names (RegisterUser, UpdatePassword).

Each command has a corresponding handler that contains the business logic
to execute the command.
"""

from src.application.commands.auth_commands import (
    AuthenticateUser,
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
from src.application.commands.token_commands import GenerateAuthTokens
from src.application.dtos import AuthenticatedUser, AuthTokens
from src.application.commands.provider_commands import (
    ConnectProvider,
    DisconnectProvider,
    RefreshProviderTokens,
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
    # Provider commands (F3.4)
    "ConnectProvider",
    "DisconnectProvider",
    "RefreshProviderTokens",
]
