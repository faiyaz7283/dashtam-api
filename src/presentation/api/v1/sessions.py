"""Sessions resource router.

RESTful endpoints for session management.

Endpoints:
    POST   /api/v1/sessions         - Create session (login)
    GET    /api/v1/sessions         - List user sessions
    GET    /api/v1/sessions/{id}    - Get session details
    DELETE /api/v1/sessions/{id}    - Revoke specific session
    DELETE /api/v1/sessions/current - Delete current session (logout)
    DELETE /api/v1/sessions         - Revoke all sessions (except current)
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Query, Request, status
from fastapi.responses import JSONResponse, Response

from src.application.commands.auth_commands import AuthenticateUser, LogoutUser
from src.application.commands.handlers.authenticate_user_handler import (
    AuthenticateUserHandler,
)
from src.application.commands.handlers.create_session_handler import (
    CreateSessionHandler,
)
from src.application.commands.handlers.generate_auth_tokens_handler import (
    GenerateAuthTokensHandler,
)
from src.application.commands.handlers.logout_user_handler import LogoutUserHandler
from src.application.commands.session_commands import CreateSession
from src.application.commands.token_commands import GenerateAuthTokens
from src.application.commands.handlers.revoke_all_sessions_handler import (
    RevokeAllSessionsHandler,
)
from src.application.commands.handlers.revoke_session_handler import (
    RevokeSessionHandler,
)
from src.application.commands.session_commands import (
    RevokeAllUserSessions,
    RevokeSession,
)
from src.application.queries.handlers.get_session_handler import GetSessionHandler
from src.application.queries.handlers.list_sessions_handler import ListSessionsHandler
from src.application.queries.session_queries import GetSession, ListUserSessions
from src.core.config import settings
from src.core.container import (
    get_authenticate_user_handler,
    get_create_session_handler,
    get_generate_auth_tokens_handler,
    get_get_session_handler,
    get_list_sessions_handler,
    get_logout_user_handler,
    get_revoke_all_sessions_handler,
    get_revoke_session_handler,
)
from src.core.result import Failure, Success
from src.presentation.api.middleware.trace_middleware import get_trace_id
from src.schemas.auth_schemas import (
    AuthErrorResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionDeleteRequest,
)
from src.schemas.session_schemas import (
    SessionListResponse,
    SessionResponse,
    SessionRevokeAllRequest,
    SessionRevokeAllResponse,
    SessionRevokeRequest,
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
    auth_handler: AuthenticateUserHandler = Depends(get_authenticate_user_handler),
    session_handler: CreateSessionHandler = Depends(get_create_session_handler),
    token_handler: GenerateAuthTokensHandler = Depends(
        get_generate_auth_tokens_handler
    ),
) -> SessionCreateResponse | JSONResponse:
    """Create a new session (login).

    POST /api/v1/sessions → 201 Created

    Orchestrates 3 handlers (CQRS pattern):
    1. AuthenticateUser - Verify credentials
    2. CreateSession - Create session with device/location
    3. GenerateAuthTokens - Generate JWT + refresh token

    Args:
        request: FastAPI request object.
        data: Session creation request (email, password).
        auth_handler: Authentication handler (injected).
        session_handler: Session creation handler (injected).
        token_handler: Token generation handler (injected).

    Returns:
        SessionCreateResponse on success (201 Created).
        JSONResponse with error on failure (400/401/403).
    """
    # Extract client info for session
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Step 1: Authenticate user credentials
    auth_command = AuthenticateUser(
        email=data.email,
        password=data.password,
    )
    auth_result = await auth_handler.handle(auth_command)

    match auth_result:
        case Failure(error=error):
            return _create_auth_error_response(request, error)
        case Success(value=authenticated_user):
            pass  # Continue to step 2

    # Step 2: Create session
    session_command = CreateSession(
        user_id=authenticated_user.user_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session_result = await session_handler.handle(session_command)

    match session_result:
        case Failure(error=error):
            return _create_auth_error_response(request, error)
        case Success(value=session_response):
            pass  # Continue to step 3

    # Step 3: Generate tokens
    token_command = GenerateAuthTokens(
        user_id=authenticated_user.user_id,
        email=authenticated_user.email,
        roles=authenticated_user.roles,
        session_id=session_response.session_id,
    )
    token_result = await token_handler.handle(token_command)

    match token_result:
        case Failure(error=error):
            return _create_auth_error_response(request, error)
        case Success(value=tokens):
            return SessionCreateResponse(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                token_type=tokens.token_type,
                expires_in=tokens.expires_in,
            )


def _create_auth_error_response(request: Request, error: str) -> JSONResponse:
    """Create error response for authentication failures.

    Args:
        request: FastAPI request object.
        error: Error code from handler.

    Returns:
        JSONResponse with appropriate status code and error message.
    """
    error_mapping = {
        "invalid_credentials": (
            status.HTTP_401_UNAUTHORIZED,
            "Invalid Credentials",
        ),
        "email_not_verified": (status.HTTP_403_FORBIDDEN, "Email Not Verified"),
        "account_locked": (status.HTTP_403_FORBIDDEN, "Account Locked"),
        "account_inactive": (status.HTTP_403_FORBIDDEN, "Account Inactive"),
        "user_not_found": (status.HTTP_401_UNAUTHORIZED, "Invalid Credentials"),
        "session_limit_exceeded": (status.HTTP_403_FORBIDDEN, "Session Limit Exceeded"),
    }
    status_code, title = error_mapping.get(
        error, (status.HTTP_400_BAD_REQUEST, "Authentication Failed")
    )

    trace_id = get_trace_id()
    return JSONResponse(
        status_code=status_code,
        content=AuthErrorResponse(
            type=f"{settings.api_base_url}/errors/{error}",
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
    response_model=None,
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
) -> Response | JSONResponse:
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
                type=f"{settings.api_base_url}/errors/unauthorized",
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
        result = token_service.validate_access_token(token)
        # Handle Result type - payload is inside Success
        from src.core.result import Success

        if isinstance(result, Success) and "sub" in result.value:
            return UUID(str(result.value["sub"]))
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


def _extract_session_id_from_token(authorization: str | None) -> UUID | None:
    """Extract session_id from JWT authorization header.

    Args:
        authorization: Authorization header value (e.g., "Bearer <token>").

    Returns:
        Session ID from token, or None if invalid/missing.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    try:
        from src.core.container import get_token_service

        token = authorization[7:]  # Remove "Bearer " prefix
        token_service = get_token_service()
        result = token_service.validate_access_token(token)
        # Handle Result type - payload is inside Success
        from src.core.result import Success

        if isinstance(result, Success) and "session_id" in result.value:
            return UUID(str(result.value["session_id"]))
    except Exception:
        pass

    return None


# =============================================================================
# Session Management Endpoints (F1.3)
# =============================================================================


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=SessionListResponse,
    responses={
        200: {"description": "List of user sessions", "model": SessionListResponse},
        401: {"description": "Not authenticated", "model": AuthErrorResponse},
    },
    summary="List sessions",
    description="Get all sessions for the current user.",
)
async def list_sessions(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    active_only: bool = Query(default=True, description="Only return active sessions"),
    handler: ListSessionsHandler = Depends(get_list_sessions_handler),
) -> SessionListResponse | JSONResponse:
    """List all sessions for the current user.

    GET /api/v1/sessions → 200 OK

    Args:
        request: FastAPI request object.
        authorization: JWT access token from Authorization header.
        active_only: Filter to active sessions only.
        handler: List sessions handler (injected).

    Returns:
        SessionListResponse with list of sessions.
        JSONResponse with error on failure (401).
    """
    # Extract user_id and session_id from token
    user_id = _extract_user_id_from_token(authorization)
    current_session_id = _extract_session_id_from_token(authorization)

    if user_id is None:
        return _unauthorized_response(request)

    # Create query
    query = ListUserSessions(
        user_id=user_id,
        active_only=active_only,
        current_session_id=current_session_id,
    )

    # Execute handler
    result = await handler.handle(query)

    # Handle result (queries always succeed)
    match result:
        case Success(value=list_result):
            return SessionListResponse(
                sessions=[
                    SessionResponse(
                        id=s.id,
                        device_info=s.device_info,
                        ip_address=s.ip_address,
                        location=s.location,
                        created_at=s.created_at,
                        last_activity_at=s.last_activity_at,
                        expires_at=s.expires_at,
                        is_current=s.is_current,
                        is_revoked=s.is_revoked,
                    )
                    for s in list_result.sessions
                ],
                total_count=list_result.total_count,
                active_count=list_result.active_count,
            )
        case _:
            return _unauthorized_response(request)


@router.get(
    "/{session_id}",
    status_code=status.HTTP_200_OK,
    response_model=SessionResponse,
    responses={
        200: {"description": "Session details", "model": SessionResponse},
        401: {"description": "Not authenticated", "model": AuthErrorResponse},
        404: {"description": "Session not found", "model": AuthErrorResponse},
    },
    summary="Get session",
    description="Get details of a specific session.",
)
async def get_session(
    request: Request,
    session_id: UUID = Path(..., description="Session ID"),
    authorization: Annotated[str | None, Header()] = None,
    handler: GetSessionHandler = Depends(get_get_session_handler),
) -> SessionResponse | JSONResponse:
    """Get details of a specific session.

    GET /api/v1/sessions/{id} → 200 OK

    Args:
        request: FastAPI request object.
        session_id: Session ID from URL path.
        authorization: JWT access token from Authorization header.
        handler: Get session handler (injected).

    Returns:
        SessionResponse with session details.
        JSONResponse with error on failure (401/404).
    """
    # Extract user_id and current session_id from token
    user_id = _extract_user_id_from_token(authorization)
    current_session_id = _extract_session_id_from_token(authorization)

    if user_id is None:
        return _unauthorized_response(request)

    # Create query
    query = GetSession(
        session_id=session_id,
        user_id=user_id,
    )

    # Execute handler
    result = await handler.handle(query)

    # Handle result
    match result:
        case Success(value=session_result):
            return SessionResponse(
                id=session_result.id,
                device_info=session_result.device_info,
                ip_address=session_result.ip_address,
                location=session_result.location,
                created_at=session_result.created_at,
                last_activity_at=session_result.last_activity_at,
                expires_at=session_result.expires_at,
                is_current=session_result.id == current_session_id,
                is_revoked=session_result.is_revoked,
            )
        case Failure(error=error):
            if error == "session_not_found" or error == "not_session_owner":
                return _not_found_response(request, "Session not found")
            return _unauthorized_response(request)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        204: {"description": "Session revoked successfully"},
        401: {"description": "Not authenticated", "model": AuthErrorResponse},
        404: {"description": "Session not found", "model": AuthErrorResponse},
    },
    summary="Revoke session",
    description="Revoke a specific session (logout that device).",
)
async def revoke_session(
    request: Request,
    session_id: UUID = Path(..., description="Session ID to revoke"),
    data: SessionRevokeRequest | None = None,
    authorization: Annotated[str | None, Header()] = None,
    handler: RevokeSessionHandler = Depends(get_revoke_session_handler),
) -> Response | JSONResponse:
    """Revoke a specific session.

    DELETE /api/v1/sessions/{id} → 204 No Content

    Args:
        request: FastAPI request object.
        session_id: Session ID from URL path.
        data: Optional request body with reason.
        authorization: JWT access token from Authorization header.
        handler: Revoke session handler (injected).

    Returns:
        204 No Content on success.
        JSONResponse with error on failure (401/404).
    """
    # Extract user_id from token
    user_id = _extract_user_id_from_token(authorization)

    if user_id is None:
        return _unauthorized_response(request)

    # Create command
    reason = data.reason if data else "manual"
    command = RevokeSession(
        session_id=session_id,
        user_id=user_id,
        reason=reason,
    )

    # Execute handler
    result = await handler.handle(command)

    # Handle result
    match result:
        case Success(value=_):
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        case Failure(error=error):
            if error == "session_not_found" or error == "not_session_owner":
                return _not_found_response(request, "Session not found")
            if error == "session_already_revoked":
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            return _unauthorized_response(request)


@router.delete(
    "",
    status_code=status.HTTP_200_OK,
    response_model=SessionRevokeAllResponse,
    responses={
        200: {"description": "Sessions revoked", "model": SessionRevokeAllResponse},
        401: {"description": "Not authenticated", "model": AuthErrorResponse},
    },
    summary="Revoke all sessions",
    description="Revoke all sessions except the current one (logout everywhere else).",
)
async def revoke_all_sessions(
    request: Request,
    data: SessionRevokeAllRequest | None = None,
    authorization: Annotated[str | None, Header()] = None,
    handler: RevokeAllSessionsHandler = Depends(get_revoke_all_sessions_handler),
) -> SessionRevokeAllResponse | JSONResponse:
    """Revoke all sessions except current.

    DELETE /api/v1/sessions → 200 OK

    Args:
        request: FastAPI request object.
        data: Optional request body with reason.
        authorization: JWT access token from Authorization header.
        handler: Revoke all sessions handler (injected).

    Returns:
        SessionRevokeAllResponse with count of revoked sessions.
        JSONResponse with error on failure (401).
    """
    # Extract user_id and session_id from token
    user_id = _extract_user_id_from_token(authorization)
    current_session_id = _extract_session_id_from_token(authorization)

    if user_id is None:
        return _unauthorized_response(request)

    # Create command
    reason = data.reason if data else "logout_all"
    command = RevokeAllUserSessions(
        user_id=user_id,
        reason=reason,
        except_session_id=current_session_id,
    )

    # Execute handler
    result = await handler.handle(command)

    # Handle result
    match result:
        case Success(value=revoked_count):
            return SessionRevokeAllResponse(
                revoked_count=revoked_count,
                message=f"{revoked_count} session(s) revoked successfully",
            )
        case _:
            return _unauthorized_response(request)


# =============================================================================
# Helper functions for error responses
# =============================================================================


def _unauthorized_response(request: Request) -> JSONResponse:
    """Create 401 Unauthorized response."""
    trace_id = get_trace_id()
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=AuthErrorResponse(
            type=f"{settings.api_base_url}/errors/unauthorized",
            title="Unauthorized",
            status=status.HTTP_401_UNAUTHORIZED,
            detail="Valid authorization token required",
            instance=str(request.url.path),
        ).model_dump(),
        headers={"X-Trace-ID": trace_id} if trace_id else None,
    )


def _not_found_response(request: Request, detail: str) -> JSONResponse:
    """Create 404 Not Found response."""
    trace_id = get_trace_id()
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=AuthErrorResponse(
            type=f"{settings.api_base_url}/errors/not_found",
            title="Not Found",
            status=status.HTTP_404_NOT_FOUND,
            detail=detail,
            instance=str(request.url.path),
        ).model_dump(),
        headers={"X-Trace-ID": trace_id} if trace_id else None,
    )
