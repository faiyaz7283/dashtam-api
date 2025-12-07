"""Unit tests for ProviderCredentials value object.

Tests cover:
- Value object creation and validation
- Immutability (frozen dataclass)
- Expiry checking methods (is_expired, is_expiring_soon, time_until_expiry)
- Refresh support checking
- String representations (security: no encrypted data)

Architecture:
- Unit tests for domain value object (no dependencies)
- Tests pure validation logic
- Validates immutability constraints
"""

from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from src.domain.enums.credential_type import CredentialType
from src.domain.value_objects.provider_credentials import ProviderCredentials
from tests.conftest import create_credentials


@pytest.mark.unit
class TestProviderCredentialsCreation:
    """Test ProviderCredentials value object creation."""

    def test_credentials_created_with_all_fields(self):
        """Test credentials can be created with all fields."""
        # Arrange
        encrypted_data = b"encrypted_oauth_tokens"
        credential_type = CredentialType.OAUTH2
        expires_at = datetime.now(UTC) + timedelta(hours=1)

        # Act
        credentials = ProviderCredentials(
            encrypted_data=encrypted_data,
            credential_type=credential_type,
            expires_at=expires_at,
        )

        # Assert
        assert credentials.encrypted_data == encrypted_data
        assert credentials.credential_type == credential_type
        assert credentials.expires_at == expires_at

    def test_credentials_created_without_expiration(self):
        """Test credentials can be created without expiration (never expires)."""
        # Act
        credentials = create_credentials(
            credential_type=CredentialType.API_KEY,
            expires_at=None,
        )

        # Assert
        assert credentials.expires_at is None

    def test_credentials_created_with_each_credential_type(self):
        """Test credentials can be created with each CredentialType."""
        for cred_type in CredentialType:
            # Act
            credentials = create_credentials(credential_type=cred_type)

            # Assert
            assert credentials.credential_type == cred_type

    def test_credentials_raises_error_for_empty_encrypted_data(self):
        """Test creation fails with empty encrypted_data."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            create_credentials(encrypted_data=b"")

        assert "encrypted_data cannot be empty" in str(exc_info.value)

    def test_credentials_raises_error_for_non_bytes_encrypted_data(self):
        """Test creation fails with non-bytes encrypted_data."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            ProviderCredentials(
                encrypted_data="not bytes",  # type: ignore[arg-type]
                credential_type=CredentialType.OAUTH2,
            )

        assert "encrypted_data must be bytes" in str(exc_info.value)

    def test_credentials_raises_error_for_invalid_credential_type(self):
        """Test creation fails with invalid credential_type."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            ProviderCredentials(
                encrypted_data=b"data",
                credential_type="oauth2",  # type: ignore[arg-type]
            )

        assert "credential_type must be a CredentialType enum" in str(exc_info.value)

    def test_credentials_raises_error_for_naive_datetime(self):
        """Test creation fails with naive (non-timezone-aware) datetime."""
        # Arrange
        naive_datetime = datetime.now()  # No timezone  # noqa: DTZ005

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            create_credentials(expires_at=naive_datetime)

        assert "expires_at must be timezone-aware" in str(exc_info.value)


@pytest.mark.unit
class TestProviderCredentialsImmutability:
    """Test ProviderCredentials immutability (frozen dataclass)."""

    def test_credentials_are_frozen(self):
        """Test credentials cannot be modified after creation."""
        # Arrange
        credentials = create_credentials()

        # Act & Assert
        with pytest.raises(AttributeError):
            credentials.encrypted_data = b"new_data"  # type: ignore[misc]

    def test_credentials_credential_type_is_frozen(self):
        """Test credential_type cannot be modified."""
        # Arrange
        credentials = create_credentials()

        # Act & Assert
        with pytest.raises(AttributeError):
            credentials.credential_type = CredentialType.API_KEY  # type: ignore[misc]

    def test_credentials_expires_at_is_frozen(self):
        """Test expires_at cannot be modified."""
        # Arrange
        credentials = create_credentials(expires_at=datetime.now(UTC))

        # Act & Assert
        with pytest.raises(AttributeError):
            credentials.expires_at = datetime.now(UTC) + timedelta(hours=1)  # type: ignore[misc]


@pytest.mark.unit
class TestProviderCredentialsIsExpired:
    """Test ProviderCredentials.is_expired() method."""

    def test_is_expired_false_when_no_expiration(self):
        """Test is_expired returns False when no expiration set."""
        # Arrange
        credentials = create_credentials(expires_at=None)

        # Assert
        assert credentials.is_expired() is False

    @freeze_time("2024-01-01 12:00:00")
    def test_is_expired_false_when_future_expiration(self):
        """Test is_expired returns False when expiration is in future."""
        # Arrange - expires 1 hour in future
        credentials = create_credentials(
            expires_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC)
        )

        # Assert
        assert credentials.is_expired() is False

    @freeze_time("2024-01-01 12:00:00")
    def test_is_expired_true_when_past_expiration(self):
        """Test is_expired returns True when expiration is in past."""
        # Arrange - expired 1 hour ago
        credentials = create_credentials(
            expires_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=UTC)
        )

        # Assert
        assert credentials.is_expired() is True

    @freeze_time("2024-01-01 12:00:00")
    def test_is_expired_true_at_exact_expiration(self):
        """Test is_expired returns True at exact expiration time."""
        # Arrange - expires exactly now
        credentials = create_credentials(
            expires_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        )

        # Assert
        assert credentials.is_expired() is True


@pytest.mark.unit
class TestProviderCredentialsIsExpiringSoon:
    """Test ProviderCredentials.is_expiring_soon() method."""

    def test_is_expiring_soon_false_when_no_expiration(self):
        """Test is_expiring_soon returns False when no expiration set."""
        # Arrange
        credentials = create_credentials(expires_at=None)

        # Assert
        assert credentials.is_expiring_soon() is False

    @freeze_time("2024-01-01 12:00:00")
    def test_is_expiring_soon_false_when_far_from_expiry(self):
        """Test is_expiring_soon returns False when expiration is far away."""
        # Arrange - expires 1 hour from now (outside 5 min threshold)
        credentials = create_credentials(
            expires_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC)
        )

        # Assert
        assert credentials.is_expiring_soon() is False

    @freeze_time("2024-01-01 12:00:00")
    def test_is_expiring_soon_true_within_default_threshold(self):
        """Test is_expiring_soon returns True within 5 minute threshold."""
        # Arrange - expires 3 minutes from now (within default 5 min threshold)
        credentials = create_credentials(
            expires_at=datetime(2024, 1, 1, 12, 3, 0, tzinfo=UTC)
        )

        # Assert
        assert credentials.is_expiring_soon() is True

    @freeze_time("2024-01-01 12:00:00")
    def test_is_expiring_soon_false_outside_default_threshold(self):
        """Test is_expiring_soon returns False just outside threshold."""
        # Arrange - expires 6 minutes from now (outside default 5 min threshold)
        credentials = create_credentials(
            expires_at=datetime(2024, 1, 1, 12, 6, 0, tzinfo=UTC)
        )

        # Assert
        assert credentials.is_expiring_soon() is False

    @freeze_time("2024-01-01 12:00:00")
    def test_is_expiring_soon_with_custom_threshold(self):
        """Test is_expiring_soon with custom threshold."""
        # Arrange - expires 8 minutes from now
        credentials = create_credentials(
            expires_at=datetime(2024, 1, 1, 12, 8, 0, tzinfo=UTC)
        )

        # Assert - 10 minute threshold should capture it
        assert credentials.is_expiring_soon(threshold=timedelta(minutes=10)) is True

    @freeze_time("2024-01-01 12:00:00")
    def test_is_expiring_soon_true_when_already_expired(self):
        """Test is_expiring_soon returns True when already expired."""
        # Arrange - expired 5 minutes ago
        credentials = create_credentials(
            expires_at=datetime(2024, 1, 1, 11, 55, 0, tzinfo=UTC)
        )

        # Assert
        assert credentials.is_expiring_soon() is True


@pytest.mark.unit
class TestProviderCredentialsTimeUntilExpiry:
    """Test ProviderCredentials.time_until_expiry() method."""

    def test_time_until_expiry_none_when_no_expiration(self):
        """Test time_until_expiry returns None when no expiration set."""
        # Arrange
        credentials = create_credentials(expires_at=None)

        # Assert
        assert credentials.time_until_expiry() is None

    @freeze_time("2024-01-01 12:00:00")
    def test_time_until_expiry_positive_when_not_expired(self):
        """Test time_until_expiry returns positive timedelta when valid."""
        # Arrange - expires 1 hour from now
        credentials = create_credentials(
            expires_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=UTC)
        )

        # Act
        remaining = credentials.time_until_expiry()

        # Assert
        assert remaining is not None
        assert remaining.total_seconds() == 3600  # Exactly 1 hour

    @freeze_time("2024-01-01 12:00:00")
    def test_time_until_expiry_zero_when_expired(self):
        """Test time_until_expiry returns zero timedelta when expired."""
        # Arrange - expired 1 hour ago
        credentials = create_credentials(
            expires_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=UTC)
        )

        # Act
        remaining = credentials.time_until_expiry()

        # Assert
        assert remaining is not None
        assert remaining.total_seconds() == 0


@pytest.mark.unit
class TestProviderCredentialsSupportsRefresh:
    """Test ProviderCredentials.supports_refresh() method."""

    def test_supports_refresh_true_for_oauth2(self):
        """Test supports_refresh returns True for OAuth2."""
        # Arrange
        credentials = create_credentials(credential_type=CredentialType.OAUTH2)

        # Assert
        assert credentials.supports_refresh() is True

    def test_supports_refresh_true_for_link_token(self):
        """Test supports_refresh returns True for Plaid link tokens."""
        # Arrange
        credentials = create_credentials(credential_type=CredentialType.LINK_TOKEN)

        # Assert
        assert credentials.supports_refresh() is True

    def test_supports_refresh_false_for_api_key(self):
        """Test supports_refresh returns False for API keys."""
        # Arrange
        credentials = create_credentials(credential_type=CredentialType.API_KEY)

        # Assert
        assert credentials.supports_refresh() is False

    def test_supports_refresh_false_for_certificate(self):
        """Test supports_refresh returns False for certificates."""
        # Arrange
        credentials = create_credentials(credential_type=CredentialType.CERTIFICATE)

        # Assert
        assert credentials.supports_refresh() is False

    def test_supports_refresh_false_for_custom(self):
        """Test supports_refresh returns False for custom credentials."""
        # Arrange
        credentials = create_credentials(credential_type=CredentialType.CUSTOM)

        # Assert
        assert credentials.supports_refresh() is False


@pytest.mark.unit
class TestProviderCredentialsStringRepresentations:
    """Test ProviderCredentials __repr__ and __str__ methods."""

    def test_repr_does_not_include_encrypted_data(self):
        """Test __repr__ does not expose encrypted data."""
        # Arrange
        credentials = create_credentials(
            encrypted_data=b"super_secret_oauth_tokens",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        # Act
        repr_str = repr(credentials)

        # Assert
        assert "super_secret_oauth_tokens" not in repr_str
        assert "<25 bytes>" in repr_str  # Shows length instead

    def test_repr_includes_credential_type(self):
        """Test __repr__ includes credential type."""
        # Arrange
        credentials = create_credentials(credential_type=CredentialType.API_KEY)

        # Act
        repr_str = repr(credentials)

        # Assert
        assert "api_key" in repr_str

    def test_repr_includes_expiration(self):
        """Test __repr__ includes expiration time."""
        # Arrange
        expires_at = datetime.now(UTC) + timedelta(hours=1)
        credentials = create_credentials(expires_at=expires_at)

        # Act
        repr_str = repr(credentials)

        # Assert
        assert expires_at.isoformat() in repr_str

    def test_repr_handles_none_expiration(self):
        """Test __repr__ handles None expiration."""
        # Arrange
        credentials = create_credentials(expires_at=None)

        # Act
        repr_str = repr(credentials)

        # Assert
        assert "expires_at=None" in repr_str

    def test_str_does_not_include_encrypted_data(self):
        """Test __str__ does not expose encrypted data."""
        # Arrange
        credentials = create_credentials(encrypted_data=b"super_secret_oauth_tokens")

        # Act
        str_result = str(credentials)

        # Assert
        assert "super_secret_oauth_tokens" not in str_result

    def test_str_shows_valid_status_when_not_expired(self):
        """Test __str__ shows 'valid' for non-expired credentials."""
        # Arrange
        credentials = create_credentials(
            expires_at=datetime.now(UTC) + timedelta(hours=1)
        )

        # Act
        str_result = str(credentials)

        # Assert
        assert "valid" in str_result

    def test_str_shows_expired_status_when_expired(self):
        """Test __str__ shows 'expired' for expired credentials."""
        # Arrange
        credentials = create_credentials(
            expires_at=datetime.now(UTC) - timedelta(hours=1)
        )

        # Act
        str_result = str(credentials)

        # Assert
        assert "expired" in str_result

    def test_str_includes_credential_type(self):
        """Test __str__ includes credential type."""
        # Arrange
        credentials = create_credentials(credential_type=CredentialType.CERTIFICATE)

        # Act
        str_result = str(credentials)

        # Assert
        assert "certificate" in str_result


@pytest.mark.unit
class TestProviderCredentialsEquality:
    """Test ProviderCredentials equality (frozen dataclass behavior)."""

    def test_equal_credentials_are_equal(self):
        """Test identical credentials are equal."""
        # Arrange
        expires_at = datetime.now(UTC) + timedelta(hours=1)
        cred1 = ProviderCredentials(
            encrypted_data=b"same_data",
            credential_type=CredentialType.OAUTH2,
            expires_at=expires_at,
        )
        cred2 = ProviderCredentials(
            encrypted_data=b"same_data",
            credential_type=CredentialType.OAUTH2,
            expires_at=expires_at,
        )

        # Assert
        assert cred1 == cred2

    def test_different_encrypted_data_not_equal(self):
        """Test credentials with different data are not equal."""
        # Arrange
        cred1 = create_credentials(encrypted_data=b"data1")
        cred2 = create_credentials(encrypted_data=b"data2")

        # Assert
        assert cred1 != cred2

    def test_different_credential_type_not_equal(self):
        """Test credentials with different types are not equal."""
        # Arrange
        cred1 = create_credentials(credential_type=CredentialType.OAUTH2)
        cred2 = create_credentials(credential_type=CredentialType.API_KEY)

        # Assert
        assert cred1 != cred2

    def test_different_expiration_not_equal(self):
        """Test credentials with different expiration are not equal."""
        # Arrange
        now = datetime.now(UTC)
        cred1 = create_credentials(expires_at=now + timedelta(hours=1))
        cred2 = create_credentials(expires_at=now + timedelta(hours=2))

        # Assert
        assert cred1 != cred2

    def test_credentials_hashable(self):
        """Test credentials can be used in sets and as dict keys."""
        # Arrange
        expires_at = datetime.now(UTC) + timedelta(hours=1)
        cred1 = create_credentials(encrypted_data=b"data1", expires_at=expires_at)
        cred2 = create_credentials(encrypted_data=b"data2", expires_at=expires_at)
        cred3 = create_credentials(
            encrypted_data=b"data1", expires_at=expires_at
        )  # Same as cred1

        # Act
        cred_set = {cred1, cred2, cred3}

        # Assert
        assert len(cred_set) == 2  # cred1 and cred3 are equal


@pytest.mark.unit
class TestCredentialTypeEnumMethods:
    """Test CredentialType enum helper methods."""

    def test_values_returns_all_types(self):
        """Test CredentialType.values() returns all type strings."""
        # Act
        values = CredentialType.values()

        # Assert
        assert len(values) == 5
        assert "oauth2" in values
        assert "api_key" in values
        assert "link_token" in values
        assert "certificate" in values
        assert "custom" in values

    def test_is_valid_true_for_valid_type(self):
        """Test is_valid returns True for valid type string."""
        # Assert
        assert CredentialType.is_valid("oauth2") is True
        assert CredentialType.is_valid("api_key") is True

    def test_is_valid_false_for_invalid_type(self):
        """Test is_valid returns False for invalid type string."""
        # Assert
        assert CredentialType.is_valid("invalid") is False
        assert CredentialType.is_valid("OAUTH2") is False  # Case sensitive

    def test_supports_refresh_returns_correct_types(self):
        """Test supports_refresh returns types that support auto-refresh."""
        # Act
        refresh_types = CredentialType.supports_refresh()

        # Assert
        assert len(refresh_types) == 2
        assert CredentialType.OAUTH2 in refresh_types
        assert CredentialType.LINK_TOKEN in refresh_types
        assert CredentialType.API_KEY not in refresh_types

    def test_never_expires_returns_correct_types(self):
        """Test never_expires returns types without expiration."""
        # Act
        no_expire_types = CredentialType.never_expires()

        # Assert
        assert len(no_expire_types) == 2
        assert CredentialType.API_KEY in no_expire_types
        assert CredentialType.CERTIFICATE in no_expire_types
        assert CredentialType.OAUTH2 not in no_expire_types
