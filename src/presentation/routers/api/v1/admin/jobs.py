"""Background jobs admin handlers.

Handler functions for admin background jobs monitoring endpoint.
Routes are registered via ROUTE_REGISTRY in routes/registry.py.

Handlers:
    get_jobs_status - Get jobs service status

All handlers require:
    - JWT authentication (valid access token)
    - Admin role (Casbin RBAC check)
"""

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from src.core.container import get_jobs_monitor
from src.core.result import Failure
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
from src.schemas.jobs_schemas import JobsStatusResponse

if TYPE_CHECKING:
    from src.infrastructure.jobs.monitor import JobsMonitor


# =============================================================================
# Jobs Status
# =============================================================================


async def get_jobs_status(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    _admin_check: None = Depends(require_casbin_role("admin")),
    monitor: "JobsMonitor" = Depends(get_jobs_monitor),
) -> JobsStatusResponse | JSONResponse:
    """Get background jobs service status.

    GET /api/v1/admin/jobs → 200 OK

    Returns detailed status of the dashtam-jobs background worker service,
    including queue length, Redis connectivity, and health status.

    Requires admin role (Casbin RBAC).

    Args:
        request: FastAPI request object.
        current_user: Authenticated admin user (from JWT).
        _admin_check: Admin role verification (Casbin).
        monitor: JobsMonitor instance for querying job queue status.

    Returns:
        JobsStatusResponse on success (200 OK).
        JSONResponse with error on failure.
    """
    result = await monitor.check_health()

    if isinstance(result, Failure):
        error = ApplicationError(
            code=ApplicationErrorCode.COMMAND_EXECUTION_FAILED,
            message="Failed to check jobs status",
        )
        return ErrorResponseBuilder.from_application_error(
            error=error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    status = result.value
    return JobsStatusResponse(
        healthy=status.healthy,
        queue_length=status.queue_length,
        redis_connected=status.redis_connected,
        error=status.error,
    )
