"""Commands - Write operations that change state.

Commands represent user intent to perform an action. They are immutable
dataclasses with imperative names (RegisterUser, UpdatePassword).

Each command has a corresponding handler that contains the business logic
to execute the command.
"""

from src.application.commands.auth_commands import (
    ConfirmPasswordReset,
    LoginUser,
    LogoutUser,
    RefreshToken,
    RegisterUser,
    RequestPasswordReset,
    VerifyEmail,
)

__all__ = [
    "ConfirmPasswordReset",
    "LoginUser",
    "LogoutUser",
    "RefreshToken",
    "RegisterUser",
    "RequestPasswordReset",
    "VerifyEmail",
]
