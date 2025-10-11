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
    """Test timezone-aware datetime handling across all models.

    Validates P0 requirement: All datetimes must be timezone-aware (TIMESTAMPTZ).
    Tests datetime conversion, storage, and property calculations with timezones.
    """

    def test_user_model_created_at_is_timezone_aware(self):
        """Test User model created_at field is timezone-aware.

        Verifies that:
        - created_at automatically set on instantiation
        - created_at has tzinfo (timezone-aware)
        - Timezone is UTC
        - TIMESTAMPTZ compliance

        Note:
            P0 requirement: All timestamps must be timezone-aware.
        """
        user = User(email="test@example.com", name="Test User")

        assert user.created_at is not None
        assert user.created_at.tzinfo is not None
        assert user.created_at.tzinfo == timezone.utc

    def test_user_model_last_login_accepts_timezone_aware(self):
        """Test User model accepts timezone-aware datetime for last_login_at.

        Verifies that:
        - last_login_at accepts timezone-aware datetime
        - Timezone information preserved
        - Stored as UTC

        Note:
            Ensures no timezone data loss during assignment.
        """
        now = datetime.now(timezone.utc)
        user = User(email="test@example.com", name="Test User", last_login_at=now)

        assert user.last_login_at is not None
        assert user.last_login_at.tzinfo is not None
        assert user.last_login_at.tzinfo == timezone.utc

    def test_user_model_converts_naive_datetime_to_aware(self):
        """Test naive datetimes automatically converted to timezone-aware.

        Verifies that:
        - Naive datetime (no tzinfo) accepted
        - Automatically converted to UTC
        - tzinfo is set to timezone.utc
        - No errors for backward compatibility

        Note:
            Safety feature: ensures all datetimes are timezone-aware.
        """
        # Create naive datetime
        naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        user = User(email="test@example.com", name="Test User", last_login_at=naive_dt)

        # Should be converted to timezone-aware UTC
        assert user.last_login_at.tzinfo is not None
        assert user.last_login_at.tzinfo == timezone.utc

    def test_provider_model_timestamps_are_timezone_aware(self):
        """Test Provider model timestamps are timezone-aware.

        Verifies that:
        - created_at is UTC timezone-aware
        - updated_at is None or UTC timezone-aware
        - Automatic timestamp generation works correctly

        Note:
            Provider model inherits timestamp behavior.
        """
        provider = Provider(user_id=uuid4(), provider_key="schwab", alias="Test Schwab")

        assert provider.created_at.tzinfo == timezone.utc
        assert provider.updated_at is None or provider.updated_at.tzinfo == timezone.utc

    def test_provider_connection_timestamps_are_timezone_aware(self):
        """Test ProviderConnection model timestamps are timezone-aware.

        Verifies that:
        - created_at is UTC timezone-aware
        - mark_connected() sets connected_at as UTC
        - mark_connected() sets next_sync_at as UTC
        - All method-generated timestamps are timezone-aware

        Note:
            Tests both automatic and method-generated timestamps.
        """
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
        """Test mark_sync_successful method sets timezone-aware datetimes.

        Verifies that:
        - last_sync_at set to UTC datetime
        - next_sync_at calculated with UTC timezone
        - Method always generates timezone-aware timestamps

        Note:
            Sync scheduling depends on accurate timezone handling.
        """
        connection = ProviderConnection(
            provider_id=uuid4(), status=ProviderStatus.ACTIVE
        )

        connection.mark_sync_successful()

        assert connection.last_sync_at is not None
        assert connection.last_sync_at.tzinfo == timezone.utc
        assert connection.next_sync_at is not None
        assert connection.next_sync_at.tzinfo == timezone.utc

    def test_provider_token_expires_at_is_timezone_aware(self):
        """Test ProviderToken expires_at field is timezone-aware.

        Verifies that:
        - expires_at accepts UTC datetime
        - Timezone information preserved
        - Token expiry calculations use UTC

        Note:
            Critical for automatic token refresh logic.
        """
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        token = ProviderToken(
            connection_id=uuid4(),
            access_token_encrypted="encrypted_token",
            expires_at=expires_at,
        )

        assert token.expires_at is not None
        assert token.expires_at.tzinfo == timezone.utc

    def test_provider_token_update_tokens_uses_timezone_aware(self):
        """Test update_tokens method sets timezone-aware datetimes.

        Verifies that:
        - expires_at calculated with UTC timezone
        - last_refreshed_at set to UTC datetime
        - Token rotation preserves timezone awareness

        Note:
            Method called during OAuth token refresh.
        """
        token = ProviderToken(connection_id=uuid4(), access_token_encrypted="old_token")

        token.update_tokens(access_token_encrypted="new_token", expires_in=3600)

        assert token.expires_at is not None
        assert token.expires_at.tzinfo == timezone.utc
        assert token.last_refreshed_at is not None
        assert token.last_refreshed_at.tzinfo == timezone.utc

    def test_provider_token_is_expired_works_with_timezone_aware(self):
        """Test is_expired property works correctly with timezone-aware datetimes.

        Verifies that:
        - Expired token (past UTC datetime) returns True
        - Valid token (future UTC datetime) returns False
        - Timezone-aware comparison works correctly
        - No naive datetime comparison errors

        Note:
            Automatic token refresh depends on accurate expiry detection.
        """
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
        """Test is_expiring_soon property with timezone-aware datetimes.

        Verifies that:
        - Token expiring in 3 minutes returns True
        - Token expiring in 10 minutes returns False
        - 5-minute threshold applied correctly
        - Timezone-aware timedelta calculations work

        Note:
            Proactive refresh triggered when is_expiring_soon is True.
        """
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
        """Test soft_delete method sets timezone-aware datetime.

        Verifies that:
        - deleted_at set to UTC datetime
        - is_deleted property returns True
        - Soft delete timestamp is timezone-aware

        Note:
            Soft delete preserves audit trail with accurate timestamps.
        """
        user = User(email="test@example.com", name="Test User")

        user.soft_delete()

        assert user.deleted_at is not None
        assert user.deleted_at.tzinfo == timezone.utc
        assert user.is_deleted is True

    def test_different_timezone_converted_to_utc(self):
        """Test datetimes from different timezones converted to UTC.

        Verifies that:
        - PST (UTC-8) datetime accepted
        - Automatically converted to UTC
        - Time adjusted correctly (12:00 PST = 20:00 UTC)
        - Timezone normalization works across all zones

        Note:
            CRITICAL: All datetimes stored as UTC for global consistency.
        """
        # Create datetime in PST (UTC-8)
        from datetime import timezone as tz

        pst = tz(timedelta(hours=-8))
        pst_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=pst)

        user = User(email="test@example.com", name="Test User", last_login_at=pst_time)

        # Should be converted to UTC
        assert user.last_login_at.tzinfo == timezone.utc
        # Time should be adjusted (12:00 PST = 20:00 UTC)
        assert user.last_login_at.hour == 20
