"""Unit tests for User model authentication functionality.

Tests user authentication fields, account lockout logic, and security features.
"""

from datetime import datetime, timezone, timedelta


from src.models.user import User


class TestUserAuthentication:
    """Test suite for User model authentication features."""

    def test_user_creation_with_auth_fields(self):
        """Test creating user with authentication fields."""
        user = User(
            email="test@example.com",
            name="Test User",
            password_hash="hashed_password_here",
            email_verified=False,
            failed_login_attempts=0,
            is_active=True,
        )

        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.password_hash == "hashed_password_here"
        assert user.email_verified is False
        assert user.failed_login_attempts == 0
        assert user.is_active is True
        assert user.account_locked_until is None

    def test_user_defaults(self):
        """Test default values for authentication fields."""
        user = User(
            email="test@example.com",
            name="Test User",
        )

        assert user.password_hash is None
        assert user.email_verified is False
        assert user.email_verified_at is None
        assert user.failed_login_attempts == 0
        assert user.account_locked_until is None
        assert user.last_login_at is None
        assert user.last_login_ip is None
        assert user.is_active is True

    def test_is_locked_property_when_not_locked(self):
        """Test is_locked returns False when account is not locked."""
        user = User(
            email="test@example.com",
            name="Test User",
            account_locked_until=None,
        )

        assert user.is_locked is False

    def test_is_locked_property_when_locked_in_future(self):
        """Test is_locked returns True when locked until future time."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        user = User(
            email="test@example.com",
            name="Test User",
            account_locked_until=future_time,
        )

        assert user.is_locked is True

    def test_is_locked_property_when_lockout_expired(self):
        """Test is_locked returns False when lockout period has expired."""
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        user = User(
            email="test@example.com",
            name="Test User",
            account_locked_until=past_time,
        )

        assert user.is_locked is False

    def test_can_login_when_active_and_not_locked(self):
        """Test can_login returns True for active, unlocked account."""
        user = User(
            email="test@example.com",
            name="Test User",
            is_active=True,
            account_locked_until=None,
        )

        assert user.can_login is True

    def test_can_login_when_inactive(self):
        """Test can_login returns False for inactive account."""
        user = User(
            email="test@example.com",
            name="Test User",
            is_active=False,
            account_locked_until=None,
        )

        assert user.can_login is False

    def test_can_login_when_locked(self):
        """Test can_login returns False for locked account."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        user = User(
            email="test@example.com",
            name="Test User",
            is_active=True,
            account_locked_until=future_time,
        )

        assert user.can_login is False

    def test_reset_failed_login_attempts(self):
        """Test resetting failed login attempts."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        user = User(
            email="test@example.com",
            name="Test User",
            failed_login_attempts=5,
            account_locked_until=future_time,
        )

        user.reset_failed_login_attempts()

        assert user.failed_login_attempts == 0
        assert user.account_locked_until is None

    def test_increment_failed_login_attempts_below_threshold(self):
        """Test incrementing failed attempts below lockout threshold."""
        user = User(
            email="test@example.com",
            name="Test User",
            failed_login_attempts=5,
        )

        user.increment_failed_login_attempts()

        assert user.failed_login_attempts == 6
        assert user.account_locked_until is None

    def test_increment_failed_login_attempts_reaches_threshold(self):
        """Test account locks after 10 failed attempts."""
        user = User(
            email="test@example.com",
            name="Test User",
            failed_login_attempts=9,
        )

        before_time = datetime.now(timezone.utc)
        user.increment_failed_login_attempts()
        after_time = datetime.now(timezone.utc) + timedelta(hours=1, minutes=1)

        assert user.failed_login_attempts == 10
        assert user.account_locked_until is not None
        assert before_time < user.account_locked_until < after_time
        assert user.is_locked is True

    def test_increment_failed_login_attempts_beyond_threshold(self):
        """Test incrementing beyond 10 attempts keeps account locked."""
        existing_lock_time = datetime.now(timezone.utc) + timedelta(hours=1)
        user = User(
            email="test@example.com",
            name="Test User",
            failed_login_attempts=10,
            account_locked_until=existing_lock_time,
        )

        user.increment_failed_login_attempts()

        assert user.failed_login_attempts == 11
        # Lock time should be updated
        assert user.account_locked_until is not None
        assert user.is_locked is True

    def test_display_name_uses_name(self):
        """Test display_name returns user's name when available."""
        user = User(
            email="test@example.com",
            name="John Doe",
        )

        assert user.display_name == "John Doe"

    def test_display_name_falls_back_to_email(self):
        """Test display_name uses email prefix when name is empty."""
        user = User(
            email="test@example.com",
            name="",
        )

        assert user.display_name == "test"

    def test_timezone_aware_datetime_fields(self):
        """Test that datetime fields are timezone-aware."""
        now = datetime.now(timezone.utc)
        user = User(
            email="test@example.com",
            name="Test User",
            email_verified_at=now,
            account_locked_until=now,
            last_login_at=now,
        )

        assert user.email_verified_at.tzinfo is not None
        assert user.account_locked_until.tzinfo is not None
        assert user.last_login_at.tzinfo is not None

    def test_active_providers_count_with_no_providers(self):
        """Test active_providers_count returns 0 when no providers."""
        user = User(
            email="test@example.com",
            name="Test User",
        )

        assert user.active_providers_count == 0
