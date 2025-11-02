"""Unit tests for SessionBase model.

Tests the business logic methods defined in SessionBase,
particularly is_active() which determines session validity.
"""

from datetime import datetime, timedelta, timezone

from src.session_manager.tests.fixtures.mock_models import MockSession


class TestIsActiveMethod:
    """Test SessionBase.is_active() business logic."""

    def test_is_active_when_valid(self):
        """Test that active, non-expired session returns True."""
        future = datetime.now(timezone.utc) + timedelta(days=1)
        session = MockSession(
            is_revoked=False,
            expires_at=future,
        )

        assert session.is_active() is True

    def test_is_active_when_revoked(self):
        """Test that revoked session returns False."""
        future = datetime.now(timezone.utc) + timedelta(days=1)
        session = MockSession(
            is_revoked=True,
            expires_at=future,
        )

        assert session.is_active() is False

    def test_is_active_when_expired(self):
        """Test that expired session returns False."""
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        session = MockSession(
            is_revoked=False,
            expires_at=past,
        )

        assert session.is_active() is False

    def test_is_active_when_revoked_and_expired(self):
        """Test that revoked AND expired session returns False."""
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        session = MockSession(
            is_revoked=True,
            expires_at=past,
        )

        assert session.is_active() is False

    def test_is_active_when_no_expiration(self):
        """Test that session with no expiration is active if not revoked."""
        session = MockSession(
            is_revoked=False,
            expires_at=None,  # Never expires
        )

        assert session.is_active() is True

    def test_is_active_when_expires_at_exactly_now(self):
        """Test edge case when expires_at is exactly current time."""
        now = datetime.now(timezone.utc)
        session = MockSession(
            is_revoked=False,
            expires_at=now,
        )

        # Should be False (expired) since now > expires_at would be True
        # after any tiny time passing
        assert session.is_active() is False

    def test_is_active_when_expires_in_one_second(self):
        """Test that session expiring in 1 second is still active."""
        one_second_future = datetime.now(timezone.utc) + timedelta(seconds=1)
        session = MockSession(
            is_revoked=False,
            expires_at=one_second_future,
        )

        assert session.is_active() is True


class TestSessionBaseFields:
    """Test that SessionBase enforces required fields."""

    def test_required_fields_present(self):
        """Test that all required fields are present in MockSession."""
        session = MockSession()

        # Required fields should exist
        assert hasattr(session, "id")
        assert hasattr(session, "user_id")
        assert hasattr(session, "device_info")
        assert hasattr(session, "ip_address")
        assert hasattr(session, "user_agent")
        assert hasattr(session, "location")
        assert hasattr(session, "created_at")
        assert hasattr(session, "last_activity")
        assert hasattr(session, "expires_at")
        assert hasattr(session, "is_revoked")
        assert hasattr(session, "is_trusted")
        assert hasattr(session, "revoked_at")
        assert hasattr(session, "revoked_reason")

    def test_is_active_method_exists(self):
        """Test that is_active() method exists."""
        session = MockSession()

        # Should have is_active method
        assert hasattr(session, "is_active")
        assert callable(session.is_active)

    def test_created_at_is_timezone_aware(self):
        """Test that created_at is timezone-aware (UTC)."""
        session = MockSession()

        assert session.created_at.tzinfo is not None
        assert session.created_at.tzinfo == timezone.utc

    def test_default_values(self):
        """Test that MockSession has sensible defaults."""
        session = MockSession()

        # Defaults
        assert session.is_revoked is False
        assert session.is_trusted is False
        assert session.revoked_at is None
        assert session.revoked_reason is None
