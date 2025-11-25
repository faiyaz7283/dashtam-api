"""Sessions resource router.

RESTful endpoints for session management.

Endpoints:
    POST /api/v1/sessions         - Create session (login)
    DELETE /api/v1/sessions/current - Delete current session (logout)
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse, Response

from src.application.commands.auth_commands import LoginUser, LogoutUser
from src.application.commands.handlers.login_user_handler import LoginUserHandler
from src.application.commands.handlers.logout_user_handler import LogoutUserHandler
from src.core.container import get_login_user_handler, get_logout_user_handler
from src.core.result import Failure, Success
from src.presentation.api.middleware.trace_middleware import get_trace_id
from src.schemas.auth_schemas import (
    AuthErrorResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionDeleteRequest,
)

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionCreateResponse,
    responses={
        201: {
            "description": "Session created successfully",
            "model": SessionCreateResponse,
        },
        400: {"description": "Invalid credentials", "model": AuthErrorResponse},
        401: {"description": "Authentication failed", "model": AuthErrorResponse},
        403: {
            "description": "Account locked or not verified",
            "model": AuthErrorResponse,
        },
    },
    summary="Create session",
    description="Authenticate user and create a new session with tokens.",
)
async def create_session(
    request: Request,
    data: SessionCreateRequest,
    handler: LoginUserHandler = Depends(get_login_user_handler),
) -> SessionCreateResponse | JSONResponse:
    """Create a new session (login).

    POST /api/v1/sessions → 201 Created

    Authenticates user credentials and returns JWT access token
    and opaque refresh token.

    Args:
        request: FastAPI request object.
        data: Session creation request (email, password).
        handler: Login handler (injected).

    Returns:
        SessionCreateResponse on success (201 Created).
        JSONResponse with error on failure (400/401/403).
    """
    # Create command from request data
    command = LoginUser(
        email=data.email,
        password=data.password,
    )

    # Execute handler
    result = await handler.handle(command)

    # Handle result
    match result:
        case Success(login_response):
            return SessionCreateResponse(
                access_token=login_response.access_token,
                refresh_token=login_response.refresh_token,
                token_type=login_response.token_type,
                expires_in=login_response.expires_in,
            )
        case Failure(error):
            # Map error to appropriate status code
            error_mapping = {
                "invalid_credentials": (
                    status.HTTP_401_UNAUTHORIZED,
                    "Invalid Credentials",
                ),
                "email_not_verified": (status.HTTP_403_FORBIDDEN, "Email Not Verified"),
                "account_locked": (status.HTTP_403_FORBIDDEN, "Account Locked"),
                "account_inactive": (status.HTTP_403_FORBIDDEN, "Account Inactive"),
            }
            status_code, title = error_mapping.get(
                error, (status.HTTP_400_BAD_REQUEST, "Authentication Failed")
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


@router.delete(
    "/current",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Session deleted successfully"},
        401: {"description": "Not authenticated", "model": AuthErrorResponse},
    },
    summary="Delete current session",
    description="Logout by revoking the refresh token for current session.",
)
async def delete_current_session(
    request: Request,
    data: SessionDeleteRequest,
    authorization: Annotated[str | None, Header()] = None,
    handler: LogoutUserHandler = Depends(get_logout_user_handler),
):
    """Delete current session (logout).

    DELETE /api/v1/sessions/current → 204 No Content

    Revokes the refresh token to prevent new access tokens.
    The current access token remains valid until expiration (15 min).

    Args:
        request: FastAPI request object.
        data: Session delete request (refresh_token).
        authorization: JWT access token from Authorization header.
        handler: Logout handler (injected).

    Returns:
        204 No Content on success.
        JSONResponse with error on failure (401).
    """
    # Extract user_id from JWT token (if provided)
    user_id = _extract_user_id_from_token(authorization)

    if user_id is None:
        trace_id = get_trace_id()
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=AuthErrorResponse(
                type="https://api.dashtam.com/errors/unauthorized",
                title="Unauthorized",
                status=status.HTTP_401_UNAUTHORIZED,
                detail="Valid authorization token required",
                instance=str(request.url.path),
            ).model_dump(),
            headers={"X-Trace-ID": trace_id} if trace_id else None,
        )

    # Create command
    command = LogoutUser(
        user_id=user_id,
        refresh_token=data.refresh_token,
    )

    # Execute handler (always returns success for security)
    await handler.handle(command)

    # Return 204 No Content
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _extract_user_id_from_token(authorization: str | None) -> UUID | None:
    """Extract user_id from JWT authorization header.

    Args:
        authorization: Authorization header value (e.g., "Bearer <token>").

    Returns:
        User ID from token, or None if invalid/missing.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    try:
        from src.core.container import get_token_service

        token = authorization[7:]  # Remove "Bearer " prefix
        token_service = get_token_service()
        payload = token_service.verify_access_token(token)
        if payload and "sub" in payload:
            return UUID(payload["sub"])
    except Exception:
        pass

    return None


def _get_user_friendly_error(error: str) -> str:
    """Get user-friendly error message.

    Args:
        error: Internal error code.

    Returns:
        User-friendly error message.
    """
    messages = {
        "invalid_credentials": "Email or password is incorrect.",
        "email_not_verified": "Please verify your email address before logging in.",
        "account_locked": "Your account has been locked due to too many failed attempts.",
        "account_inactive": "Your account has been deactivated.",
    }
    return messages.get(error, "Authentication failed. Please try again.")
