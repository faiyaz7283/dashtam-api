"""Unit tests for event bus container registry completeness.

This module tests that ALL domain events have at least one handler registered
in the container. This is a safety net to prevent drift between defined events
and registered handlers.

Pattern:
    Uses reflection to discover all DomainEvent subclasses and verifies each
    has at least one handler registered via the container's get_event_bus().

Reference:
    - F6.15: Event Handler Wiring Completion
    - docs/architecture/domain-events-architecture.md
"""

import pytest

from src.core.container.events import get_event_bus
from src.domain.events import DomainEvent


class TestEventRegistryCompleteness:
    """Test that all domain events are registered with handlers."""

    def test_all_events_have_handlers(self) -> None:
        """Verify every DomainEvent subclass has at least one handler registered.

        This test ensures completeness of event handler wiring in the container.
        If this test fails, it means a new event was added but not wired in
        src/core/container/events.py.

        Safety Net:
            Prevents production bugs where events are emitted but not handled,
            causing silent failures in audit/logging.

        Exclusions:
            Operational events deferred to v1.1.0+ (documented in F6.15):
            - RateLimitCheck events (3): Low priority, operational only
            - Session events (8): Lightweight telemetry, no audit requirement
        """
        # Get event bus with all handlers registered
        event_bus = get_event_bus()

        # Get all DomainEvent subclasses using reflection
        all_event_classes = _get_all_event_subclasses()

        # Verify we found events (sanity check)
        assert len(all_event_classes) > 0, "No domain events found - reflection failed"

        # Deferred operational events (documented in F6.15 Phase 1 inventory)
        # These are LOW priority and intentionally excluded from v1.0
        deferred_events = {
            # Rate Limiting operational events (3 events)
            "RateLimitCheckAttempted",
            "RateLimitCheckAllowed",
            "RateLimitCheckDenied",
            # Session operational events (8 events)
            "SessionCreatedEvent",
            "SessionRevokedEvent",
            "SessionActivityUpdatedEvent",
            "SessionLimitExceededEvent",
            "SessionProviderAccessEvent",
            "SuspiciousSessionActivityEvent",
            "SessionEvictedEvent",
            "AllSessionsRevokedEvent",
        }

        # Track events without handlers (excluding deferred)
        missing_handlers: list[str] = []

        # Check each event class has at least one handler
        for event_class in all_event_classes:
            event_name = event_class.__name__

            # Skip deferred operational events
            if event_name in deferred_events:
                continue

            handlers = event_bus._handlers.get(event_class, [])
            if not handlers:
                missing_handlers.append(event_name)

        # Assert all non-deferred events have handlers
        if missing_handlers:
            error_msg = (
                f"Found {len(missing_handlers)} event(s) without handlers:\n"
                + "\n".join(f"  - {name}" for name in sorted(missing_handlers))
                + "\n\nAdd handler registration in src/core/container/events.py"
            )
            pytest.fail(error_msg)

    def test_registry_count_matches_documentation(self) -> None:
        """Verify total subscription count matches container docstring.

        The container docstring claims 100 total subscriptions. This test
        verifies that count is accurate.

        Note:
            This is a documentation consistency check. Update docstring if
            subscription count changes.
        """
        event_bus = get_event_bus()

        # Count total subscriptions (sum of all handlers across all events)
        total_subscriptions = sum(
            len(handlers) for handlers in event_bus._handlers.values()
        )

        # As of F6.15 completion, we have 100 total subscriptions
        expected_subscriptions = 100

        assert total_subscriptions == expected_subscriptions, (
            f"Subscription count mismatch: expected {expected_subscriptions}, "
            f"got {total_subscriptions}. Update container docstring if count changed."
        )

    def test_critical_events_have_audit_and_logging(self) -> None:
        """Verify critical security events have both audit AND logging handlers.

        Critical events (3-state ATTEMPT → OUTCOME pattern) MUST have both
        logging and audit handlers for compliance (PCI-DSS, SOC 2).

        Security Compliance:
            PCI-DSS 10.2: All authentication attempts must be logged AND audited
            SOC 2 CC6.1: Security events require audit trail
        """
        event_bus = get_event_bus()

        # Critical security events (3-state pattern)
        critical_event_names = [
            # Authentication
            "UserRegistrationAttempted",
            "UserRegistrationSucceeded",
            "UserRegistrationFailed",
            "UserLoginAttempted",
            "UserLoginSucceeded",
            "UserLoginFailed",
            # Token Rotation (Security)
            "GlobalTokenRotationAttempted",
            "GlobalTokenRotationSucceeded",
            "GlobalTokenRotationFailed",
            "UserTokenRotationAttempted",
            "UserTokenRotationSucceeded",
            "UserTokenRotationFailed",
            # Authorization
            "RoleAssignmentAttempted",
            "RoleAssignmentSucceeded",
            "RoleAssignmentFailed",
            "RoleRevocationAttempted",
            "RoleRevocationSucceeded",
            "RoleRevocationFailed",
            # Provider
            "ProviderConnectionAttempted",
            "ProviderConnectionSucceeded",
            "ProviderConnectionFailed",
            "ProviderDisconnectionAttempted",
            "ProviderDisconnectionSucceeded",
            "ProviderDisconnectionFailed",
        ]

        # Get all event classes
        all_event_classes = {cls.__name__: cls for cls in _get_all_event_subclasses()}

        # Verify each critical event has both audit and logging
        for event_name in critical_event_names:
            event_class = all_event_classes.get(event_name)
            assert event_class is not None, f"Critical event {event_name} not found"

            handlers = event_bus._handlers.get(event_class, [])

            # Extract handler class names from bound methods
            # Handlers are bound methods, so we need handler.__self__.__class__.__name__
            handler_types = [
                handler.__self__.__class__.__name__
                if hasattr(handler, "__self__")
                else type(handler).__name__
                for handler in handlers
            ]

            # Must have at least 2 handlers (logging + audit)
            assert len(handlers) >= 2, (
                f"{event_name} only has {len(handlers)} handler(s). "
                f"Critical events require both logging AND audit handlers."
            )

            # Check for both handler types
            has_logging = any("Logging" in name for name in handler_types)
            has_audit = any("Audit" in name for name in handler_types)

            assert has_logging and has_audit, (
                f"{event_name} missing required handlers. "
                f"Has: {handler_types}. "
                f"Required: LoggingEventHandler + AuditEventHandler"
            )


def _get_all_event_subclasses() -> set[type[DomainEvent]]:
    """Get all DomainEvent subclasses using reflection.

    Returns:
        Set of all concrete event classes (excludes DomainEvent base).

    Implementation:
        Uses __subclasses__() recursively to find all descendants of DomainEvent.
    """

    def get_subclasses(cls: type) -> set[type]:
        """Recursively get all subclasses of a class."""
        subclasses = set(cls.__subclasses__())
        for subclass in list(subclasses):
            subclasses.update(get_subclasses(subclass))
        return subclasses

    # Get all DomainEvent subclasses (excluding base)
    all_subclasses = get_subclasses(DomainEvent)

    # Filter to only concrete event classes (exclude base DomainEvent)
    concrete_events = {
        cls
        for cls in all_subclasses
        if cls is not DomainEvent and cls.__name__ != "DomainEvent"
    }

    return concrete_events
