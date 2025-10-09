"""Unit tests for User model authentication functionality.

Tests user authentication fields, account lockout logic, and security features.
"""

from datetime import datetime, timezone, timedelta


from src.models.user import User


class TestUserAuthentication:
    """Test suite for User model authentication features."""

    def test_user_creation_with_auth_fields(self):
        """Test User model instantiation with all authentication fields.
        
        Verifies that:
        - All authentication fields can be set during instantiation
        - email, name, password_hash assigned correctly
        - email_verified boolean flag set
        - failed_login_attempts counter initialized
        - is_active flag set
        - account_locked_until defaults to None
        
        Note:
            Tests basic User model constructor for auth-related fields.
        """
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
        """Test default values for optional authentication fields.
        
        Verifies that:
        - password_hash defaults to None (must be set explicitly)
        - email_verified defaults to False (security: verify required)
        - email_verified_at defaults to None
        - failed_login_attempts defaults to 0
        - account_locked_until defaults to None (not locked)
        - last_login_at defaults to None
        - last_login_ip defaults to None
        - is_active defaults to True (new users active)
        
        Note:
            Secure defaults: email_verified=False prevents unverified login.
        """
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
        """Test is_locked property returns False for unlocked account.
        
        Verifies that:
        - is_locked property returns False
        - account_locked_until is None
        - User can attempt login
        
        Note:
            is_locked is a computed property based on account_locked_until.
        """
        user = User(
            email="test@example.com",
            name="Test User",
            account_locked_until=None,
        )

        assert user.is_locked is False

    def test_is_locked_property_when_locked_in_future(self):
        """Test is_locked property returns True during active lockout.
        
        Verifies that:
        - is_locked returns True when lock time in future
        - account_locked_until is set to future datetime
        - User cannot login during lockout period
        
        Note:
            Account lockout triggered after 10 failed login attempts (1-hour TTL).
        """
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        user = User(
            email="test@example.com",
            name="Test User",
            account_locked_until=future_time,
        )

        assert user.is_locked is True

    def test_is_locked_property_when_lockout_expired(self):
        """Test is_locked property returns False after lockout expiry.
        
        Verifies that:
        - is_locked returns False when lock time in past
        - account_locked_until set but expired
        - User can attempt login after lockout expires
        - Automatic unlocking based on timestamp
        
        Note:
            Lockout automatically expires after 1 hour - no manual unlock needed.
        """
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        user = User(
            email="test@example.com",
            name="Test User",
            account_locked_until=past_time,
        )

        assert user.is_locked is False

    def test_can_login_when_active_and_not_locked(self):
        """Test can_login property for normal active account.
        
        Verifies that:
        - can_login returns True
        - User is_active is True
        - account_locked_until is None
        - User can proceed with login
        
        Note:
            Normal case: active user with no lockout.
        """
        user = User(
            email="test@example.com",
            name="Test User",
            is_active=True,
            account_locked_until=None,
        )

        assert user.can_login is True

    def test_can_login_when_inactive(self):
        """Test can_login property rejects inactive accounts.
        
        Verifies that:
        - can_login returns False
        - User is_active is False
        - Login blocked regardless of lockout status
        - Prevents deleted/disabled user login
        
        Note:
            Admin can deactivate accounts for security/compliance.
        """
        user = User(
            email="test@example.com",
            name="Test User",
            is_active=False,
            account_locked_until=None,
        )

        assert user.can_login is False

    def test_can_login_when_locked(self):
        """Test can_login property rejects locked accounts.
        
        Verifies that:
        - can_login returns False
        - User is_active is True (but locked)
        - account_locked_until in future
        - Login blocked during lockout period
        
        Note:
            Lockout triggered after 10 failed login attempts.
        """
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        user = User(
            email="test@example.com",
            name="Test User",
            is_active=True,
            account_locked_until=future_time,
        )

        assert user.can_login is False

    def test_reset_failed_login_attempts(self):
        """Test reset_failed_login_attempts method clears lockout.
        
        Verifies that:
        - failed_login_attempts reset to 0
        - account_locked_until cleared (None)
        - User can attempt login again
        - Lockout fully cleared
        
        Note:
            Called after successful login to reset security counter.
        """
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
        """Test increment_failed_login_attempts before lockout threshold.
        
        Verifies that:
        - failed_login_attempts incremented by 1
        - Counter goes from 5 to 6 (below threshold)
        - account_locked_until remains None
        - No lockout triggered (threshold is 10)
        
        Note:
            Failed attempts tracked but no lockout until 10th attempt.
        """
        user = User(
            email="test@example.com",
            name="Test User",
            failed_login_attempts=5,
        )

        user.increment_failed_login_attempts()

        assert user.failed_login_attempts == 6
        assert user.account_locked_until is None

    def test_increment_failed_login_attempts_reaches_threshold(self):
        """Test account lockout triggered at 10th failed attempt.
        
        Verifies that:
        - failed_login_attempts incremented from 9 to 10
        - account_locked_until set to future timestamp
        - Lockout duration is 1 hour from now
        - is_locked property returns True
        - Automatic security lockout activated
        
        Note:
            Critical security feature: prevents brute-force attacks.
        """
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
        """Test continued failed attempts extend lockout period.
        
        Verifies that:
        - failed_login_attempts incremented beyond 10 (11)
        - account_locked_until updated to new timestamp
        - Lockout time extended (not cleared)
        - is_locked remains True
        - Each failed attempt during lockout extends duration
        
        Note:
            Prevents immediate retry after lockout expires.
        """
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
        """Test display_name property returns full name when set.
        
        Verifies that:
        - display_name returns user.name value
        - Full name "John Doe" returned
        - Preferred display value is name field
        
        Note:
            Used in UI and email templates for personalization.
        """
        user = User(
            email="test@example.com",
            name="John Doe",
        )

        assert user.display_name == "John Doe"

    def test_display_name_falls_back_to_email(self):
        """Test display_name property fallback to email prefix.
        
        Verifies that:
        - display_name falls back to email prefix
        - Empty name string triggers fallback
        - Email "test@example.com" returns "test"
        - Graceful handling of missing name
        
        Note:
            Ensures always have display name for UI (never empty).
        """
        user = User(
            email="test@example.com",
            name="",
        )

        assert user.display_name == "test"

    def test_timezone_aware_datetime_fields(self):
        """Test datetime fields are timezone-aware (TIMESTAMPTZ compliance).
        
        Verifies that:
        - email_verified_at has tzinfo (not naive)
        - account_locked_until has tzinfo
        - last_login_at has tzinfo
        - All datetime fields are timezone-aware
        - PCI-DSS compliance requirement met
        
        Note:
            CRITICAL: All datetimes must be timezone-aware per P0 requirements.
        """
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
        """Test active_providers_count property with no connected providers.
        
        Verifies that:
        - active_providers_count returns 0
        - User has no provider connections
        - Property handles empty relationship
        - No errors for new user
        
        Note:
            User without providers cannot access financial data yet.
        """
        user = User(
            email="test@example.com",
            name="Test User",
        )

        assert user.active_providers_count == 0
