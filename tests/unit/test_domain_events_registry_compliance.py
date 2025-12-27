"""Registry Compliance Tests - FAIL FAST on drift.

These tests verify the Event Registry remains synchronized with implementations.
Tests FAIL if:
- Event registered but handler method missing
- Event registered but AuditAction enum missing
- Registry statistics don't match expectations

This ensures the registry remains the single source of truth and catches drift
immediately during development.

Reference:
    - src/domain/events/registry.py
    - F7.7 Phase 1.5: Event Registry enforcement mechanism
"""

import pytest

from src.domain.enums.audit_action import AuditAction
from src.domain.events.registry import (
    EVENT_REGISTRY,
    EventCategory,
    WorkflowPhase,
    get_all_events,
    get_events_requiring_handler,
    get_expected_audit_actions,
    get_statistics,
    get_workflow_events,
)
from src.infrastructure.events.handlers.audit_event_handler import AuditEventHandler
from src.infrastructure.events.handlers.email_event_handler import EmailEventHandler
from src.infrastructure.events.handlers.logging_event_handler import LoggingEventHandler
from src.infrastructure.events.handlers.session_event_handler import SessionEventHandler


class TestRegistryCompleteness:
    """Verify registry is complete and accurate."""

    def test_registry_not_empty(self):
        """Registry must contain events."""
        assert len(EVENT_REGISTRY) > 0, "Registry is empty!"

    def test_all_events_have_metadata(self):
        """Every event must have complete metadata."""
        for meta in EVENT_REGISTRY:
            assert meta.event_class is not None, "Event class missing"
            assert meta.category is not None, "Category missing"
            assert meta.workflow_name, "Workflow name empty"
            assert meta.phase is not None, "Phase missing"
            assert meta.audit_action_name, "Audit action name empty"

    def test_registry_statistics_accurate(self):
        """Registry statistics must match actual counts."""
        stats = get_statistics()

        assert stats["total_events"] == len(EVENT_REGISTRY)
        assert stats["total_workflows"] > 0

        # Verify category counts
        by_category = stats["by_category"]
        assert "authentication" in by_category
        assert "authorization" in by_category
        assert "provider" in by_category

        # Verify phase counts
        by_phase = stats["by_phase"]
        assert "attempted" in by_phase
        assert "succeeded" in by_phase
        assert "failed" in by_phase


class TestHandlerMethodCompliance:
    """CRITICAL: Verify all registered events have handler methods.

    These tests FAIL if handler methods are missing.
    Fix: Add the missing handler methods to the handler classes.
    """

    def test_all_events_have_logging_handler_methods(self):
        """CRITICAL: Every event requiring logging MUST have handler method.

        This test FAILS if:
        - Event registered with requires_logging=True
        - But LoggingEventHandler missing handle_* method

        Fix: Add missing handler methods to LoggingEventHandler.
        """
        logging_handler = LoggingEventHandler(logger=None)  # type: ignore
        missing = []

        events_requiring_logging = get_events_requiring_handler("logging")

        for event_class in events_requiring_logging:
            # Find metadata for this event
            meta = next(m for m in EVENT_REGISTRY if m.event_class == event_class)
            method_name = f"handle_{meta.workflow_name}_{meta.phase.value}"

            if not hasattr(logging_handler, method_name):
                missing.append(f"LoggingEventHandler.{method_name} for {event_class.__name__}")

        assert not missing, (
            f"\n❌ REGISTRY COMPLIANCE FAILURE: LoggingEventHandler methods missing\n\n"
            f"Missing handler methods:\n"
            f"{chr(10).join(f'  - {m}' for m in missing)}\n\n"
            f"Fix: Add these methods to src/infrastructure/events/handlers/logging_event_handler.py\n"
            f"Pattern:\n"
            f"  async def handle_<workflow>_<phase>(self, event: EventClass) -> None:\n"
            f"      self.logger.info('Event occurred', ...)"
        )

    def test_all_events_have_audit_handler_methods(self):
        """CRITICAL: Every event requiring audit MUST have handler method.

        This test FAILS if:
        - Event registered with requires_audit=True
        - But AuditEventHandler missing handle_* method

        Fix: Add missing handler methods to AuditEventHandler.
        """
        # Cannot instantiate without dependencies, check class attributes instead
        audit_handler_methods = {
            name for name in dir(AuditEventHandler)
            if name.startswith("handle_") and not name.startswith("_")
        }

        missing = []
        events_requiring_audit = get_events_requiring_handler("audit")

        for event_class in events_requiring_audit:
            # Find metadata for this event
            meta = next(m for m in EVENT_REGISTRY if m.event_class == event_class)
            method_name = f"handle_{meta.workflow_name}_{meta.phase.value}"

            if method_name not in audit_handler_methods:
                missing.append(f"AuditEventHandler.{method_name} for {event_class.__name__}")

        assert not missing, (
            f"\n❌ REGISTRY COMPLIANCE FAILURE: AuditEventHandler methods missing\n\n"
            f"Missing handler methods:\n"
            f"{chr(10).join(f'  - {m}' for m in missing)}\n\n"
            f"Fix: Add these methods to src/infrastructure/events/handlers/audit_event_handler.py\n"
            f"Pattern:\n"
            f"  async def handle_<workflow>_<phase>(self, event: EventClass) -> None:\n"
            f"      await self._create_audit_record(action=AuditAction.XXX, ...)"
        )

    def test_all_events_have_email_handler_methods_if_required(self):
        """Events requiring email MUST have handler method.

        This test FAILS if:
        - Event registered with requires_email=True
        - But EmailEventHandler missing handle_* method

        Fix: Add missing handler methods to EmailEventHandler.
        """
        email_handler_methods = {
            name for name in dir(EmailEventHandler)
            if name.startswith("handle_") and not name.startswith("_")
        }

        missing = []
        events_requiring_email = get_events_requiring_handler("email")

        for event_class in events_requiring_email:
            # Find metadata for this event
            meta = next(m for m in EVENT_REGISTRY if m.event_class == event_class)
            method_name = f"handle_{meta.workflow_name}_{meta.phase.value}"

            if method_name not in email_handler_methods:
                missing.append(f"EmailEventHandler.{method_name} for {event_class.__name__}")

        assert not missing, (
            f"\n❌ REGISTRY COMPLIANCE FAILURE: EmailEventHandler methods missing\n\n"
            f"Missing handler methods:\n"
            f"{chr(10).join(f'  - {m}' for m in missing)}\n\n"
            f"Fix: Add these methods to src/infrastructure/events/handlers/email_event_handler.py"
        )

    def test_all_events_have_session_handler_methods_if_required(self):
        """Events requiring session handling MUST have handler method.

        This test FAILS if:
        - Event registered with requires_session=True
        - But SessionEventHandler missing handle_* method

        Fix: Add missing handler methods to SessionEventHandler.
        """
        session_handler_methods = {
            name for name in dir(SessionEventHandler)
            if name.startswith("handle_") and not name.startswith("_")
        }

        missing = []
        events_requiring_session = get_events_requiring_handler("session")

        for event_class in events_requiring_session:
            # Find metadata for this event
            meta = next(m for m in EVENT_REGISTRY if m.event_class == event_class)
            method_name = f"handle_{meta.workflow_name}_{meta.phase.value}"

            if method_name not in session_handler_methods:
                missing.append(f"SessionEventHandler.{method_name} for {event_class.__name__}")

        assert not missing, (
            f"\n❌ REGISTRY COMPLIANCE FAILURE: SessionEventHandler methods missing\n\n"
            f"Missing handler methods:\n"
            f"{chr(10).join(f'  - {m}' for m in missing)}\n\n"
            f"Fix: Add these methods to src/infrastructure/events/handlers/session_event_handler.py"
        )


class TestAuditActionCompliance:
    """CRITICAL: Verify all registered events have AuditAction enums.

    These tests FAIL if AuditAction enums are missing.
    Fix: Add the missing enums to src/domain/enums/audit_action.py
    """

    def test_all_events_have_audit_actions(self):
        """CRITICAL: Every event requiring audit MUST have AuditAction enum.

        This test FAILS if:
        - Event registered with requires_audit=True
        - But AuditAction enum doesn't exist

        Fix: Add missing AuditAction enums.
        """
        expected_actions = get_expected_audit_actions()
        all_audit_actions = {action.name for action in AuditAction}

        missing = []
        for event_class, action_name in expected_actions.items():
            if action_name not in all_audit_actions:
                missing.append(f"{event_class.__name__} → AuditAction.{action_name}")

        assert not missing, (
            f"\n❌ REGISTRY COMPLIANCE FAILURE: AuditAction enums missing\n\n"
            f"Missing AuditAction enums:\n"
            f"{chr(10).join(f'  - {m}' for m in missing)}\n\n"
            f"Fix: Add these enums to src/domain/enums/audit_action.py\n"
            f"Pattern:\n"
            f"  ACTION_NAME = 'action_name'  # snake_case string value"
        )

    def test_audit_action_naming_convention(self):
        """Verify AuditAction enums follow naming convention."""
        expected_actions = get_expected_audit_actions()

        for event_class, action_name in expected_actions.items():
            # Should be UPPER_SNAKE_CASE
            assert action_name.isupper() or "_" in action_name, (
                f"AuditAction.{action_name} should be UPPER_SNAKE_CASE"
            )


class TestHandlerRequirements:
    """Verify handler requirements are logically consistent."""

    def test_all_events_have_logging(self):
        """All events should have logging (default True)."""
        events_without_logging = [
            meta.event_class.__name__
            for meta in EVENT_REGISTRY
            if not meta.requires_logging
        ]

        # Operational events may not require logging (lightweight telemetry)
        operational_events = {
            meta.event_class.__name__
            for meta in EVENT_REGISTRY
            if meta.phase == WorkflowPhase.OPERATIONAL
        }

        unexpected = set(events_without_logging) - operational_events
        assert not unexpected, (
            f"Non-operational events without logging: {unexpected}"
        )

    def test_email_only_for_succeeded(self):
        """Email notifications should only be sent for SUCCEEDED events."""
        invalid = [
            (meta.event_class.__name__, meta.phase.value)
            for meta in EVENT_REGISTRY
            if meta.requires_email and meta.phase not in (
                WorkflowPhase.SUCCEEDED, WorkflowPhase.OPERATIONAL
            )
        ]

        assert not invalid, (
            f"Email should only be sent for SUCCEEDED or OPERATIONAL events: {invalid}"
        )

    def test_session_only_for_succeeded(self):
        """Session handling should only be for SUCCEEDED events."""
        invalid = [
            (meta.event_class.__name__, meta.phase.value)
            for meta in EVENT_REGISTRY
            if meta.requires_session and meta.phase != WorkflowPhase.SUCCEEDED
        ]

        assert not invalid, (
            f"Session handling should only be for SUCCEEDED events: {invalid}"
        )


class TestHelperFunctions:
    """Test registry helper functions."""

    def test_get_all_events(self):
        """get_all_events returns all event classes."""
        all_events = get_all_events()
        assert len(all_events) == len(EVENT_REGISTRY)
        assert all(event is not None for event in all_events)

    def test_get_events_requiring_handler(self):
        """get_events_requiring_handler returns correct events."""
        # Logging - should have most events
        logging_events = get_events_requiring_handler("logging")
        assert len(logging_events) > 0

        # Audit - should have most events
        audit_events = get_events_requiring_handler("audit")
        assert len(audit_events) > 0

        # Email - should have fewer (only SUCCEEDED)
        email_events = get_events_requiring_handler("email")
        assert len(email_events) > 0
        assert len(email_events) < len(logging_events)

        # Session - should have fewest
        session_events = get_events_requiring_handler("session")
        assert len(session_events) >= 0  # May be 0 or more
        assert len(session_events) < len(email_events)

    def test_get_events_requiring_handler_invalid_type(self):
        """get_events_requiring_handler raises on invalid type."""
        with pytest.raises(ValueError, match="Invalid handler_type"):
            get_events_requiring_handler("invalid")

    def test_get_workflow_events(self):
        """get_workflow_events returns all events for a workflow."""
        # User registration should have 3 events (attempted, succeeded, failed)
        registration_events = get_workflow_events("user_registration")
        assert len(registration_events) == 3
        assert WorkflowPhase.ATTEMPTED in registration_events
        assert WorkflowPhase.SUCCEEDED in registration_events
        assert WorkflowPhase.FAILED in registration_events

    def test_get_expected_audit_actions(self):
        """get_expected_audit_actions returns mapping."""
        audit_actions = get_expected_audit_actions()
        assert len(audit_actions) > 0
        assert all(isinstance(name, str) for name in audit_actions.values())

    def test_get_statistics(self):
        """get_statistics returns accurate counts."""
        stats = get_statistics()

        assert "total_events" in stats
        assert "by_category" in stats
        assert "by_phase" in stats
        assert "requiring_logging" in stats
        assert "requiring_audit" in stats
        assert "requiring_email" in stats
        assert "requiring_session" in stats
        assert "total_workflows" in stats

        # All counts should be non-negative
        for key, value in stats.items():
            if key not in ("by_category", "by_phase"):
                assert value >= 0, f"{key} should be >= 0"
