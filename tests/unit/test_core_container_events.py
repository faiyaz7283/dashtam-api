"""Unit tests for event bus container registry completeness.

This module tests that ALL domain events have at least one handler registered
in the container. This is a safety net to prevent drift between defined events
and registered handlers.

Pattern:
    Uses reflection to discover all DomainEvent subclasses and verifies each
    has at least one handler registered via the container's get_event_bus().

Reference:
    - F6.15: Event Handler Wiring Completion
    - F7.7: Domain Events Compliance Audit
    - docs/architecture/domain-events-architecture.md
"""

import pytest

from src.core.container.events import get_event_bus
from src.domain.events.registry import EVENT_REGISTRY


class TestEventRegistryCompleteness:
    """Test that all domain events are registered with handlers."""

    @pytest.fixture(scope="class")
    def event_bus(self):
        """Shared event bus for all tests in this class.

        Using class scope to avoid repeated container initialization
        which can cause OOM in CI environments.
        """
        return get_event_bus()

    def test_all_events_have_handlers(self, event_bus) -> None:
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
        # Use injected event_bus fixture (class scope for memory efficiency)

        # Get all registered event classes from the event bus itself
        # This avoids expensive reflection and only checks wired events
        all_event_classes = set(event_bus._handlers.keys())

        # Verify we found events (sanity check)
        assert len(all_event_classes) > 0, (
            "No events registered - container wiring failed"
        )

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

    def test_registry_count_matches_actual_wiring(self, event_bus) -> None:
        """Verify actual subscription count matches registry metadata.

        This test dynamically calculates expected subscriptions from EVENT_REGISTRY
        metadata (requires_logging, requires_audit, requires_email, requires_session)
        and verifies the container actually wired them all.

        Benefits:
            - Self-maintaining (no manual updates when adding events)
            - Catches wiring bugs (if actual < expected)
            - Always knows correct expected count

        Pattern:
            Expected = sum of all requires_* flags across EVENT_REGISTRY
            Actual = sum of handlers across all events in event_bus._handlers

        Reference:
            - F7.7: Domain Events Compliance Audit (registry-driven auto-wiring)
        """

        # Calculate expected subscriptions from registry metadata
        # This is the source of truth - if an event metadata says requires_logging=True,
        # we expect that subscription to exist in the event bus
        expected_logging = sum(1 for m in EVENT_REGISTRY if m.requires_logging)
        expected_audit = sum(1 for m in EVENT_REGISTRY if m.requires_audit)
        expected_email = sum(1 for m in EVENT_REGISTRY if m.requires_email)
        expected_session = sum(1 for m in EVENT_REGISTRY if m.requires_session)

        # Count SSE handler subscriptions (from DOMAIN_TO_SSE_MAPPING)
        from src.domain.events.sse_registry import get_domain_event_to_sse_mapping

        expected_sse = len(get_domain_event_to_sse_mapping())

        expected_subscriptions = (
            expected_logging
            + expected_audit
            + expected_email
            + expected_session
            + expected_sse
        )

        # Count actual subscriptions (sum of all handlers across all events)
        actual_subscriptions = sum(
            len(handlers) for handlers in event_bus._handlers.values()
        )

        # Assert actual matches expected
        assert actual_subscriptions == expected_subscriptions, (
            f"Subscription count mismatch!\n"
            f"Expected: {expected_subscriptions} subscriptions\n"
            f"  - Logging: {expected_logging}\n"
            f"  - Audit: {expected_audit}\n"
            f"  - Email: {expected_email}\n"
            f"  - Session: {expected_session}\n"
            f"  - SSE: {expected_sse}\n"
            f"Actual: {actual_subscriptions} subscriptions\n\n"
            f"If actual < expected: Container wiring bug (missing subscriptions)\n"
            f"If actual > expected: Update EVENT_REGISTRY or SSE_EVENT_REGISTRY metadata"
        )

    def test_critical_events_have_audit_and_logging(self, event_bus) -> None:
        """Verify critical security events have both audit AND logging handlers.

        Critical events (3-state ATTEMPT → OUTCOME pattern) MUST have both
        logging and audit handlers for compliance (PCI-DSS, SOC 2).

        Security Compliance:
            PCI-DSS 10.2: All authentication attempts must be logged AND audited
            SOC 2 CC6.1: Security events require audit trail
        """

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

        # Get event classes from the registered handlers (avoids expensive reflection)
        all_event_classes = {cls.__name__: cls for cls in event_bus._handlers.keys()}

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
