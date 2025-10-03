"""Tests for timezone-aware datetime handling in models.

This module verifies that all datetime fields in our models properly handle
timezone-aware datetimes and store them as TIMESTAMPTZ in PostgreSQL.
"""

from datetime import datetime, timezone, timedelta
from uuid import uuid4

from src.models.user import User
from src.models.provider import (
    Provider,
    ProviderConnection,
    ProviderToken,
    ProviderStatus,
)


class TestTimezoneAwareDatetimes:
    """Test timezone-aware datetime handling across all models."""

    def test_user_model_created_at_is_timezone_aware(self):
        """Verify User model's created_at is timezone-aware."""
        user = User(email="test@example.com", name="Test User")

        assert user.created_at is not None
        assert user.created_at.tzinfo is not None
        assert user.created_at.tzinfo == timezone.utc

    def test_user_model_last_login_accepts_timezone_aware(self):
        """Verify User model's last_login accepts timezone-aware datetime."""
        now = datetime.now(timezone.utc)
        user = User(email="test@example.com", name="Test User", last_login=now)

        assert user.last_login is not None
        assert user.last_login.tzinfo is not None
        assert user.last_login.tzinfo == timezone.utc

    def test_user_model_converts_naive_datetime_to_aware(self):
        """Verify naive datetimes are converted to timezone-aware."""
        # Create naive datetime
        naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        user = User(email="test@example.com", name="Test User", last_login=naive_dt)

        # Should be converted to timezone-aware UTC
        assert user.last_login.tzinfo is not None
        assert user.last_login.tzinfo == timezone.utc

    def test_provider_model_timestamps_are_timezone_aware(self):
        """Verify Provider model timestamps are timezone-aware."""
        provider = Provider(user_id=uuid4(), provider_key="schwab", alias="Test Schwab")

        assert provider.created_at.tzinfo == timezone.utc
        assert provider.updated_at is None or provider.updated_at.tzinfo == timezone.utc

    def test_provider_connection_timestamps_are_timezone_aware(self):
        """Verify ProviderConnection model timestamps are timezone-aware."""
        connection = ProviderConnection(
            provider_id=uuid4(), status=ProviderStatus.ACTIVE
        )

        assert connection.created_at.tzinfo == timezone.utc

        # Test mark_connected method sets timezone-aware datetime
        connection.mark_connected()
        assert connection.connected_at is not None
        assert connection.connected_at.tzinfo == timezone.utc
        assert connection.next_sync_at is not None
        assert connection.next_sync_at.tzinfo == timezone.utc

    def test_provider_connection_mark_sync_successful_uses_timezone_aware(self):
        """Verify mark_sync_successful sets timezone-aware datetime."""
        connection = ProviderConnection(
            provider_id=uuid4(), status=ProviderStatus.ACTIVE
        )

        connection.mark_sync_successful()

        assert connection.last_sync_at is not None
        assert connection.last_sync_at.tzinfo == timezone.utc
        assert connection.next_sync_at is not None
        assert connection.next_sync_at.tzinfo == timezone.utc

    def test_provider_token_expires_at_is_timezone_aware(self):
        """Verify ProviderToken expires_at is timezone-aware."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        token = ProviderToken(
            connection_id=uuid4(),
            access_token_encrypted="encrypted_token",
            expires_at=expires_at,
        )

        assert token.expires_at is not None
        assert token.expires_at.tzinfo == timezone.utc

    def test_provider_token_update_tokens_uses_timezone_aware(self):
        """Verify update_tokens method sets timezone-aware datetimes."""
        token = ProviderToken(connection_id=uuid4(), access_token_encrypted="old_token")

        token.update_tokens(access_token_encrypted="new_token", expires_in=3600)

        assert token.expires_at is not None
        assert token.expires_at.tzinfo == timezone.utc
        assert token.last_refreshed_at is not None
        assert token.last_refreshed_at.tzinfo == timezone.utc

    def test_provider_token_is_expired_works_with_timezone_aware(self):
        """Verify is_expired property works correctly with timezone-aware datetimes."""
        # Expired token
        expired_token = ProviderToken(
            connection_id=uuid4(),
            access_token_encrypted="expired_token",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        assert expired_token.is_expired is True

        # Valid token
        valid_token = ProviderToken(
            connection_id=uuid4(),
            access_token_encrypted="valid_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert valid_token.is_expired is False

    def test_provider_token_is_expiring_soon_works_with_timezone_aware(self):
        """Verify is_expiring_soon property works correctly."""
        # Token expiring in 3 minutes
        expiring_token = ProviderToken(
            connection_id=uuid4(),
            access_token_encrypted="expiring_token",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=3),
        )

        assert expiring_token.is_expiring_soon is True

        # Token expiring in 10 minutes
        valid_token = ProviderToken(
            connection_id=uuid4(),
            access_token_encrypted="valid_token",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )

        assert valid_token.is_expiring_soon is False

    def test_soft_delete_uses_timezone_aware_datetime(self):
        """Verify soft_delete method sets timezone-aware datetime."""
        user = User(email="test@example.com", name="Test User")

        user.soft_delete()

        assert user.deleted_at is not None
        assert user.deleted_at.tzinfo == timezone.utc
        assert user.is_deleted is True

    def test_different_timezone_converted_to_utc(self):
        """Verify datetimes from different timezones are converted to UTC."""
        # Create datetime in PST (UTC-8)
        from datetime import timezone as tz

        pst = tz(timedelta(hours=-8))
        pst_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=pst)

        user = User(email="test@example.com", name="Test User", last_login=pst_time)

        # Should be converted to UTC
        assert user.last_login.tzinfo == timezone.utc
        # Time should be adjusted (12:00 PST = 20:00 UTC)
        assert user.last_login.hour == 20
