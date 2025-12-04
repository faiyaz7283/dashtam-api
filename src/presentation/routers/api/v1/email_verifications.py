"""Email verifications resource router.

RESTful endpoints for email verification management.

Endpoints:
    POST /api/v1/email-verifications - Create email verification (verify email)
"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from src.application.commands.auth_commands import VerifyEmail
from src.application.commands.handlers.verify_email_handler import VerifyEmailHandler
from src.core.container import get_verify_email_handler
from src.core.result import Failure, Success
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id
from src.schemas.auth_schemas import (
    AuthErrorResponse,
    EmailVerificationCreateRequest,
    EmailVerificationCreateResponse,
)

router = APIRouter(prefix="/email-verifications", tags=["Email Verifications"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=EmailVerificationCreateResponse,
    responses={
        201: {
            "description": "Email verified successfully",
            "model": EmailVerificationCreateResponse,
        },
        400: {"description": "Invalid or expired token", "model": AuthErrorResponse},
        404: {"description": "Token not found", "model": AuthErrorResponse},
    },
    summary="Create email verification",
    description="Verify user's email address using verification token from email.",
)
async def create_email_verification(
    request: Request,
    data: EmailVerificationCreateRequest,
    handler: VerifyEmailHandler = Depends(get_verify_email_handler),
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
    result = await handler.handle(command)

    # Handle result
    match result:
        case Success(value=_):
            return EmailVerificationCreateResponse()
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
                error, (status.HTTP_400_BAD_REQUEST, "Verification Failed")
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
        "token_not_found": "Verification link is invalid or has already been used.",
        "token_expired": "Verification link has expired. Please request a new one.",
        "token_already_used": "This verification link has already been used.",
        "user_not_found": "User account not found.",
    }
    return messages.get(error, "Email verification failed. Please try again.")
