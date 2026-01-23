"""Unit tests for SSE Security Notifications Mappings (Issue #258).

Tests cover:
- All 5 domain-to-SSE mappings for security events
- Payload extraction for each event type
- User ID extraction (including optional user_id for UserLoginFailed)
- Mapping registry integration

Note:
    The security.session.expiring event is NOT covered here as it requires
    a background job (not triggered by domain events). That is implemented
    in the dashtam-jobs project.

Reference:
    - src/domain/events/sse_registry.py
    - docs/architecture/sse-architecture.md Section 3.6
    - GitHub Issue #258
"""

from typing import cast
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.domain.events.auth_events import (
    UserLoginFailed,
    UserPasswordChangeSucceeded,
)
from src.domain.events.session_events import (
    SessionCreatedEvent,
    SessionRevokedEvent,
    SuspiciousSessionActivityEvent,
)
from src.domain.events.sse_event import SSEEventType
from src.domain.events.sse_registry import (
    DOMAIN_TO_SSE_MAPPING,
    get_domain_event_to_sse_mapping,
    get_registry_statistics,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def user_id() -> UUID:
    """Provide a test user ID."""
    return cast(UUID, uuid7())


@pytest.fixture
def session_id() -> UUID:
    """Provide a test session ID."""
    return cast(UUID, uuid7())


# =============================================================================
# Registry Tests
# =============================================================================


@pytest.mark.unit
class TestSecurityMappingsRegistry:
    """Test that security mappings are properly registered."""

    def test_all_security_events_have_mappings(self):
        """Verify all 5 security domain events have SSE mappings."""
        mapping = get_domain_event_to_sse_mapping()

        # Session events
        assert SessionCreatedEvent in mapping
        assert SessionRevokedEvent in mapping
        assert SuspiciousSessionActivityEvent in mapping

        # Auth events
        assert UserPasswordChangeSucceeded in mapping
        assert UserLoginFailed in mapping

    def test_registry_statistics_include_security_mappings(self):
        """Verify registry statistics reflect security mappings."""
        stats = get_registry_statistics()

        # Should have at least 21 mappings (9 data sync + 3 provider + 4 import + 5 security)
        total_mappings = cast(int, stats["total_mappings"])
        assert total_mappings >= 21

    def test_mapping_list_contains_security_entries(self):
        """Verify DOMAIN_TO_SSE_MAPPING has security entries."""
        security_types = {
            SSEEventType.SECURITY_SESSION_NEW,
            SSEEventType.SECURITY_SESSION_REVOKED,
            SSEEventType.SECURITY_SESSION_SUSPICIOUS,
            SSEEventType.SECURITY_PASSWORD_CHANGED,
            SSEEventType.SECURITY_LOGIN_FAILED,
        }

        mapped_types = {m.sse_event_type for m in DOMAIN_TO_SSE_MAPPING}
        assert security_types.issubset(mapped_types)


# =============================================================================
# SessionCreatedEvent Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestSessionCreatedMapping:
    """Test SessionCreatedEvent domain-to-SSE mapping."""

    def test_mapping_to_correct_sse_event_type(self):
        """Test SessionCreatedEvent maps to SECURITY_SESSION_NEW."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[SessionCreatedEvent]

        assert m.sse_event_type == SSEEventType.SECURITY_SESSION_NEW

    def test_payload_extraction(self, user_id, session_id):
        """Test payload is correctly extracted from SessionCreatedEvent."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[SessionCreatedEvent]

        event = SessionCreatedEvent(
            user_id=user_id,
            session_id=session_id,
            device_info="Chrome on macOS",
            ip_address="192.168.1.1",
            location="New York, US",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "session_id": str(session_id),
            "device_info": "Chrome on macOS",
            "ip_address": "192.168.1.1",
            "location": "New York, US",
        }

    def test_payload_extraction_with_none_fields(self, user_id, session_id):
        """Test payload extraction when optional fields are None."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[SessionCreatedEvent]

        event = SessionCreatedEvent(
            user_id=user_id,
            session_id=session_id,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "session_id": str(session_id),
            "device_info": None,
            "ip_address": None,
            "location": None,
        }

    def test_user_id_extraction(self, user_id, session_id):
        """Test user_id is correctly extracted from SessionCreatedEvent."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[SessionCreatedEvent]

        event = SessionCreatedEvent(
            user_id=user_id,
            session_id=session_id,
        )

        assert m.user_id_extractor(event) == user_id


# =============================================================================
# SessionRevokedEvent Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestSessionRevokedMapping:
    """Test SessionRevokedEvent domain-to-SSE mapping."""

    def test_mapping_to_correct_sse_event_type(self):
        """Test SessionRevokedEvent maps to SECURITY_SESSION_REVOKED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[SessionRevokedEvent]

        assert m.sse_event_type == SSEEventType.SECURITY_SESSION_REVOKED

    def test_payload_extraction(self, user_id, session_id):
        """Test payload is correctly extracted from SessionRevokedEvent."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[SessionRevokedEvent]

        event = SessionRevokedEvent(
            user_id=user_id,
            session_id=session_id,
            reason="user_logout",
            device_info="Chrome on macOS",
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "session_id": str(session_id),
            "device_info": "Chrome on macOS",
            "reason": "user_logout",
        }

    def test_payload_extraction_security_revocation(self, user_id, session_id):
        """Test payload extraction for security-triggered revocation."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[SessionRevokedEvent]

        event = SessionRevokedEvent(
            user_id=user_id,
            session_id=session_id,
            reason="password_changed",
            device_info="Firefox on Windows",
            revoked_by_user=False,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "session_id": str(session_id),
            "device_info": "Firefox on Windows",
            "reason": "password_changed",
        }

    def test_user_id_extraction(self, user_id, session_id):
        """Test user_id is correctly extracted from SessionRevokedEvent."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[SessionRevokedEvent]

        event = SessionRevokedEvent(
            user_id=user_id,
            session_id=session_id,
            reason="test",
        )

        assert m.user_id_extractor(event) == user_id


# =============================================================================
# SuspiciousSessionActivityEvent Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestSuspiciousActivityMapping:
    """Test SuspiciousSessionActivityEvent domain-to-SSE mapping."""

    def test_mapping_to_correct_sse_event_type(self):
        """Test SuspiciousSessionActivityEvent maps to SECURITY_SESSION_SUSPICIOUS."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[SuspiciousSessionActivityEvent]

        assert m.sse_event_type == SSEEventType.SECURITY_SESSION_SUSPICIOUS

    def test_payload_extraction(self, user_id, session_id):
        """Test payload is correctly extracted from SuspiciousSessionActivityEvent."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[SuspiciousSessionActivityEvent]

        event = SuspiciousSessionActivityEvent(
            user_id=user_id,
            session_id=session_id,
            activity_type="ip_change",
            details={"old_ip": "192.168.1.1", "new_ip": "10.0.0.1"},
            suspicious_count=3,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "session_id": str(session_id),
            "reason": "ip_change",
        }

    def test_user_id_extraction(self, user_id, session_id):
        """Test user_id is correctly extracted from SuspiciousSessionActivityEvent."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[SuspiciousSessionActivityEvent]

        event = SuspiciousSessionActivityEvent(
            user_id=user_id,
            session_id=session_id,
            activity_type="rapid_requests",
        )

        assert m.user_id_extractor(event) == user_id


# =============================================================================
# UserPasswordChangeSucceeded Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestPasswordChangedMapping:
    """Test UserPasswordChangeSucceeded domain-to-SSE mapping."""

    def test_mapping_to_correct_sse_event_type(self):
        """Test UserPasswordChangeSucceeded maps to SECURITY_PASSWORD_CHANGED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[UserPasswordChangeSucceeded]

        assert m.sse_event_type == SSEEventType.SECURITY_PASSWORD_CHANGED

    def test_payload_extraction_user_initiated(self, user_id):
        """Test payload extraction when user initiated password change."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[UserPasswordChangeSucceeded]

        event = UserPasswordChangeSucceeded(
            user_id=user_id,
            initiated_by="user",
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "initiated_by": "user",
        }

    def test_payload_extraction_admin_initiated(self, user_id):
        """Test payload extraction when admin initiated password change."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[UserPasswordChangeSucceeded]

        event = UserPasswordChangeSucceeded(
            user_id=user_id,
            initiated_by="admin",
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "initiated_by": "admin",
        }

    def test_user_id_extraction(self, user_id):
        """Test user_id is correctly extracted from UserPasswordChangeSucceeded."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[UserPasswordChangeSucceeded]

        event = UserPasswordChangeSucceeded(
            user_id=user_id,
            initiated_by="user",
        )

        assert m.user_id_extractor(event) == user_id


# =============================================================================
# UserLoginFailed Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestLoginFailedMapping:
    """Test UserLoginFailed domain-to-SSE mapping."""

    def test_mapping_to_correct_sse_event_type(self):
        """Test UserLoginFailed maps to SECURITY_LOGIN_FAILED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[UserLoginFailed]

        assert m.sse_event_type == SSEEventType.SECURITY_LOGIN_FAILED

    def test_payload_extraction_invalid_credentials(self, user_id):
        """Test payload extraction for invalid credentials failure."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[UserLoginFailed]

        event = UserLoginFailed(
            email="user@example.com",
            reason="invalid_credentials",
            user_id=user_id,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "reason": "invalid_credentials",
        }

    def test_payload_extraction_account_locked(self, user_id):
        """Test payload extraction for account locked failure."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[UserLoginFailed]

        event = UserLoginFailed(
            email="user@example.com",
            reason="account_locked",
            user_id=user_id,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "reason": "account_locked",
        }

    def test_user_id_extraction_with_user(self, user_id):
        """Test user_id extraction when user exists."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[UserLoginFailed]

        event = UserLoginFailed(
            email="user@example.com",
            reason="invalid_credentials",
            user_id=user_id,
        )

        assert m.user_id_extractor(event) == user_id

    def test_user_id_extraction_without_user(self):
        """Test user_id extraction when user doesn't exist (None).

        When user_id is None, SSE event cannot be published since
        there's no target user channel. This is expected behavior.
        """
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[UserLoginFailed]

        event = UserLoginFailed(
            email="nonexistent@example.com",
            reason="user_not_found",
            user_id=None,
        )

        assert m.user_id_extractor(event) is None


# =============================================================================
# SSE Event Handler Integration Tests
# =============================================================================


@pytest.mark.unit
class TestSSEEventHandlerIntegration:
    """Test that security mappings work with SSEEventHandler."""

    def test_handler_has_mapping_for_all_security_events(self):
        """Verify SSEEventHandler can find mappings for security events."""
        from src.infrastructure.sse.sse_event_handler import SSEEventHandler

        mock_publisher = MagicMock()
        handler = SSEEventHandler(publisher=mock_publisher)

        # All security events should have mappings
        assert handler.has_mapping_for(SessionCreatedEvent)
        assert handler.has_mapping_for(SessionRevokedEvent)
        assert handler.has_mapping_for(SuspiciousSessionActivityEvent)
        assert handler.has_mapping_for(UserPasswordChangeSucceeded)
        assert handler.has_mapping_for(UserLoginFailed)

    def test_handler_returns_security_events_in_mapped_types(self):
        """Verify SSEEventHandler returns security events in mapped types."""
        from src.infrastructure.sse.sse_event_handler import SSEEventHandler

        mock_publisher = MagicMock()
        handler = SSEEventHandler(publisher=mock_publisher)

        mapped_types = handler.get_mapped_event_types()

        # Should include all security events
        assert SessionCreatedEvent in mapped_types
        assert SessionRevokedEvent in mapped_types
        assert SuspiciousSessionActivityEvent in mapped_types
        assert UserPasswordChangeSucceeded in mapped_types
        assert UserLoginFailed in mapped_types
