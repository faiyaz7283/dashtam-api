"""Token rotation admin handlers.

Handler functions for admin token breach rotation endpoints.
Routes are registered via ROUTE_REGISTRY in routes/registry.py.

Handlers:
    create_global_rotation - Global token rotation
    create_user_rotation   - Per-user token rotation
    get_security_config    - Get security configuration

All handlers require:
    - JWT authentication (valid access token)
    - Admin role (Casbin RBAC check)
"""

from uuid import UUID

from fastapi import Depends, Path, Request
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
from src.core.container import get_db_session
from src.core.container.handler_factory import handler_factory
from src.core.result import Failure, Success
from src.infrastructure.persistence.repositories import SecurityConfigRepository
from src.presentation.routers.api.middleware.auth_dependencies import (
    CurrentUser,
    get_current_user,
)
from src.application.errors import ApplicationError, ApplicationErrorCode
from src.presentation.routers.api.middleware.authorization_dependencies import (
    require_casbin_role,
)
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id
from src.presentation.routers.api.v1.errors import ErrorResponseBuilder
from src.schemas.rotation_schemas import (
    GlobalRotationRequest,
    GlobalRotationResponse,
    SecurityConfigResponse,
    UserRotationRequest,
    UserRotationResponse,
)


# ===========================================# =============================================================================
# Global Token Rotation
# =============================================================================


async def create_global_rotation(
    request: Request,
    data: GlobalRotationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    _admin_check: None = Depends(require_casbin_role("admin")),
    handler: TriggerGlobalTokenRotationHandler = Depends(
        handler_factory(TriggerGlobalTokenRotationHandler)
    ),
) -> GlobalRotationResponse | JSONResponse:
    """Trigger global token rotation.

    POST /api/v1/admin/security/rotations → 201 Created

    Increments global_min_token_version. All refresh tokens with
    token_version < new minimum will fail validation.

    Grace period allows gradual transition (tokens rejected after grace expires).

    Requires admin role (Casbin RBAC).

    Args:
        request: FastAPI request object.
        data: Rotation request with reason.
        current_user: Authenticated admin user (from JWT).
        _admin_check: Admin role verification (Casbin).
        handler: Global rotation handler (injected).

    Returns:
        GlobalRotationResponse on success (201 Created).
        JSONResponse with error on failure.
    """
    triggered_by = str(current_user.user_id)

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
                error_code=ApplicationErrorCode.COMMAND_EXECUTION_FAILED,
                message=f"Failed to trigger global rotation: {error}",
            )


# =============================================================================
# Per-User Token Rotation
# =============================================================================


async def create_user_rotation(
    request: Request,
    data: UserRotationRequest,
    user_id: UUID = Path(description="User ID to rotate tokens for"),
    current_user: CurrentUser = Depends(get_current_user),
    _admin_check: None = Depends(require_casbin_role("admin")),
    handler: TriggerUserTokenRotationHandler = Depends(
        handler_factory(TriggerUserTokenRotationHandler)
    ),
) -> UserRotationResponse | JSONResponse:
    """Trigger per-user token rotation.

    POST /api/v1/admin/users/{user_id}/rotations → 201 Created

    Increments user.min_token_version. Only that user's refresh tokens
    with token_version < new minimum will fail validation.

    Requires admin role (Casbin RBAC).

    Args:
        request: FastAPI request object.
        data: Rotation request with reason.
        user_id: Target user's ID.
        current_user: Authenticated admin user (from JWT).
        _admin_check: Admin role verification (Casbin).
        handler: User rotation handler (injected).

    Returns:
        UserRotationResponse on success (201 Created).
        JSONResponse with error on failure (404/500).
    """
    triggered_by = str(current_user.user_id)

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
                    error_code=ApplicationErrorCode.NOT_FOUND,
                    message=f"User with ID {user_id} not found",
                )
            return _error_response(
                request=request,
                error_code=ApplicationErrorCode.COMMAND_EXECUTION_FAILED,
                message=f"Failed to trigger user rotation: {error}",
            )


# =============================================================================
# Security Configuration
# =============================================================================


async def get_security_config(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    _admin_check: None = Depends(require_casbin_role("admin")),
    session: AsyncSession = Depends(get_db_session),
) -> SecurityConfigResponse | JSONResponse:
    """Get security configuration.

    GET /api/v1/admin/security/config → 200 OK

    Returns current global token version and grace period settings.

    Requires admin role (Casbin RBAC).

    Args:
        request: FastAPI request object.
        current_user: Authenticated admin user (from JWT).
        _admin_check: Admin role verification (Casbin).
        session: Database session (injected).

    Returns:
        SecurityConfigResponse with current configuration.
    """
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
    error_code: ApplicationErrorCode,
    message: str,
) -> JSONResponse:
    """Create standardized error response.

    Args:
        request: FastAPI request object.
        error_code: ApplicationErrorCode.
        message: Error message.

    Returns:
        JSONResponse with RFC 9457 error format.
    """
    app_error = ApplicationError(
        code=error_code,
        message=message,
    )
    return ErrorResponseBuilder.from_application_error(
        error=app_error,
        request=request,
        trace_id=get_trace_id() or "",
    )
