"""Application event handlers for reactive aggregation.

This module contains event handlers that listen to domain events and perform
reactive aggregation - computing derived values and emitting new events.

These handlers use MANUAL WIRING (not registry-driven auto-wiring) because:
1. Custom method names (not handle_{workflow}_{phase})
2. Stateful coordination (queries repositories and caches)
3. Emits derived events (not just side effects)

See: docs/architecture/domain-events.md Section 5.2 for pattern documentation.
"""

from src.application.event_handlers.portfolio_event_handler import (
    PortfolioEventHandler,
)

__all__ = ["PortfolioEventHandler"]
