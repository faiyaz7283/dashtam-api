"""Unit tests for Session domain entity.

Tests cover:
- Session creation with various attributes
- is_active() logic (revoked, expired)
- revoke() method
- update_activity() method
- record_provider_access() method
- increment_suspicious_activity() method
- mark_as_trusted() method

Architecture:
- Pure domain entity tests (no mocks needed)
- Test business logic, not persistence
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.domain.entities.session import Session


@pytest.mark.unit
class TestSessionCreation:
    """Test Session entity creation."""

    def test_session_creation_with_required_fields(self):
        """Test session creation with only required fields."""
        session_id = uuid4()
        user_id = uuid4()

        session = Session(id=session_id, user_id=user_id)

        assert session.id == session_id
        assert session.user_id == user_id
        assert session.is_revoked is False
        assert session.is_trusted is False
        assert session.suspicious_activity_count == 0
        assert session.providers_accessed == []

    def test_session_creation_with_all_fields(self):
        """Test session creation with all fields populated."""
        session_id = uuid4()
        user_id = uuid4()
        refresh_token_id = uuid4()
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=30)

        session = Session(
            id=session_id,
            user_id=user_id,
            device_info="Chrome on Windows",
            user_agent="Mozilla/5.0 Chrome/120.0",
            ip_address="192.168.1.1",
            location="New York, US",
            created_at=now,
            last_activity_at=now,
            expires_at=expires_at,
            is_revoked=False,
            is_trusted=True,
            refresh_token_id=refresh_token_id,
            last_ip_address="192.168.1.1",
            suspicious_activity_count=0,
            last_provider_accessed="schwab",
            last_provider_sync_at=now,
            providers_accessed=["schwab", "fidelity"],
        )

        assert session.id == session_id
        assert session.device_info == "Chrome on Windows"
        assert session.location == "New York, US"
        assert session.is_trusted is True
        assert session.providers_accessed == ["schwab", "fidelity"]


@pytest.mark.unit
class TestSessionIsActive:
    """Test Session.is_active() business logic."""

    def test_is_active_returns_true_for_new_session(self):
        """Test new session is active by default."""
        session = Session(id=uuid4(), user_id=uuid4())

        assert session.is_active() is True

    def test_is_active_returns_false_when_revoked(self):
        """Test revoked session is not active."""
        session = Session(id=uuid4(), user_id=uuid4(), is_revoked=True)

        assert session.is_active() is False

    def test_is_active_returns_false_when_expired(self):
        """Test expired session is not active."""
        past_time = datetime.now(UTC) - timedelta(hours=1)
        session = Session(id=uuid4(), user_id=uuid4(), expires_at=past_time)

        assert session.is_active() is False

    def test_is_active_returns_true_when_not_expired(self):
        """Test session with future expiration is active."""
        future_time = datetime.now(UTC) + timedelta(days=30)
        session = Session(id=uuid4(), user_id=uuid4(), expires_at=future_time)

        assert session.is_active() is True

    def test_is_active_returns_true_when_no_expiration(self):
        """Test session without expiration is active."""
        session = Session(id=uuid4(), user_id=uuid4(), expires_at=None)

        assert session.is_active() is True

    def test_is_active_returns_false_when_both_revoked_and_expired(self):
        """Test session that is both revoked and expired is not active."""
        past_time = datetime.now(UTC) - timedelta(hours=1)
        session = Session(
            id=uuid4(), user_id=uuid4(), is_revoked=True, expires_at=past_time
        )

        assert session.is_active() is False


@pytest.mark.unit
class TestSessionRevoke:
    """Test Session.revoke() method."""

    def test_revoke_marks_session_as_revoked(self):
        """Test revoke sets is_revoked to True."""
        session = Session(id=uuid4(), user_id=uuid4())

        session.revoke("user_logout")

        assert session.is_revoked is True

    def test_revoke_sets_revoked_reason(self):
        """Test revoke stores the reason."""
        session = Session(id=uuid4(), user_id=uuid4())

        session.revoke("password_changed")

        assert session.revoked_reason == "password_changed"

    def test_revoke_sets_revoked_at_timestamp(self):
        """Test revoke sets timestamp."""
        session = Session(id=uuid4(), user_id=uuid4())
        before_revoke = datetime.now(UTC)

        session.revoke("security_concern")

        assert session.revoked_at is not None
        assert session.revoked_at >= before_revoke

    def test_revoke_makes_session_inactive(self):
        """Test revoked session becomes inactive."""
        session = Session(id=uuid4(), user_id=uuid4())
        assert session.is_active() is True

        session.revoke("admin_action")

        assert session.is_active() is False

    def test_revoke_with_various_reasons(self):
        """Test revoke accepts various standard reasons."""
        reasons = [
            "user_logout",
            "password_changed",
            "max_sessions_exceeded",
            "admin_action",
            "security_concern",
        ]

        for reason in reasons:
            session = Session(id=uuid4(), user_id=uuid4())
            session.revoke(reason)
            assert session.revoked_reason == reason


@pytest.mark.unit
class TestSessionUpdateActivity:
    """Test Session.update_activity() method."""

    def test_update_activity_updates_timestamp(self):
        """Test update_activity sets last_activity_at."""
        session = Session(id=uuid4(), user_id=uuid4())
        before_update = datetime.now(UTC)

        session.update_activity()

        assert session.last_activity_at is not None
        assert session.last_activity_at >= before_update

    def test_update_activity_with_same_ip(self):
        """Test update_activity with same IP doesn't track change."""
        session = Session(id=uuid4(), user_id=uuid4(), ip_address="192.168.1.1")

        session.update_activity(ip_address="192.168.1.1")

        # Same IP, no change tracked
        assert session.ip_address == "192.168.1.1"
        assert session.last_ip_address is None

    def test_update_activity_with_different_ip_tracks_change(self):
        """Test update_activity with different IP tracks change."""
        session = Session(id=uuid4(), user_id=uuid4(), ip_address="192.168.1.1")

        session.update_activity(ip_address="10.0.0.1")

        # Original IP unchanged, new IP stored in last_ip
        assert session.ip_address == "192.168.1.1"
        assert session.last_ip_address == "10.0.0.1"

    def test_update_activity_sets_ip_when_none(self):
        """Test update_activity sets IP if none was set."""
        session = Session(id=uuid4(), user_id=uuid4(), ip_address=None)

        session.update_activity(ip_address="192.168.1.1")

        assert session.ip_address == "192.168.1.1"

    def test_update_activity_without_ip(self):
        """Test update_activity without IP only updates timestamp."""
        session = Session(id=uuid4(), user_id=uuid4(), ip_address="192.168.1.1")
        before_update = datetime.now(UTC)

        session.update_activity()

        assert session.last_activity_at >= before_update
        assert session.ip_address == "192.168.1.1"


@pytest.mark.unit
class TestSessionRecordProviderAccess:
    """Test Session.record_provider_access() method."""

    def test_record_provider_access_stores_provider(self):
        """Test record_provider_access adds provider to list."""
        session = Session(id=uuid4(), user_id=uuid4())

        session.record_provider_access("schwab")

        assert "schwab" in session.providers_accessed

    def test_record_provider_access_sets_last_provider(self):
        """Test record_provider_access sets last_provider_accessed."""
        session = Session(id=uuid4(), user_id=uuid4())

        session.record_provider_access("fidelity")

        assert session.last_provider_accessed == "fidelity"

    def test_record_provider_access_sets_sync_timestamp(self):
        """Test record_provider_access sets last_provider_sync_at."""
        session = Session(id=uuid4(), user_id=uuid4())
        before_access = datetime.now(UTC)

        session.record_provider_access("schwab")

        assert session.last_provider_sync_at is not None
        assert session.last_provider_sync_at >= before_access

    def test_record_provider_access_multiple_providers(self):
        """Test recording access to multiple providers."""
        session = Session(id=uuid4(), user_id=uuid4())

        session.record_provider_access("schwab")
        session.record_provider_access("fidelity")
        session.record_provider_access("vanguard")

        assert session.providers_accessed == ["schwab", "fidelity", "vanguard"]
        assert session.last_provider_accessed == "vanguard"

    def test_record_provider_access_no_duplicates(self):
        """Test same provider not added twice to list."""
        session = Session(id=uuid4(), user_id=uuid4())

        session.record_provider_access("schwab")
        session.record_provider_access("schwab")

        assert session.providers_accessed == ["schwab"]
        assert session.providers_accessed.count("schwab") == 1


@pytest.mark.unit
class TestSessionSuspiciousActivity:
    """Test Session.increment_suspicious_activity() method."""

    def test_increment_suspicious_activity_increases_count(self):
        """Test increment adds to counter."""
        session = Session(id=uuid4(), user_id=uuid4())
        assert session.suspicious_activity_count == 0

        session.increment_suspicious_activity()

        assert session.suspicious_activity_count == 1

    def test_increment_suspicious_activity_multiple_times(self):
        """Test multiple increments."""
        session = Session(id=uuid4(), user_id=uuid4())

        session.increment_suspicious_activity()
        session.increment_suspicious_activity()
        session.increment_suspicious_activity()

        assert session.suspicious_activity_count == 3


@pytest.mark.unit
class TestSessionMarkAsTrusted:
    """Test Session.mark_as_trusted() method."""

    def test_mark_as_trusted_sets_flag(self):
        """Test mark_as_trusted sets is_trusted to True."""
        session = Session(id=uuid4(), user_id=uuid4())
        assert session.is_trusted is False

        session.mark_as_trusted()

        assert session.is_trusted is True

    def test_mark_as_trusted_idempotent(self):
        """Test mark_as_trusted can be called multiple times."""
        session = Session(id=uuid4(), user_id=uuid4())

        session.mark_as_trusted()
        session.mark_as_trusted()

        assert session.is_trusted is True
