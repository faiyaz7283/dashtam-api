"""Metrics audit backend - optional observability integration.

Emits metrics for session events. App provides metrics client.
Useful for Prometheus, StatsD, DataDog, etc.
"""

from typing import Any, Dict, Protocol

from ..models.base import SessionBase
from .base import SessionAuditBackend


class MetricsClient(Protocol):
    """Abstract metrics client interface.

    App can provide ANY metrics client implementing this protocol:
    - Prometheus (via prometheus-client)
    - StatsD (via statsd)
    - DataDog (via datadog)
    - Custom metrics implementation

    Example (Prometheus):
        ```python
        from prometheus_client import Counter

        session_events = Counter(
            'session_events_total',
            'Total session events',
            ['event_type']
        )

        class PrometheusMetrics:
            def increment(self, metric: str, tags: Dict[str, str]):
                session_events.labels(**tags).inc()
        ```

    Example (StatsD):
        ```python
        from statsd import StatsClient

        class StatsDMetrics:
            def __init__(self):
                self.client = StatsClient('localhost', 8125)

            def increment(self, metric: str, tags: Dict[str, str]):
                self.client.incr(metric, tags=tags)
        ```
    """

    def increment(self, metric: str, tags: Dict[str, str]) -> None:
        """Increment a counter metric.

        Args:
            metric: Metric name
            tags: Metric tags/labels
        """
        ...


class MetricsAuditBackend(SessionAuditBackend):
    """Metrics-based audit backend.

    Emits metrics for observability instead of logging.
    App provides metrics client.

    Design Pattern:
        - Metrics-agnostic (Prometheus, StatsD, DataDog, etc.)
        - App provides metrics client
        - Useful for dashboards and alerting
        - Complements other audit backends

    Example (Prometheus):
        ```python
        metrics_client = PrometheusMetrics()  # App's implementation
        audit = MetricsAuditBackend(metrics=metrics_client)
        ```

    Note:
        Often used alongside DatabaseAuditBackend or LoggerAuditBackend.
        Metrics provide aggregated view; logs provide details.
    """

    def __init__(self, metrics: MetricsClient):
        """Initialize with app's metrics client.

        Args:
            metrics: Any client implementing MetricsClient protocol
        """
        self.metrics = metrics

    async def log_session_created(
        self, session: SessionBase, context: Dict[str, Any]
    ) -> None:
        """Emit session_created metric.

        Args:
            session: Newly created session
            context: Additional context
        """
        self.metrics.increment(
            "session_events_total",
            tags={
                "event_type": "created",
                "user_id": session.user_id,
                "device_type": self._extract_device_type(session.device_info),
            },
        )

    async def log_session_revoked(
        self, session_id: str, reason: str, context: Dict[str, Any]
    ) -> None:
        """Emit session_revoked metric.

        Args:
            session_id: Revoked session ID
            reason: Revocation reason
            context: Who revoked it, from where
        """
        self.metrics.increment(
            "session_events_total",
            tags={
                "event_type": "revoked",
                "reason": reason,
            },
        )

    async def log_session_accessed(
        self, session_id: str, context: Dict[str, Any]
    ) -> None:
        """Emit session_accessed metric.

        Args:
            session_id: Accessed session ID
            context: Access metadata
        """
        self.metrics.increment(
            "session_events_total",
            tags={
                "event_type": "accessed",
            },
        )

    async def log_suspicious_activity(
        self, session_id: str, event: str, context: Dict[str, Any]
    ) -> None:
        """Emit suspicious_activity metric.

        Args:
            session_id: Session involved
            event: Suspicious event type
            context: Event details
        """
        self.metrics.increment(
            "session_suspicious_events_total",
            tags={
                "event_type": event,
            },
        )

    def _extract_device_type(self, device_info: str | None) -> str:
        """Extract device type from device_info string.

        Args:
            device_info: Device/browser information

        Returns:
            Device type (mobile, desktop, tablet, unknown)
        """
        if not device_info:
            return "unknown"

        device_lower = device_info.lower()
        if any(x in device_lower for x in ["mobile", "android", "iphone"]):
            return "mobile"
        elif "tablet" in device_lower or "ipad" in device_lower:
            return "tablet"
        else:
            return "desktop"
