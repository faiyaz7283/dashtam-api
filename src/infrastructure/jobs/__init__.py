"""Background jobs infrastructure package.

This package provides integration with the dashtam-jobs background worker service.
It enables the API to monitor job queue status and health without directly
depending on the jobs service code.

Architecture:
- JobsMonitor: Queries jobs Redis for queue status and health
- Uses same Redis instance as dashtam-jobs (configurable via JOBS_REDIS_URL)
- No code dependency on dashtam-jobs (shared config via environment)

Usage:
    from src.core.container import get_jobs_monitor

    monitor = get_jobs_monitor()
    health = await monitor.check_health()
"""

from src.infrastructure.jobs.monitor import JobsMonitor

__all__ = ["JobsMonitor"]
