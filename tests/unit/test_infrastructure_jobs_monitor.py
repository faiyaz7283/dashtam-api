"""Unit tests for JobsMonitor.

Tests cover:
- check_health() - Redis reachable, unreachable, unexpected errors
- get_queue_length() - success, Redis error
- get_job_result() - found, not found, Redis error, unexpected error

Architecture:
- Pure unit tests (no external dependencies)
- Uses AsyncMock for Redis client
- Uses Result pattern (Success/Failure)
- Tests infrastructure error types
"""

import json
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import RedisError

from src.core.result import Failure, Success
from src.infrastructure.jobs.monitor import JobsHealthStatus, JobsMonitor


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.llen = AsyncMock(return_value=5)
    redis.get = AsyncMock(return_value=None)
    return redis


@pytest.fixture
def monitor(mock_redis):
    """Create JobsMonitor with mocked Redis client."""
    return JobsMonitor(redis_client=mock_redis, queue_name="test:jobs")


# =============================================================================
# Test: JobsHealthStatus
# =============================================================================


class TestJobsHealthStatus:
    """Test JobsHealthStatus dataclass."""

    def test_healthy_status_to_dict(self):
        """Healthy status should serialize correctly."""
        status = JobsHealthStatus(
            healthy=True,
            queue_length=10,
            redis_connected=True,
        )

        result = status.to_dict()

        assert result["healthy"] is True
        assert result["queue_length"] == 10
        assert result["redis_connected"] is True
        assert result["error"] is None

    def test_unhealthy_status_to_dict(self):
        """Unhealthy status should include error message."""
        status = JobsHealthStatus(
            healthy=False,
            queue_length=0,
            redis_connected=False,
            error="Connection refused",
        )

        result = status.to_dict()

        assert result["healthy"] is False
        assert result["redis_connected"] is False
        assert result["error"] == "Connection refused"

    def test_status_is_immutable(self):
        """JobsHealthStatus should be frozen (immutable)."""
        status = JobsHealthStatus(
            healthy=True,
            queue_length=5,
            redis_connected=True,
        )

        with pytest.raises(AttributeError):
            status.healthy = False  # type: ignore[misc]


# =============================================================================
# Test: check_health()
# =============================================================================


class TestJobsMonitorCheckHealth:
    """Test check_health method."""

    @pytest.mark.asyncio
    async def test_returns_healthy_when_redis_reachable(
        self, monitor, mock_redis
    ) -> None:
        """Should return healthy status when Redis is reachable."""
        mock_redis.llen.return_value = 3

        result = await monitor.check_health()

        assert isinstance(result, Success)
        status = result.value
        assert status.healthy is True
        assert status.queue_length == 3
        assert status.redis_connected is True
        assert status.error is None

    @pytest.mark.asyncio
    async def test_pings_redis_to_verify_connectivity(
        self, monitor, mock_redis
    ) -> None:
        """Should ping Redis to verify connectivity."""
        await monitor.check_health()

        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_queries_queue_length(self, monitor, mock_redis) -> None:
        """Should query queue length using configured queue name."""
        await monitor.check_health()

        mock_redis.llen.assert_called_once_with("test:jobs")

    @pytest.mark.asyncio
    async def test_returns_unhealthy_when_redis_fails(
        self, monitor, mock_redis
    ) -> None:
        """Should return unhealthy status when Redis connection fails."""
        mock_redis.ping.side_effect = RedisError("Connection refused")

        result = await monitor.check_health()

        # RedisError returns Success with unhealthy status (fail-open pattern)
        assert isinstance(result, Success)
        status = result.value
        assert status.healthy is False
        assert status.queue_length == 0
        assert status.redis_connected is False
        assert "Connection refused" in str(status.error)

    @pytest.mark.asyncio
    async def test_returns_unhealthy_when_llen_fails(self, monitor, mock_redis) -> None:
        """Should return unhealthy status when llen fails."""
        mock_redis.llen.side_effect = RedisError("Timeout")

        result = await monitor.check_health()

        assert isinstance(result, Success)
        status = result.value
        assert status.healthy is False
        assert "Timeout" in str(status.error)

    @pytest.mark.asyncio
    async def test_returns_failure_on_unexpected_error(
        self, monitor, mock_redis
    ) -> None:
        """Should return Failure on unexpected (non-Redis) errors."""
        mock_redis.ping.side_effect = RuntimeError("Unexpected error")

        result = await monitor.check_health()

        assert isinstance(result, Failure)
        assert "Unexpected error" in result.error.message


# =============================================================================
# Test: get_queue_length()
# =============================================================================


class TestJobsMonitorGetQueueLength:
    """Test get_queue_length method."""

    @pytest.mark.asyncio
    async def test_returns_queue_length(self, monitor, mock_redis) -> None:
        """Should return queue length from Redis."""
        mock_redis.llen.return_value = 42

        result = await monitor.get_queue_length()

        assert isinstance(result, Success)
        assert result.value == 42

    @pytest.mark.asyncio
    async def test_uses_configured_queue_name(self, monitor, mock_redis) -> None:
        """Should use the configured queue name."""
        await monitor.get_queue_length()

        mock_redis.llen.assert_called_once_with("test:jobs")

    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_queue(self, monitor, mock_redis) -> None:
        """Should return 0 for empty queue."""
        mock_redis.llen.return_value = 0

        result = await monitor.get_queue_length()

        assert isinstance(result, Success)
        assert result.value == 0

    @pytest.mark.asyncio
    async def test_returns_failure_on_redis_error(self, monitor, mock_redis) -> None:
        """Should return Failure when Redis fails."""
        mock_redis.llen.side_effect = RedisError("Connection lost")

        result = await monitor.get_queue_length()

        assert isinstance(result, Failure)
        assert "Failed to get jobs queue length" in result.error.message
        assert result.error.details is not None
        assert "Connection lost" in result.error.details["error"]


# =============================================================================
# Test: get_job_result()
# =============================================================================


class TestJobsMonitorGetJobResult:
    """Test get_job_result method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_result_not_found(
        self, monitor, mock_redis
    ) -> None:
        """Should return None when job result doesn't exist."""
        mock_redis.get.return_value = None

        result = await monitor.get_job_result("task-123")

        assert isinstance(result, Success)
        assert result.value is None

    @pytest.mark.asyncio
    async def test_queries_correct_key_format(self, monitor, mock_redis) -> None:
        """Should query TaskIQ result key format."""
        await monitor.get_job_result("abc-123")

        mock_redis.get.assert_called_once_with("taskiq:result:abc-123")

    @pytest.mark.asyncio
    async def test_returns_parsed_json_result(self, monitor, mock_redis) -> None:
        """Should parse and return JSON result."""
        job_result = {"return_value": "success", "is_err": False}
        mock_redis.get.return_value = json.dumps(job_result).encode("utf-8")

        result = await monitor.get_job_result("task-456")

        assert isinstance(result, Success)
        assert result.value == job_result

    @pytest.mark.asyncio
    async def test_handles_string_result(self, monitor, mock_redis) -> None:
        """Should handle string result (not bytes)."""
        job_result = {"status": "completed"}
        mock_redis.get.return_value = json.dumps(job_result)

        result = await monitor.get_job_result("task-789")

        assert isinstance(result, Success)
        assert result.value == job_result

    @pytest.mark.asyncio
    async def test_returns_failure_on_redis_error(self, monitor, mock_redis) -> None:
        """Should return Failure when Redis fails."""
        mock_redis.get.side_effect = RedisError("Read timeout")

        result = await monitor.get_job_result("task-error")

        assert isinstance(result, Failure)
        assert "Failed to get job result" in result.error.message
        assert result.error.details is not None
        assert "task-error" in result.error.details["task_id"]

    @pytest.mark.asyncio
    async def test_returns_failure_on_invalid_json(self, monitor, mock_redis) -> None:
        """Should return Failure when result is invalid JSON."""
        mock_redis.get.return_value = b"not valid json"

        result = await monitor.get_job_result("task-bad-json")

        assert isinstance(result, Failure)
        assert "Unexpected error" in result.error.message

    @pytest.mark.asyncio
    async def test_returns_failure_on_unexpected_error(
        self, monitor, mock_redis
    ) -> None:
        """Should return Failure on unexpected errors."""
        mock_redis.get.side_effect = TypeError("Unexpected")

        result = await monitor.get_job_result("task-unexpected")

        assert isinstance(result, Failure)
        assert "Unexpected error" in result.error.message
        assert result.error.details is not None
        assert "TypeError" in result.error.details["type"]


# =============================================================================
# Test: Constructor
# =============================================================================


class TestJobsMonitorInit:
    """Test JobsMonitor initialization."""

    def test_uses_default_queue_name(self, mock_redis):
        """Should use default queue name if not specified."""
        monitor = JobsMonitor(redis_client=mock_redis)

        # Access private attribute for testing
        assert monitor._queue_name == "dashtam:jobs"

    def test_uses_custom_queue_name(self, mock_redis):
        """Should use custom queue name when specified."""
        monitor = JobsMonitor(redis_client=mock_redis, queue_name="custom:queue")

        assert monitor._queue_name == "custom:queue"
