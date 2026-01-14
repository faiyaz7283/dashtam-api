"""Tokens resource handlers.

Handler functions for token management endpoints.
Routes are registered via ROUTE_REGISTRY in routes/registry.py.

Handlers:
    create_tokens - Create new tokens (refresh)
"""

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from src.application.commands.auth_commands import RefreshAccessToken
from src.application.commands.handlers.refresh_access_token_handler import (
    RefreshAccessTokenHandler,
)
from src.application.errors import ApplicationError, ApplicationErrorCode
from src.core.container.handler_factory import handler_factory
from src.core.result import Failure, Success
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id
from src.presentation.routers.api.v1.errors import ErrorResponseBuilder
from src.schemas.auth_schemas import (
    TokenCreateRequest,
    TokenCreateResponse,
)


async def create_tokens(
    request: Request,
    data: TokenCreateRequest,
    handler: RefreshAccessTokenHandler = Depends(
        handler_factory(RefreshAccessTokenHandler)
    ),
) -> TokenCreateResponse | JSONResponse:
    """Create new tokens (refresh).

    POST /api/v1/tokens → 201 Created

    Exchanges a valid refresh token for new access and refresh tokens.
    Implements token rotation: old refresh token is invalidated.

    Args:
        request: FastAPI request object.
        data: Token creation request (refresh_token).
        handler: Refresh token handler (injected).

    Returns:
        TokenCreateResponse on success (201 Created).
        JSONResponse with error on failure (400/401).
    """
    # Create command from request data
    command = RefreshAccessToken(
        refresh_token=data.refresh_token,
    )

    # Execute handler
    result = await handler.handle(command, request)

    # Handle result
    match result:
        case Success(value=refresh_response):
            return TokenCreateResponse(
                access_token=refresh_response.access_token,
                refresh_token=refresh_response.refresh_token,
                token_type=refresh_response.token_type,
                expires_in=refresh_response.expires_in,
            )
        case Failure(error=error):
            # Map error to ApplicationErrorCode
            error_mapping = {
                "token_invalid": ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
                "token_expired": ApplicationErrorCode.UNAUTHORIZED,
                "token_revoked": ApplicationErrorCode.UNAUTHORIZED,
                "user_not_found": ApplicationErrorCode.UNAUTHORIZED,
                "user_inactive": ApplicationErrorCode.UNAUTHORIZED,
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
        "token_invalid": "The provided refresh token is invalid.",
        "token_expired": "Your session has expired. Please log in again.",
        "token_revoked": "Your session has been revoked. Please log in again.",
        "user_not_found": "User account not found.",
        "user_inactive": "Your account has been deactivated.",
    }
    return messages.get(error, "Token refresh failed. Please log in again.")
