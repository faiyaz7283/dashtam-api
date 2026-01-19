"""Background jobs monitor for querying job queue status.

This module provides JobsMonitor, which connects to the dashtam-jobs Redis
instance to query queue length, job status, and health. It enables the API
to monitor the background jobs service without code dependencies.

Architecture:
- Uses redis.asyncio for async Redis operations
- Follows fail-open pattern for resilience
- Returns Result types for error handling
- No dependency on dashtam-jobs code (shared config via environment)
"""

import json
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success
from src.infrastructure.enums import InfrastructureErrorCode
from src.infrastructure.errors import InfrastructureError


@dataclass(frozen=True, kw_only=True)
class JobsHealthStatus:
    """Health status of the background jobs service.

    Attributes:
        healthy: Whether the jobs Redis is reachable.
        queue_length: Number of jobs waiting in the queue.
        redis_connected: Whether Redis connection is active.
        error: Error message if unhealthy.
    """

    healthy: bool
    queue_length: int
    redis_connected: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:  # noqa: PLW3201
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict representation of health status.
        """
        return {
            "healthy": self.healthy,
            "queue_length": self.queue_length,
            "redis_connected": self.redis_connected,
            "error": self.error,
        }


class JobsMonitor:
    """Monitor for background jobs service.

    Connects to the jobs Redis instance to query queue status and health.
    This class does not depend on dashtam-jobs code - it only queries Redis
    directly using the same queue name configured in dashtam-jobs.

    Attributes:
        _redis: Async Redis client instance.
        _queue_name: Name of the jobs queue in Redis.
    """

    def __init__(self, redis_client: Redis, queue_name: str = "dashtam:jobs") -> None:
        """Initialize jobs monitor.

        Args:
            redis_client: Async Redis client instance.
            queue_name: Name of the jobs queue (must match dashtam-jobs config).
        """
        self._redis = redis_client
        self._queue_name = queue_name

    async def check_health(self) -> Result[JobsHealthStatus, InfrastructureError]:
        """Check health of the background jobs service.

        Verifies Redis connectivity and returns queue status.

        Returns:
            Result with JobsHealthStatus on success, or InfrastructureError.
        """
        try:
            # Ping Redis to verify connectivity
            await self._redis.ping()  # type: ignore[misc]

            # Get queue length
            queue_length = await self._redis.llen(self._queue_name)  # type: ignore[misc]

            return Success(
                value=JobsHealthStatus(
                    healthy=True,
                    queue_length=queue_length,
                    redis_connected=True,
                )
            )
        except RedisError as e:
            return Success(
                value=JobsHealthStatus(
                    healthy=False,
                    queue_length=0,
                    redis_connected=False,
                    error=f"Redis connection failed: {e}",
                )
            )
        except Exception as e:
            return Failure(
                error=InfrastructureError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.UNEXPECTED_ERROR,
                    message="Unexpected error checking jobs health",
                    details={"error": str(e), "type": type(e).__name__},
                )
            )

    async def get_queue_length(self) -> Result[int, InfrastructureError]:
        """Get the number of jobs waiting in the queue.

        Returns:
            Result with queue length on success, or InfrastructureError.
        """
        try:
            length = await self._redis.llen(self._queue_name)  # type: ignore[misc]
            return Success(value=length)
        except RedisError as e:
            return Failure(
                error=InfrastructureError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CONNECTION_ERROR,
                    message="Failed to get jobs queue length",
                    details={"error": str(e), "queue_name": self._queue_name},
                )
            )

    async def get_job_result(
        self, task_id: str
    ) -> Result[dict[str, Any] | None, InfrastructureError]:
        """Get the result of a completed job by task ID.

        TaskIQ stores results with keys like 'taskiq:result:{task_id}'.

        Args:
            task_id: The unique identifier of the task.

        Returns:
            Result with job result dict if found, None if not found,
            or InfrastructureError.
        """
        try:
            # TaskIQ result backend key format
            result_key = f"taskiq:result:{task_id}"
            raw_result = await self._redis.get(result_key)

            if raw_result is None:
                return Success(value=None)

            result = (
                raw_result.decode("utf-8")
                if isinstance(raw_result, bytes)
                else raw_result
            )
            return Success(value=json.loads(result))
        except RedisError as e:
            return Failure(
                error=InfrastructureError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CONNECTION_ERROR,
                    message="Failed to get job result",
                    details={"error": str(e), "task_id": task_id},
                )
            )
        except Exception as e:
            return Failure(
                error=InfrastructureError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.UNEXPECTED_ERROR,
                    message="Unexpected error getting job result",
                    details={
                        "error": str(e),
                        "task_id": task_id,
                        "type": type(e).__name__,
                    },
                )
            )
