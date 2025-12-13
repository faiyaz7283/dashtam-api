"""Tokens resource router.

RESTful endpoints for token management.

Endpoints:
    POST /api/v1/tokens - Create new tokens (refresh)
"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from src.application.commands.auth_commands import RefreshAccessToken
from src.application.commands.handlers.refresh_access_token_handler import (
    RefreshAccessTokenHandler,
)
from src.core.container import get_refresh_token_handler
from src.core.result import Failure, Success
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id
from src.schemas.auth_schemas import (
    AuthErrorResponse,
    TokenCreateRequest,
    TokenCreateResponse,
)

router = APIRouter(prefix="/tokens", tags=["Tokens"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TokenCreateResponse,
    responses={
        201: {
            "description": "Tokens created successfully",
            "model": TokenCreateResponse,
        },
        400: {"description": "Invalid token", "model": AuthErrorResponse},
        401: {"description": "Token expired or revoked", "model": AuthErrorResponse},
    },
    summary="Create tokens",
    description="Refresh access token using refresh token. Implements token rotation.",
)
async def create_tokens(
    request: Request,
    data: TokenCreateRequest,
    handler: RefreshAccessTokenHandler = Depends(get_refresh_token_handler),
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
            # Map error to appropriate status code
            error_mapping = {
                "token_invalid": (status.HTTP_400_BAD_REQUEST, "Invalid Token"),
                "token_expired": (status.HTTP_401_UNAUTHORIZED, "Token Expired"),
                "token_revoked": (status.HTTP_401_UNAUTHORIZED, "Token Revoked"),
                "user_not_found": (status.HTTP_401_UNAUTHORIZED, "User Not Found"),
                "user_inactive": (status.HTTP_401_UNAUTHORIZED, "User Inactive"),
            }
            status_code, title = error_mapping.get(
                error, (status.HTTP_400_BAD_REQUEST, "Token Refresh Failed")
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
        "token_invalid": "The provided refresh token is invalid.",
        "token_expired": "Your session has expired. Please log in again.",
        "token_revoked": "Your session has been revoked. Please log in again.",
        "user_not_found": "User account not found.",
        "user_inactive": "Your account has been deactivated.",
    }
    return messages.get(error, "Token refresh failed. Please log in again.")
