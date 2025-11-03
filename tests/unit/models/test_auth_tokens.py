"""Unit tests for authentication token models.

Tests RefreshToken, EmailVerificationToken, and PasswordResetToken models.
"""

from datetime import datetime, timezone, timedelta
from uuid import uuid4


from src.models.auth import (
    RefreshToken,
    EmailVerificationToken,
    PasswordResetToken,
)


class TestRefreshToken:
    """Test suite for RefreshToken model.

    Tests opaque refresh token model used in JWT authentication (Pattern A).
    Tokens are hashed (bcrypt) before storage for security.
    """

    def test_refresh_token_creation(self):
        """Test RefreshToken model instantiation with all fields.

        Verifies that:
        - Model created with user_id, token_hash, expires_at
        - session_id links to Session (device/browser metadata stored there)
        - is_revoked defaults to False
        - revoked_at defaults to None
        - Token versioning fields included

        Note:
            Refresh tokens are opaque (hashed) and linked to sessions (30-day TTL).
            Device/IP metadata moved to Session model for proper separation of concerns.
        """
        user_id = uuid4()
        session_id = uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        token = RefreshToken(
            user_id=user_id,
            session_id=session_id,
            token_hash="hashed_token_here",
            expires_at=expires_at,
            token_version=1,
            global_version_at_issuance=1,
        )

        assert token.user_id == user_id
        assert token.session_id == session_id
        assert token.token_hash == "hashed_token_here"
        assert token.expires_at == expires_at
        assert token.is_revoked is False
        assert token.revoked_at is None
        assert token.token_version == 1
        assert token.global_version_at_issuance == 1

    def test_is_expired_property_when_not_expired(self):
        """Test is_expired property returns False for valid token.

        Verifies that:
        - is_expired returns False
        - expires_at in future
        - Token can be used for refresh
        """
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        token = RefreshToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
        )

        assert token.is_expired is False

    def test_is_expired_property_when_expired(self):
        """Test is_expired property returns True for expired token.

        Verifies that:
        - is_expired returns True
        - expires_at in past
        - Token cannot be used (must re-login)
        """
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        token = RefreshToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=past_time,
        )

        assert token.is_expired is True

    def test_is_valid_property_when_valid(self):
        """Test is_valid property for usable token.

        Verifies that:
        - is_valid returns True
        - Token not expired and not revoked
        - Token can be used for refresh
        """
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        token = RefreshToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
            is_revoked=False,
        )

        assert token.is_valid is True

    def test_is_valid_property_when_expired(self):
        """Test is_valid property rejects expired token.

        Verifies that:
        - is_valid returns False
        - Expiry invalidates token even if not revoked
        """
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        token = RefreshToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=past_time,
            is_revoked=False,
        )

        assert token.is_valid is False

    def test_is_valid_property_when_revoked(self):
        """Test is_valid property rejects revoked token.

        Verifies that:
        - is_valid returns False
        - Revocation invalidates token even if not expired
        - Security: revoked tokens cannot be reused
        """
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        token = RefreshToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
            is_revoked=True,
        )

        assert token.is_valid is False

    def test_revoke_method(self):
        """Test revoke() method marks token as revoked.

        Verifies that:
        - is_revoked set to True
        - revoked_at timestamp set to current time
        - Token becomes invalid

        Note:
            Called on logout or security events (e.g., password change).
        """
        token = RefreshToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )

        before_revoke = datetime.now(timezone.utc)
        token.revoke()
        after_revoke = datetime.now(timezone.utc) + timedelta(seconds=1)

        assert token.is_revoked is True
        assert token.revoked_at is not None
        assert before_revoke <= token.revoked_at <= after_revoke

    def test_timezone_aware_datetime_fields(self):
        """Test datetime fields are timezone-aware (TIMESTAMPTZ).

        Verifies that:
        - expires_at has tzinfo
        - revoked_at has tzinfo
        - PCI-DSS compliance requirement met

        Note:
            last_used_at moved to Session model (session tracking).
        """
        now = datetime.now(timezone.utc)
        token = RefreshToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=now,
            revoked_at=now,
        )

        assert token.expires_at.tzinfo is not None
        assert token.revoked_at.tzinfo is not None


class TestEmailVerificationToken:
    """Test suite for EmailVerificationToken model.

    Tests single-use tokens for email verification (24-hour TTL).
    Tokens are hashed before storage and marked as used after verification.
    """

    def test_email_verification_token_creation(self):
        """Test EmailVerificationToken model instantiation.

        Verifies that:
        - Model created with user_id, token_hash, expires_at
        - used_at defaults to None (not yet used)
        - 24-hour TTL for verification

        Note:
            Email verification required before login per security policy.
        """
        user_id = uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        token = EmailVerificationToken(
            user_id=user_id,
            token_hash="hashed_token_here",
            expires_at=expires_at,
        )

        assert token.user_id == user_id
        assert token.token_hash == "hashed_token_here"
        assert token.expires_at == expires_at
        assert token.used_at is None

    def test_is_expired_property_when_not_expired(self):
        """Test is_expired property returns False for valid token.

        Verifies that:
        - is_expired returns False
        - expires_at in future
        - Token can be used for verification
        """
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
        )

        assert token.is_expired is False

    def test_is_expired_property_when_expired(self):
        """Test is_expired property returns True for expired token.

        Verifies that:
        - is_expired returns True
        - expires_at in past
        - User must request new verification email
        """
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=past_time,
        )

        assert token.is_expired is True

    def test_is_used_property_when_not_used(self):
        """Test is_used property returns False for unused token.

        Verifies that:
        - is_used returns False
        - used_at is None
        - Token available for verification
        """
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            used_at=None,
        )

        assert token.is_used is False

    def test_is_used_property_when_used(self):
        """Test is_used property returns True for used token.

        Verifies that:
        - is_used returns True
        - used_at timestamp set
        - Token cannot be reused (single-use)
        """
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            used_at=datetime.now(timezone.utc),
        )

        assert token.is_used is True

    def test_is_valid_property_when_valid(self):
        """Test is_valid property for usable token.

        Verifies that:
        - is_valid returns True
        - Token not expired and not used
        - Token can verify email
        """
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
            used_at=None,
        )

        assert token.is_valid is True

    def test_is_valid_property_when_expired(self):
        """Test is_valid property rejects expired token.

        Verifies that:
        - is_valid returns False
        - Expiry invalidates token even if not used
        """
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=past_time,
            used_at=None,
        )

        assert token.is_valid is False

    def test_is_valid_property_when_used(self):
        """Test is_valid property rejects used token.

        Verifies that:
        - is_valid returns False
        - Usage invalidates token even if not expired
        - Security: prevents token reuse
        """
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
            used_at=datetime.now(timezone.utc),
        )

        assert token.is_valid is False

    def test_mark_as_used_method(self):
        """Test mark_as_used() method marks token as consumed.

        Verifies that:
        - used_at timestamp set to current time
        - is_used returns True
        - Token becomes invalid

        Note:
            Called after successful email verification.
        """
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )

        before_mark = datetime.now(timezone.utc)
        token.mark_as_used()
        after_mark = datetime.now(timezone.utc) + timedelta(seconds=1)

        assert token.used_at is not None
        assert before_mark <= token.used_at <= after_mark
        assert token.is_used is True

    def test_timezone_aware_datetime_fields(self):
        """Test datetime fields are timezone-aware (TIMESTAMPTZ).

        Verifies that:
        - expires_at has tzinfo
        - used_at has tzinfo
        - PCI-DSS compliance requirement met
        """
        now = datetime.now(timezone.utc)
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=now,
            used_at=now,
        )

        assert token.expires_at.tzinfo is not None
        assert token.used_at.tzinfo is not None


class TestPasswordResetToken:
    """Test suite for PasswordResetToken model.

    Tests single-use tokens for password reset (1-hour TTL).
    Tokens are hashed before storage, tracked with IP/user agent for security.
    """

    def test_password_reset_token_creation(self):
        """Test PasswordResetToken model instantiation.

        Verifies that:
        - Model created with user_id, token_hash, expires_at
        - Tracking fields captured: ip_address, user_agent
        - used_at defaults to None (not yet used)
        - Short 1-hour TTL for security

        Note:
            Short expiry window reduces exposure if token intercepted.
        """
        user_id = uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        token = PasswordResetToken(
            user_id=user_id,
            token_hash="hashed_token_here",
            expires_at=expires_at,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        assert token.user_id == user_id
        assert token.token_hash == "hashed_token_here"
        assert token.expires_at == expires_at
        assert token.used_at is None
        assert token.ip_address == "192.168.1.1"
        assert token.user_agent == "Mozilla/5.0"

    def test_is_expired_property_when_not_expired(self):
        """Test is_expired property returns False for valid token.

        Verifies that:
        - is_expired returns False
        - expires_at in future
        - Token can be used for password reset
        """
        future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
        )

        assert token.is_expired is False

    def test_is_expired_property_when_expired(self):
        """Test is_expired property returns True for expired token.

        Verifies that:
        - is_expired returns True
        - expires_at in past
        - User must request new password reset
        """
        past_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=past_time,
        )

        assert token.is_expired is True

    def test_is_used_property_when_not_used(self):
        """Test is_used property returns False for unused token.

        Verifies that:
        - is_used returns False
        - used_at is None
        - Token available for password reset
        """
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            used_at=None,
        )

        assert token.is_used is False

    def test_is_used_property_when_used(self):
        """Test is_used property returns True for used token.

        Verifies that:
        - is_used returns True
        - used_at timestamp set
        - Token cannot be reused (single-use)
        """
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            used_at=datetime.now(timezone.utc),
        )

        assert token.is_used is True

    def test_is_valid_property_when_valid(self):
        """Test is_valid property for usable token.

        Verifies that:
        - is_valid returns True
        - Token not expired and not used
        - Token can reset password
        """
        future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
            used_at=None,
        )

        assert token.is_valid is True

    def test_is_valid_property_when_expired(self):
        """Test is_valid property rejects expired token.

        Verifies that:
        - is_valid returns False
        - Expiry invalidates token even if not used
        """
        past_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=past_time,
            used_at=None,
        )

        assert token.is_valid is False

    def test_is_valid_property_when_used(self):
        """Test is_valid property rejects used token.

        Verifies that:
        - is_valid returns False
        - Usage invalidates token even if not expired
        - Security: prevents token reuse attacks
        """
        future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
            used_at=datetime.now(timezone.utc),
        )

        assert token.is_valid is False

    def test_mark_as_used_method(self):
        """Test mark_as_used() method marks token as consumed.

        Verifies that:
        - used_at timestamp set to current time
        - is_used returns True
        - Token becomes invalid

        Note:
            Called after successful password reset.
        """
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )

        before_mark = datetime.now(timezone.utc)
        token.mark_as_used()
        after_mark = datetime.now(timezone.utc) + timedelta(seconds=1)

        assert token.used_at is not None
        assert before_mark <= token.used_at <= after_mark
        assert token.is_used is True

    def test_timezone_aware_datetime_fields(self):
        """Test datetime fields are timezone-aware (TIMESTAMPTZ).

        Verifies that:
        - expires_at has tzinfo
        - used_at has tzinfo
        - PCI-DSS compliance requirement met
        """
        now = datetime.now(timezone.utc)
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=now,
            used_at=now,
        )

        assert token.expires_at.tzinfo is not None
        assert token.used_at.tzinfo is not None
