"""Password resets resource handlers.

Handler functions for password reset endpoints.
Routes are registered via ROUTE_REGISTRY in routes/registry.py.

Handlers:
    create_password_reset_token - Create password reset token (request reset)
    create_password_reset       - Create password reset (execute reset)
"""

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from src.application.commands.auth_commands import (
    ConfirmPasswordReset,
    RequestPasswordReset,
)
from src.application.commands.handlers.confirm_password_reset_handler import (
    ConfirmPasswordResetHandler,
)
from src.application.commands.handlers.request_password_reset_handler import (
    RequestPasswordResetHandler,
)
from src.application.errors import ApplicationError, ApplicationErrorCode
from src.core.container.handler_factory import handler_factory
from src.core.result import Failure, Success
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id
from src.presentation.routers.api.v1.errors import ErrorResponseBuilder
from src.schemas.auth_schemas import (
    PasswordResetCreateRequest,
    PasswordResetCreateResponse,
    PasswordResetTokenCreateRequest,
    PasswordResetTokenCreateResponse,
)


async def create_password_reset_token(
    request: Request,
    data: PasswordResetTokenCreateRequest,
    handler: RequestPasswordResetHandler = Depends(
        handler_factory(RequestPasswordResetHandler)
    ),
) -> PasswordResetTokenCreateResponse:
    """Create password reset token (request reset).

    POST /api/v1/password-reset-tokens → 201 Created

    Sends a password reset email if the account exists.
    Always returns success to prevent user enumeration attacks.

    Args:
        request: FastAPI request object.
        data: Password reset token request (email).
        handler: Request password reset handler (injected).

    Returns:
        PasswordResetTokenCreateResponse (always 201 for security).
    """
    # Get client IP and user agent for audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Create command from request data
    command = RequestPasswordReset(
        email=data.email,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Execute handler (always returns success for security)
    await handler.handle(command, request)

    # Always return success to prevent user enumeration
    return PasswordResetTokenCreateResponse()


async def create_password_reset(
    request: Request,
    data: PasswordResetCreateRequest,
    handler: ConfirmPasswordResetHandler = Depends(
        handler_factory(ConfirmPasswordResetHandler)
    ),
) -> PasswordResetCreateResponse | JSONResponse:
    """Create password reset (execute reset).

    POST /api/v1/password-resets → 201 Created

    Resets user's password using the token from email.
    All existing sessions are revoked (user must re-login).

    Args:
        request: FastAPI request object.
        data: Password reset request (token, new_password).
        handler: Confirm password reset handler (injected).

    Returns:
        PasswordResetCreateResponse on success (201 Created).
        JSONResponse with error on failure (400/404).
    """
    # Create command from request data
    command = ConfirmPasswordReset(
        token=data.token,
        new_password=data.new_password,
    )

    # Execute handler
    result = await handler.handle(command, request)

    # Handle result
    match result:
        case Success(value=_):
            return PasswordResetCreateResponse()
        case Failure(error=error):
            # Map error to ApplicationErrorCode
            error_mapping = {
                "token_not_found": ApplicationErrorCode.NOT_FOUND,
                "token_expired": ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
                "token_already_used": ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
                "user_not_found": ApplicationErrorCode.NOT_FOUND,
            }
            error_code = error_mapping.get(
                error, ApplicationErrorCode.COMMAND_VALIDATION_FAILED
            )

            app_error = ApplicationError(
                code=error_code,
                message=_get_user_friendly_error(error),
            )
            return ErrorResponseBuilder.from_application_error(
                error=app_error,
                request=request,
                trace_id=get_trace_id() or "",
            )


def _get_user_friendly_error(error: str) -> str:
    """Get user-friendly error message.

    Args:
        error: Internal error code.

    Returns:
        User-friendly error message.
    """
    messages = {
        "token_not_found": "Password reset link is invalid or has already been used.",
        "token_expired": "Password reset link has expired. Please request a new one.",
        "token_already_used": "This password reset link has already been used.",
        "user_not_found": "User account not found.",
    }
    return messages.get(error, "Password reset failed. Please try again.")
