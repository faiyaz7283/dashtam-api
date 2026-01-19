"""Background jobs status request/response schemas.

Pydantic models for admin API background jobs monitoring endpoints.
Admin-only operations for monitoring the dashtam-jobs background worker service.

RESTful Endpoints (admin-only):
    GET    /api/v1/admin/jobs    - Get jobs service status
"""

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Jobs Status Response
# =============================================================================


class JobsStatusResponse(BaseModel):
    """Response schema for jobs service status.

    GET /api/v1/admin/jobs
    Returns: 200 OK

    Admin-only. Returns detailed status of the background jobs service.
    """

    healthy: bool = Field(
        ...,
        description="Whether the jobs service is healthy (Redis connected and responsive)",
    )
    queue_length: int = Field(
        ...,
        description="Number of jobs currently waiting in the queue",
    )
    redis_connected: bool = Field(
        ...,
        description="Whether the jobs Redis instance is connected",
    )
    error: str | None = Field(
        None,
        description="Error message if unhealthy (null when healthy)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "healthy": True,
                "queue_length": 3,
                "redis_connected": True,
                "error": None,
            }
        }
    )
