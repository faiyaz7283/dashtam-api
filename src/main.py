"""
Main FastAPI application entry point.

This module initializes the FastAPI application instance and configures
the basic application settings. Additional routers, middleware, and
configuration will be added as features are implemented.

Created as part of F0.2 (Docker & Environment Setup) to establish a
functional development environment with Traefik routing.
"""

from fastapi import FastAPI

# Initialize FastAPI application
app = FastAPI(
    title="Dashtam API",
    description="Secure financial data aggregation platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


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
