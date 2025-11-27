"""Unit tests for authorization domain events.

Tests for the 6 authorization events (3-state pattern):
- RoleAssignmentAttempted/Succeeded/Failed
- RoleRevocationAttempted/Succeeded/Failed

Reference:
    - src/domain/events/authorization_events.py
    - docs/architecture/authorization-architecture.md
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from src.domain.events import (
    RoleAssignmentAttempted,
    RoleAssignmentFailed,
    RoleAssignmentSucceeded,
    RoleRevocationAttempted,
    RoleRevocationFailed,
    RoleRevocationSucceeded,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def user_id() -> UUID:
    """Test user ID."""
    return uuid4()


@pytest.fixture
def admin_id() -> UUID:
    """Test admin user ID."""
    return uuid4()


# =============================================================================
# RoleAssignmentAttempted Tests
# =============================================================================


class TestRoleAssignmentAttempted:
    """Tests for RoleAssignmentAttempted event."""

    def test_create_with_required_fields(self, user_id: UUID, admin_id: UUID) -> None:
        """Test creating event with required fields."""
        event = RoleAssignmentAttempted(
            user_id=user_id,
            role="admin",
            assigned_by=admin_id,
        )

        assert event.user_id == user_id
        assert event.role == "admin"
        assert event.assigned_by == admin_id
        assert event.event_id is not None
        assert event.occurred_at is not None

    def test_event_has_auto_generated_id(self, user_id: UUID, admin_id: UUID) -> None:
        """Test event_id is auto-generated."""
        event1 = RoleAssignmentAttempted(
            user_id=user_id, role="admin", assigned_by=admin_id
        )
        event2 = RoleAssignmentAttempted(
            user_id=user_id, role="admin", assigned_by=admin_id
        )

        assert event1.event_id != event2.event_id

    def test_event_has_occurred_at_timestamp(
        self, user_id: UUID, admin_id: UUID
    ) -> None:
        """Test occurred_at is set to current time."""
        before = datetime.now(UTC)
        event = RoleAssignmentAttempted(
            user_id=user_id, role="admin", assigned_by=admin_id
        )
        after = datetime.now(UTC)

        assert before <= event.occurred_at <= after

    def test_event_is_immutable(self, user_id: UUID, admin_id: UUID) -> None:
        """Test event is frozen (immutable)."""
        event = RoleAssignmentAttempted(
            user_id=user_id, role="admin", assigned_by=admin_id
        )

        with pytest.raises(AttributeError):
            event.role = "user"  # type: ignore[misc]


# =============================================================================
# RoleAssignmentSucceeded Tests
# =============================================================================


class TestRoleAssignmentSucceeded:
    """Tests for RoleAssignmentSucceeded event."""

    def test_create_with_required_fields(self, user_id: UUID, admin_id: UUID) -> None:
        """Test creating event with required fields."""
        event = RoleAssignmentSucceeded(
            user_id=user_id,
            role="admin",
            assigned_by=admin_id,
        )

        assert event.user_id == user_id
        assert event.role == "admin"
        assert event.assigned_by == admin_id
        assert event.event_id is not None

    def test_different_roles(self, user_id: UUID, admin_id: UUID) -> None:
        """Test creating events with different roles."""
        for role in ["admin", "user", "readonly"]:
            event = RoleAssignmentSucceeded(
                user_id=user_id, role=role, assigned_by=admin_id
            )
            assert event.role == role


# =============================================================================
# RoleAssignmentFailed Tests
# =============================================================================


class TestRoleAssignmentFailed:
    """Tests for RoleAssignmentFailed event."""

    def test_create_with_required_fields(self, user_id: UUID, admin_id: UUID) -> None:
        """Test creating event with required fields."""
        event = RoleAssignmentFailed(
            user_id=user_id,
            role="admin",
            assigned_by=admin_id,
            reason="already_has_role",
        )

        assert event.user_id == user_id
        assert event.role == "admin"
        assert event.assigned_by == admin_id
        assert event.reason == "already_has_role"

    def test_different_failure_reasons(self, user_id: UUID, admin_id: UUID) -> None:
        """Test creating events with different failure reasons."""
        reasons = [
            "already_has_role",
            "invalid_role",
            "permission_denied",
            "database_error: Connection refused",
        ]

        for reason in reasons:
            event = RoleAssignmentFailed(
                user_id=user_id,
                role="admin",
                assigned_by=admin_id,
                reason=reason,
            )
            assert event.reason == reason


# =============================================================================
# RoleRevocationAttempted Tests
# =============================================================================


class TestRoleRevocationAttempted:
    """Tests for RoleRevocationAttempted event."""

    def test_create_with_required_fields(self, user_id: UUID, admin_id: UUID) -> None:
        """Test creating event with required fields."""
        event = RoleRevocationAttempted(
            user_id=user_id,
            role="admin",
            revoked_by=admin_id,
        )

        assert event.user_id == user_id
        assert event.role == "admin"
        assert event.revoked_by == admin_id
        assert event.reason is None  # Optional

    def test_create_with_optional_reason(self, user_id: UUID, admin_id: UUID) -> None:
        """Test creating event with optional reason."""
        event = RoleRevocationAttempted(
            user_id=user_id,
            role="admin",
            revoked_by=admin_id,
            reason="User violated terms of service",
        )

        assert event.reason == "User violated terms of service"

    def test_event_has_auto_generated_id(self, user_id: UUID, admin_id: UUID) -> None:
        """Test event_id is auto-generated."""
        event1 = RoleRevocationAttempted(
            user_id=user_id, role="admin", revoked_by=admin_id
        )
        event2 = RoleRevocationAttempted(
            user_id=user_id, role="admin", revoked_by=admin_id
        )

        assert event1.event_id != event2.event_id


# =============================================================================
# RoleRevocationSucceeded Tests
# =============================================================================


class TestRoleRevocationSucceeded:
    """Tests for RoleRevocationSucceeded event."""

    def test_create_with_required_fields(self, user_id: UUID, admin_id: UUID) -> None:
        """Test creating event with required fields."""
        event = RoleRevocationSucceeded(
            user_id=user_id,
            role="admin",
            revoked_by=admin_id,
        )

        assert event.user_id == user_id
        assert event.role == "admin"
        assert event.revoked_by == admin_id
        assert event.reason is None

    def test_create_with_reason(self, user_id: UUID, admin_id: UUID) -> None:
        """Test creating event with reason."""
        event = RoleRevocationSucceeded(
            user_id=user_id,
            role="admin",
            revoked_by=admin_id,
            reason="Account suspended",
        )

        assert event.reason == "Account suspended"


# =============================================================================
# RoleRevocationFailed Tests
# =============================================================================


class TestRoleRevocationFailed:
    """Tests for RoleRevocationFailed event."""

    def test_create_with_required_fields(self, user_id: UUID, admin_id: UUID) -> None:
        """Test creating event with required fields."""
        event = RoleRevocationFailed(
            user_id=user_id,
            role="admin",
            revoked_by=admin_id,
            reason="does_not_have_role",
        )

        assert event.user_id == user_id
        assert event.role == "admin"
        assert event.revoked_by == admin_id
        assert event.reason == "does_not_have_role"

    def test_different_failure_reasons(self, user_id: UUID, admin_id: UUID) -> None:
        """Test creating events with different failure reasons."""
        reasons = [
            "does_not_have_role",
            "last_admin_role",
            "permission_denied",
            "database_error: Connection refused",
        ]

        for reason in reasons:
            event = RoleRevocationFailed(
                user_id=user_id,
                role="admin",
                revoked_by=admin_id,
                reason=reason,
            )
            assert event.reason == reason


# =============================================================================
# Event Timestamp Tests
# =============================================================================


class TestEventTimestamps:
    """Tests for event timestamp behavior."""

    def test_all_events_have_utc_timestamps(
        self, user_id: UUID, admin_id: UUID
    ) -> None:
        """Test all events use UTC timezone."""
        events = [
            RoleAssignmentAttempted(
                user_id=user_id, role="admin", assigned_by=admin_id
            ),
            RoleAssignmentSucceeded(
                user_id=user_id, role="admin", assigned_by=admin_id
            ),
            RoleAssignmentFailed(
                user_id=user_id,
                role="admin",
                assigned_by=admin_id,
                reason="test",
            ),
            RoleRevocationAttempted(
                user_id=user_id, role="admin", revoked_by=admin_id
            ),
            RoleRevocationSucceeded(
                user_id=user_id, role="admin", revoked_by=admin_id
            ),
            RoleRevocationFailed(
                user_id=user_id,
                role="admin",
                revoked_by=admin_id,
                reason="test",
            ),
        ]

        for event in events:
            # Check timezone is UTC
            assert event.occurred_at.tzinfo is not None
            # Check timestamp is recent (within last minute)
            assert datetime.now(UTC) - event.occurred_at < timedelta(minutes=1)
