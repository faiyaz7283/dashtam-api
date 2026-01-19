"""System router for non-versioned application endpoints.

Provides external-facing system endpoints that are not part of the
versioned API contract, such as root, health, and configuration.

These endpoints are intentionally lightweight and side-effect free to
support health checks and basic diagnostics.
"""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.container import get_jobs_monitor
from src.core.result import Failure

if TYPE_CHECKING:
    from src.infrastructure.jobs.monitor import JobsMonitor


system_router = APIRouter(tags=["System"])


@system_router.get("/")
async def root() -> dict[str, str]:
    """Root endpoint - basic health/status check.

    Returns:
        dict[str, str]: Welcome message with API status and version.
    """
    return {
        "message": "Dashtam API",
        "status": "operational",
        "version": settings.app_version,
    }


@system_router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint for monitoring and load balancers.

    Returns:
        dict[str, str]: Health status indicator.
    """
    return {"status": "healthy"}


@system_router.get("/health/jobs")
async def health_jobs(
    monitor: "JobsMonitor" = Depends(get_jobs_monitor),
) -> dict[str, str]:
    """Health check for background jobs service (load balancer use).

    Simple health check endpoint for load balancers and infrastructure monitoring.
    Returns only status without sensitive details like queue length or error messages.

    For detailed job status, use the authenticated admin endpoint:
    GET /api/v1/admin/jobs

    Args:
        monitor: JobsMonitor instance for querying job queue status.

    Returns:
        dict[str, str]: Simple status indicator (healthy/unhealthy).
    """
    result = await monitor.check_health()

    if isinstance(result, Failure) or not result.value.healthy:
        return {"status": "unhealthy"}

    return {"status": "healthy"}


@system_router.get("/config")
async def get_config() -> JSONResponse:
    """Configuration debug endpoint (development only).

    Returns configuration information for debugging purposes. In
    non-development environments this endpoint is disabled.

    Returns:
        JSONResponse: Configuration details (sanitized) or 403 in
            non-development environments.
    """
    if not settings.is_development:
        return JSONResponse(
            status_code=403,
            content={"detail": "Config endpoint only available in development"},
        )

    return JSONResponse(
        content={
            "environment": settings.environment.value,
            "debug": settings.debug,
            "api": {
                "name": settings.app_name,
                "version": settings.app_version,
                "base_url": settings.api_base_url,
                "v1_prefix": settings.api_v1_prefix,
            },
            "database": {
                "url": "<redacted>",  # Never expose credentials
                "echo": settings.db_echo,
            },
            "cache": {
                "url": "<redacted>",
            },
            "cors": {
                "origins": settings.cors_origins,
                "allow_credentials": settings.cors_allow_credentials,
            },
        }
    )
