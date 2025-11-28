"""
Main FastAPI application entry point.

This module initializes the FastAPI application instance and configures
the basic application settings. Additional routers, middleware, and
configuration will be added as features are implemented.

Created as part of F0.2 (Docker & Environment Setup) to establish a
functional development environment with Traefik routing.

Updated in F0.3 (Configuration Management) to use Pydantic Settings.
Updated in F1.1b (User Authorization) to add Casbin enforcer initialization.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.presentation.api.middleware.trace_middleware import TraceMiddleware
from src.presentation.api.v1 import v1_router
from src.presentation.api.v1.errors import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager.

    Handles startup and shutdown events:
    - Startup: Initialize Casbin enforcer, load policies
    - Shutdown: Cleanup resources (future)

    Args:
        app: FastAPI application instance.

    Yields:
        None during application lifetime.
    """
    # Startup: Initialize Casbin enforcer
    from src.core.container import init_enforcer

    await init_enforcer()

    yield

    # Shutdown: Cleanup (future: close connections, etc.)


# Initialize FastAPI application with settings and lifespan
app = FastAPI(
    title=settings.app_name,
    description="Secure financial data aggregation platform",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    debug=settings.debug,
    lifespan=lifespan,
)

# Wire trace middleware (request correlation)
app.add_middleware(TraceMiddleware)

# Register global exception handlers (RFC 7807 error responses)
register_exception_handlers(app)

# Include API v1 routers (RESTful resource-based endpoints)
app.include_router(v1_router)


@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint - basic health check.

    Returns:
        dict: Welcome message with API status.
    """
    return {
        "message": "Dashtam API",
        "status": "operational",
        "version": "0.1.0",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """
    Health check endpoint for monitoring and load balancers.

    Returns:
        dict: Health status indicator.
    """
    return {"status": "healthy"}


@app.get("/config")
async def get_config() -> JSONResponse:
    """
    Configuration debug endpoint (development only).

    Returns configuration information for debugging purposes.
    In production, this endpoint should be disabled or protected.

    Returns:
        JSONResponse: Configuration details (sanitized).
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
