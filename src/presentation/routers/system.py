"""System router for non-versioned application endpoints.

Provides external-facing system endpoints that are not part of the
versioned API contract, such as root, health, and configuration.

These endpoints are intentionally lightweight and side-effect free to
support health checks and basic diagnostics.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.core.config import settings


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
