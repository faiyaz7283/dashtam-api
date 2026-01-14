"""Email verifications resource handlers.

Handler functions for email verification endpoints.
Routes are registered via ROUTE_REGISTRY in routes/registry.py.

Handlers:
    create_email_verification - Create email verification (verify email)
"""

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from src.application.commands.auth_commands import VerifyEmail
from src.application.commands.handlers.verify_email_handler import VerifyEmailHandler
from src.application.errors import ApplicationError, ApplicationErrorCode
from src.core.container.handler_factory import handler_factory
from src.core.result import Failure, Success
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id
from src.presentation.routers.api.v1.errors import ErrorResponseBuilder
from src.schemas.auth_schemas import (
    EmailVerificationCreateRequest,
    EmailVerificationCreateResponse,
)


async def create_email_verification(
    request: Request,
    data: EmailVerificationCreateRequest,
    handler: VerifyEmailHandler = Depends(handler_factory(VerifyEmailHandler)),
) -> EmailVerificationCreateResponse | JSONResponse:
    """Create email verification (verify email).

    POST /api/v1/email-verifications → 201 Created

    Verifies user's email address using the token sent during registration.
    After verification, user can create a session (login).

    Args:
        request: FastAPI request object.
        data: Email verification request (token).
        handler: Verify email handler (injected).

    Returns:
        EmailVerificationCreateResponse on success (201 Created).
        JSONResponse with error on failure (400/404).
    """
    # Create command from request data
    command = VerifyEmail(
        token=data.token,
    )

    # Execute handler
    result = await handler.handle(command, request)

    # Handle result
    match result:
        case Success(value=_):
            return EmailVerificationCreateResponse()
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
        "token_not_found": "Verification link is invalid or has already been used.",
        "token_expired": "Verification link has expired. Please request a new one.",
        "token_already_used": "This verification link has already been used.",
        "user_not_found": "User account not found.",
    }
    return messages.get(error, "Email verification failed. Please try again.")
