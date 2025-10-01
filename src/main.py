"""Main FastAPI application for Dashtam.

This module creates and configures the main FastAPI application with
all routers, middleware, and event handlers.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from src.core.config import settings
from src.core.database import init_db, close_db
from src.api.v1 import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events.

    Handles startup and shutdown events for the application.
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Initialize database tables (development only)
    if settings.DEBUG:
        await init_db()
        logger.info("Database tables initialized")

    # Log available providers
    from src.providers import ProviderRegistry

    providers = ProviderRegistry.get_available_providers()
    logger.info(f"Available providers: {list(providers.keys())}")

    yield

    # Shutdown
    logger.info("Shutting down application")
    await close_db()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Unified financial dashboard aggregating multiple providers",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware for security
# Include Docker service names for internal communication
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
    if settings.DEBUG
    else ["localhost", "127.0.0.1", "app", "backend", "0.0.0.0"],
)

# Include API routers
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs" if settings.DEBUG else "disabled",
        "api": {
            "v1": settings.API_V1_PREFIX,
            "endpoints": {
                "providers": f"{settings.API_V1_PREFIX}/providers",
                "auth": f"{settings.API_V1_PREFIX}/auth",
                "health": f"{settings.API_V1_PREFIX}/health",
            },
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from src.core.database import check_db_connection

    db_healthy = await check_db_connection()

    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "disconnected",
        "version": settings.APP_VERSION,
    }


if __name__ == "__main__":
    import uvicorn

    # Run with SSL in development
    if settings.SSL_CERT_FILE and settings.SSL_KEY_FILE:
        uvicorn.run(
            app,
            host=settings.HOST,
            port=settings.PORT,
            ssl_certfile=settings.SSL_CERT_FILE,
            ssl_keyfile=settings.SSL_KEY_FILE,
            reload=settings.RELOAD,
        )
    else:
        uvicorn.run(app, host=settings.HOST, port=settings.PORT, reload=settings.RELOAD)
