"""Token rotation admin router.

Admin-only endpoints for token breach rotation.

Endpoints:
    POST /api/v1/admin/security/rotations      - Global token rotation
    POST /api/v1/admin/users/{user_id}/rotations - Per-user token rotation
    GET  /api/v1/admin/security/config         - Get security configuration
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.commands.handlers.trigger_global_rotation_handler import (
    TriggerGlobalTokenRotationHandler,
)
from src.application.commands.handlers.trigger_user_rotation_handler import (
    TriggerUserTokenRotationHandler,
)
from src.application.commands.rotation_commands import (
    TriggerGlobalTokenRotation,
    TriggerUserTokenRotation,
)
from src.core.config import settings
from src.core.container import (
    get_db_session,
    get_trigger_global_rotation_handler,
    get_trigger_user_rotation_handler,
)
from src.core.result import Failure, Success
from src.infrastructure.persistence.repositories import SecurityConfigRepository
from src.presentation.api.middleware.trace_middleware import get_trace_id
from src.schemas.auth_schemas import AuthErrorResponse
from src.schemas.rotation_schemas import (
    GlobalRotationRequest,
    GlobalRotationResponse,
    SecurityConfigResponse,
    UserRotationRequest,
    UserRotationResponse,
)

router = APIRouter(tags=["Token Rotation"])


# =============================================================================
# Global Token Rotation
# =============================================================================


@router.post(
    "/security/rotations",
    status_code=status.HTTP_201_CREATED,
    response_model=GlobalRotationResponse,
    responses={
        201: {
            "description": "Global rotation triggered",
            "model": GlobalRotationResponse,
        },
        401: {"description": "Not authenticated", "model": AuthErrorResponse},
        403: {"description": "Not authorized (admin only)", "model": AuthErrorResponse},
        500: {"description": "Rotation failed", "model": AuthErrorResponse},
    },
    summary="Trigger global token rotation",
    description=(
        "Admin-only. Increments global minimum token version, invalidating "
        "all existing refresh tokens with lower versions. Use for security "
        "incidents or breach response."
    ),
)
async def create_global_rotation(
    request: Request,
    data: GlobalRotationRequest,
    handler: TriggerGlobalTokenRotationHandler = Depends(
        get_trigger_global_rotation_handler
    ),
) -> GlobalRotationResponse | JSONResponse:
    """Trigger global token rotation.

    POST /api/v1/admin/security/rotations → 201 Created

    Increments global_min_token_version. All refresh tokens with
    token_version < new minimum will fail validation.

    Grace period allows gradual transition (tokens rejected after grace expires).

    Args:
        request: FastAPI request object.
        data: Rotation request with reason.
        handler: Global rotation handler (injected).

    Returns:
        GlobalRotationResponse on success (201 Created).
        JSONResponse with error on failure.
    """
    # TODO: Add admin authentication check
    # For now, endpoint is unprotected (will add admin auth in F1.4)
    triggered_by = "admin"  # Will be replaced with actual admin user ID

    command = TriggerGlobalTokenRotation(
        reason=data.reason,
        triggered_by=triggered_by,
    )

    result = await handler.handle(command)

    match result:
        case Success(value=rotation_result):
            return GlobalRotationResponse(
                previous_version=rotation_result.previous_version,
                new_version=rotation_result.new_version,
                grace_period_seconds=rotation_result.grace_period_seconds,
            )
        case Failure(error=error):
            return _error_response(
                request=request,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_type="rotation_failed",
                title="Rotation Failed",
                detail=f"Failed to trigger global rotation: {error}",
            )


# =============================================================================
# Per-User Token Rotation
# =============================================================================


@router.post(
    "/users/{user_id}/rotations",
    status_code=status.HTTP_201_CREATED,
    response_model=UserRotationResponse,
    responses={
        201: {
            "description": "User rotation triggered",
            "model": UserRotationResponse,
        },
        401: {"description": "Not authenticated", "model": AuthErrorResponse},
        403: {"description": "Not authorized (admin only)", "model": AuthErrorResponse},
        404: {"description": "User not found", "model": AuthErrorResponse},
        500: {"description": "Rotation failed", "model": AuthErrorResponse},
    },
    summary="Trigger per-user token rotation",
    description=(
        "Admin-only. Increments user's minimum token version, invalidating "
        "only that user's existing refresh tokens. Use for suspicious "
        "activity or account compromise."
    ),
)
async def create_user_rotation(
    request: Request,
    data: UserRotationRequest,
    user_id: UUID = Path(..., description="User ID to rotate tokens for"),
    handler: TriggerUserTokenRotationHandler = Depends(
        get_trigger_user_rotation_handler
    ),
) -> UserRotationResponse | JSONResponse:
    """Trigger per-user token rotation.

    POST /api/v1/admin/users/{user_id}/rotations → 201 Created

    Increments user.min_token_version. Only that user's refresh tokens
    with token_version < new minimum will fail validation.

    Args:
        request: FastAPI request object.
        data: Rotation request with reason.
        user_id: Target user's ID.
        handler: User rotation handler (injected).

    Returns:
        UserRotationResponse on success (201 Created).
        JSONResponse with error on failure (404/500).
    """
    # TODO: Add admin authentication check
    triggered_by = "admin"  # Will be replaced with actual admin user ID

    command = TriggerUserTokenRotation(
        user_id=user_id,
        reason=data.reason,
        triggered_by=triggered_by,
    )

    result = await handler.handle(command)

    match result:
        case Success(value=rotation_result):
            return UserRotationResponse(
                user_id=rotation_result.user_id,
                previous_version=rotation_result.previous_version,
                new_version=rotation_result.new_version,
            )
        case Failure(error=error):
            if error == "user_not_found":
                return _error_response(
                    request=request,
                    status_code=status.HTTP_404_NOT_FOUND,
                    error_type="user_not_found",
                    title="User Not Found",
                    detail=f"User with ID {user_id} not found",
                )
            return _error_response(
                request=request,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_type="rotation_failed",
                title="Rotation Failed",
                detail=f"Failed to trigger user rotation: {error}",
            )


# =============================================================================
# Security Configuration
# =============================================================================


@router.get(
    "/security/config",
    status_code=status.HTTP_200_OK,
    response_model=SecurityConfigResponse,
    responses={
        200: {
            "description": "Security configuration",
            "model": SecurityConfigResponse,
        },
        401: {"description": "Not authenticated", "model": AuthErrorResponse},
        403: {"description": "Not authorized (admin only)", "model": AuthErrorResponse},
    },
    summary="Get security configuration",
    description="Admin-only. Retrieve current security configuration including token version.",
)
async def get_security_config(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> SecurityConfigResponse | JSONResponse:
    """Get security configuration.

    GET /api/v1/admin/security/config → 200 OK

    Returns current global token version and grace period settings.

    Args:
        request: FastAPI request object.
        session: Database session (injected).

    Returns:
        SecurityConfigResponse with current configuration.
    """
    # TODO: Add admin authentication check
    repo = SecurityConfigRepository(session=session)
    config = await repo.get_or_create_default()

    return SecurityConfigResponse(
        global_min_token_version=config.global_min_token_version,
        grace_period_seconds=config.grace_period_seconds,
        last_rotation_at=(
            config.last_rotation_at.isoformat() if config.last_rotation_at else None
        ),
        last_rotation_reason=config.last_rotation_reason,
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _error_response(
    request: Request,
    status_code: int,
    error_type: str,
    title: str,
    detail: str,
) -> JSONResponse:
    """Create standardized error response.

    Args:
        request: FastAPI request object.
        status_code: HTTP status code.
        error_type: Error type identifier.
        title: Error title.
        detail: Error detail message.

    Returns:
        JSONResponse with RFC 7807 error format.
    """
    trace_id = get_trace_id()
    return JSONResponse(
        status_code=status_code,
        content=AuthErrorResponse(
            type=f"{settings.api_base_url}/errors/{error_type}",
            title=title,
            status=status_code,
            detail=detail,
            instance=str(request.url.path),
        ).model_dump(),
        headers={"X-Trace-ID": trace_id} if trace_id else None,
    )
