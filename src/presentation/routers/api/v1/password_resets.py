"""Password resets resource router.

RESTful endpoints for password reset management.

Endpoints:
    POST /api/v1/password-reset-tokens - Create password reset token (request reset)
    POST /api/v1/password-resets       - Create password reset (execute reset)
"""

from fastapi import APIRouter, Depends, Request, status
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
from src.core.container import (
    get_confirm_password_reset_handler,
    get_request_password_reset_handler,
)
from src.core.result import Failure, Success
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id
from src.schemas.auth_schemas import (
    AuthErrorResponse,
    PasswordResetCreateRequest,
    PasswordResetCreateResponse,
    PasswordResetTokenCreateRequest,
    PasswordResetTokenCreateResponse,
)

# Router for password reset tokens
password_reset_tokens_router = APIRouter(
    prefix="/password-reset-tokens",
    tags=["Password Reset Tokens"],
)

# Router for password resets
password_resets_router = APIRouter(
    prefix="/password-resets",
    tags=["Password Resets"],
)


@password_reset_tokens_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=PasswordResetTokenCreateResponse,
    responses={
        201: {
            "description": "Password reset email sent (if account exists)",
            "model": PasswordResetTokenCreateResponse,
        },
    },
    summary="Create password reset token",
    description="Request a password reset. Always returns success to prevent user enumeration.",
)
async def create_password_reset_token(
    request: Request,
    data: PasswordResetTokenCreateRequest,
    handler: RequestPasswordResetHandler = Depends(get_request_password_reset_handler),
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
    await handler.handle(command)

    # Always return success to prevent user enumeration
    return PasswordResetTokenCreateResponse()


@password_resets_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=PasswordResetCreateResponse,
    responses={
        201: {
            "description": "Password reset successfully",
            "model": PasswordResetCreateResponse,
        },
        400: {"description": "Invalid or expired token", "model": AuthErrorResponse},
        404: {"description": "Token not found", "model": AuthErrorResponse},
    },
    summary="Create password reset",
    description="Reset password using token from email. Revokes all sessions.",
)
async def create_password_reset(
    request: Request,
    data: PasswordResetCreateRequest,
    handler: ConfirmPasswordResetHandler = Depends(get_confirm_password_reset_handler),
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
    result = await handler.handle(command)

    # Handle result
    match result:
        case Success(value=_):
            return PasswordResetCreateResponse()
        case Failure(error=error):
            # Map error to appropriate status code
            error_mapping = {
                "token_not_found": (status.HTTP_404_NOT_FOUND, "Token Not Found"),
                "token_expired": (status.HTTP_400_BAD_REQUEST, "Token Expired"),
                "token_already_used": (
                    status.HTTP_400_BAD_REQUEST,
                    "Token Already Used",
                ),
                "user_not_found": (status.HTTP_404_NOT_FOUND, "User Not Found"),
            }
            status_code, title = error_mapping.get(
                error, (status.HTTP_400_BAD_REQUEST, "Password Reset Failed")
            )

            trace_id = get_trace_id()
            return JSONResponse(
                status_code=status_code,
                content=AuthErrorResponse(
                    type=f"https://api.dashtam.com/errors/{error}",
                    title=title,
                    status=status_code,
                    detail=_get_user_friendly_error(error),
                    instance=str(request.url.path),
                ).model_dump(),
                headers={"X-Trace-ID": trace_id} if trace_id else None,
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
