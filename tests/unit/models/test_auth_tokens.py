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
    """Test suite for RefreshToken model."""

    def test_refresh_token_creation(self):
        """Test creating a refresh token."""
        user_id = uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        token = RefreshToken(
            user_id=user_id,
            token_hash="hashed_token_here",
            expires_at=expires_at,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        assert token.user_id == user_id
        assert token.token_hash == "hashed_token_here"
        assert token.expires_at == expires_at
        assert token.is_revoked is False
        assert token.revoked_at is None
        assert token.ip_address == "192.168.1.1"
        assert token.user_agent == "Mozilla/5.0"

    def test_is_expired_property_when_not_expired(self):
        """Test is_expired returns False for valid token."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        token = RefreshToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
        )

        assert token.is_expired is False

    def test_is_expired_property_when_expired(self):
        """Test is_expired returns True for expired token."""
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        token = RefreshToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=past_time,
        )

        assert token.is_expired is True

    def test_is_valid_property_when_valid(self):
        """Test is_valid returns True for valid, non-revoked token."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        token = RefreshToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
            is_revoked=False,
        )

        assert token.is_valid is True

    def test_is_valid_property_when_expired(self):
        """Test is_valid returns False for expired token."""
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        token = RefreshToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=past_time,
            is_revoked=False,
        )

        assert token.is_valid is False

    def test_is_valid_property_when_revoked(self):
        """Test is_valid returns False for revoked token."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        token = RefreshToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
            is_revoked=True,
        )

        assert token.is_valid is False

    def test_revoke_method(self):
        """Test revoking a refresh token."""
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
        """Test that datetime fields are timezone-aware."""
        now = datetime.now(timezone.utc)
        token = RefreshToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=now,
            revoked_at=now,
            last_used_at=now,
        )

        assert token.expires_at.tzinfo is not None
        assert token.revoked_at.tzinfo is not None
        assert token.last_used_at.tzinfo is not None


class TestEmailVerificationToken:
    """Test suite for EmailVerificationToken model."""

    def test_email_verification_token_creation(self):
        """Test creating an email verification token."""
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
        """Test is_expired returns False for valid token."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
        )

        assert token.is_expired is False

    def test_is_expired_property_when_expired(self):
        """Test is_expired returns True for expired token."""
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=past_time,
        )

        assert token.is_expired is True

    def test_is_used_property_when_not_used(self):
        """Test is_used returns False when token hasn't been used."""
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            used_at=None,
        )

        assert token.is_used is False

    def test_is_used_property_when_used(self):
        """Test is_used returns True when token has been used."""
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            used_at=datetime.now(timezone.utc),
        )

        assert token.is_used is True

    def test_is_valid_property_when_valid(self):
        """Test is_valid returns True for unused, non-expired token."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
            used_at=None,
        )

        assert token.is_valid is True

    def test_is_valid_property_when_expired(self):
        """Test is_valid returns False for expired token."""
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=past_time,
            used_at=None,
        )

        assert token.is_valid is False

    def test_is_valid_property_when_used(self):
        """Test is_valid returns False for used token."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        token = EmailVerificationToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
            used_at=datetime.now(timezone.utc),
        )

        assert token.is_valid is False

    def test_mark_as_used_method(self):
        """Test marking token as used."""
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
        """Test that datetime fields are timezone-aware."""
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
    """Test suite for PasswordResetToken model."""

    def test_password_reset_token_creation(self):
        """Test creating a password reset token."""
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
        """Test is_expired returns False for valid token."""
        future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
        )

        assert token.is_expired is False

    def test_is_expired_property_when_expired(self):
        """Test is_expired returns True for expired token."""
        past_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=past_time,
        )

        assert token.is_expired is True

    def test_is_used_property_when_not_used(self):
        """Test is_used returns False when token hasn't been used."""
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            used_at=None,
        )

        assert token.is_used is False

    def test_is_used_property_when_used(self):
        """Test is_used returns True when token has been used."""
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            used_at=datetime.now(timezone.utc),
        )

        assert token.is_used is True

    def test_is_valid_property_when_valid(self):
        """Test is_valid returns True for unused, non-expired token."""
        future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
            used_at=None,
        )

        assert token.is_valid is True

    def test_is_valid_property_when_expired(self):
        """Test is_valid returns False for expired token."""
        past_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=past_time,
            used_at=None,
        )

        assert token.is_valid is False

    def test_is_valid_property_when_used(self):
        """Test is_valid returns False for used token."""
        future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=future_time,
            used_at=datetime.now(timezone.utc),
        )

        assert token.is_valid is False

    def test_mark_as_used_method(self):
        """Test marking token as used."""
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
        """Test that datetime fields are timezone-aware."""
        now = datetime.now(timezone.utc)
        token = PasswordResetToken(
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=now,
            used_at=now,
        )

        assert token.expires_at.tzinfo is not None
        assert token.used_at.tzinfo is not None
