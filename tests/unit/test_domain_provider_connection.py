"""Unit tests for ProviderConnection domain entity.

Tests cover:
- Entity creation with all fields
- Query methods (is_connected, needs_reauthentication, can_sync, etc.)
- State transition methods with Result types
- Validation and error handling

Architecture:
- Unit tests for domain entity (no dependencies)
- Tests pure business logic and state machine
- Validates entity invariants and business rules
- All state transitions return Result types (ROP)
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from freezegun import freeze_time
from uuid_extensions import uuid7

from src.core.result import Failure, Success
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.errors.provider_connection_error import ProviderConnectionError
from src.domain.value_objects.provider_credentials import ProviderCredentials
from tests.conftest import create_credentials


@pytest.mark.unit
class TestConnectionStatusEnumMethods:
    """Test ConnectionStatus enum helper methods."""

    def test_values_returns_all_statuses(self):
        """Test ConnectionStatus.values() returns all status strings."""
        # Act
        values = ConnectionStatus.values()

        # Assert
        assert len(values) == 6
        assert "pending" in values
        assert "active" in values
        assert "expired" in values
        assert "revoked" in values
        assert "failed" in values
        assert "disconnected" in values

    def test_is_valid_true_for_valid_status(self):
        """Test is_valid returns True for valid status string."""
        # Assert
        assert ConnectionStatus.is_valid("pending") is True
        assert ConnectionStatus.is_valid("active") is True
        assert ConnectionStatus.is_valid("disconnected") is True

    def test_is_valid_false_for_invalid_status(self):
        """Test is_valid returns False for invalid status string."""
        # Assert
        assert ConnectionStatus.is_valid("invalid") is False
        assert ConnectionStatus.is_valid("ACTIVE") is False  # Case sensitive
        assert ConnectionStatus.is_valid("") is False

    def test_active_states_returns_only_active(self):
        """Test active_states returns only ACTIVE status."""
        # Act
        active = ConnectionStatus.active_states()

        # Assert
        assert len(active) == 1
        assert ConnectionStatus.ACTIVE in active
        assert ConnectionStatus.PENDING not in active

    def test_terminal_states_returns_only_disconnected(self):
        """Test terminal_states returns only DISCONNECTED status."""
        # Act
        terminal = ConnectionStatus.terminal_states()

        # Assert
        assert len(terminal) == 1
        assert ConnectionStatus.DISCONNECTED in terminal
        assert ConnectionStatus.FAILED not in terminal

    def test_needs_reauth_states_returns_correct_statuses(self):
        """Test needs_reauth_states returns expired, revoked, and failed."""
        # Act
        needs_reauth = ConnectionStatus.needs_reauth_states()

        # Assert
        assert len(needs_reauth) == 3
        assert ConnectionStatus.EXPIRED in needs_reauth
        assert ConnectionStatus.REVOKED in needs_reauth
        assert ConnectionStatus.FAILED in needs_reauth
        assert ConnectionStatus.ACTIVE not in needs_reauth


def create_connection(
    connection_id: UUID | None = None,
    user_id: UUID | None = None,
    provider_id: UUID | None = None,
    provider_slug: str = "schwab",
    alias: str | None = None,
    status: ConnectionStatus = ConnectionStatus.PENDING,
    credentials: ProviderCredentials | None = None,
    connected_at: datetime | None = None,
    last_sync_at: datetime | None = None,
) -> ProviderConnection:
    """Helper to create ProviderConnection entities for testing."""
    return ProviderConnection(
        id=connection_id or uuid7(),
        user_id=user_id or uuid7(),
        provider_id=provider_id or uuid7(),
        provider_slug=provider_slug,
        alias=alias,
        status=status,
        credentials=credentials,
        connected_at=connected_at,
        last_sync_at=last_sync_at,
    )


@pytest.mark.unit
class TestProviderConnectionCreation:
    """Test ProviderConnection entity creation."""

    def test_connection_created_with_all_required_fields(self):
        """Test connection can be created with all required fields."""
        # Arrange
        connection_id = uuid7()
        user_id = uuid7()
        provider_id = uuid7()

        # Act
        connection = ProviderConnection(
            id=connection_id,
            user_id=user_id,
            provider_id=provider_id,
            provider_slug="schwab",
            status=ConnectionStatus.PENDING,
        )

        # Assert
        assert connection.id == connection_id
        assert isinstance(connection.id, UUID)
        assert connection.user_id == user_id
        assert connection.provider_id == provider_id
        assert connection.provider_slug == "schwab"
        assert connection.status == ConnectionStatus.PENDING
        assert connection.alias is None
        assert connection.credentials is None
        assert connection.connected_at is None
        assert connection.last_sync_at is None
        assert connection.created_at is not None
        assert connection.updated_at is not None

    def test_connection_created_with_optional_alias(self):
        """Test connection can be created with alias."""
        # Act
        connection = create_connection(alias="My Schwab IRA")

        # Assert
        assert connection.alias == "My Schwab IRA"

    def test_connection_created_with_active_status_and_credentials(self):
        """Test active connection requires credentials."""
        # Arrange
        credentials = create_credentials()

        # Act
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Assert
        assert connection.status == ConnectionStatus.ACTIVE
        assert connection.credentials is not None

    def test_connection_raises_error_for_empty_provider_slug(self):
        """Test creation fails with empty provider_slug."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            create_connection(provider_slug="")

        assert ProviderConnectionError.INVALID_PROVIDER_SLUG in str(exc_info.value)

    def test_connection_raises_error_for_long_provider_slug(self):
        """Test creation fails with provider_slug > 50 chars."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            create_connection(provider_slug="x" * 51)

        assert ProviderConnectionError.INVALID_PROVIDER_SLUG in str(exc_info.value)

    def test_connection_raises_error_for_long_alias(self):
        """Test creation fails with alias > 100 chars."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            create_connection(alias="x" * 101)

        assert ProviderConnectionError.INVALID_ALIAS in str(exc_info.value)

    def test_connection_raises_error_for_active_without_credentials(self):
        """Test creation fails for ACTIVE status without credentials."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            create_connection(status=ConnectionStatus.ACTIVE, credentials=None)

        assert ProviderConnectionError.ACTIVE_WITHOUT_CREDENTIALS in str(exc_info.value)


@pytest.mark.unit
class TestProviderConnectionIsConnected:
    """Test ProviderConnection.is_connected() query method."""

    def test_is_connected_true_when_active_with_credentials(self):
        """Test is_connected returns True for ACTIVE with credentials."""
        # Arrange
        credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Assert
        assert connection.is_connected() is True

    def test_is_connected_false_when_pending(self):
        """Test is_connected returns False for PENDING status."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.PENDING)

        # Assert
        assert connection.is_connected() is False

    def test_is_connected_false_when_expired(self):
        """Test is_connected returns False for EXPIRED status."""
        # Arrange
        credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )
        # Manually set to expired (simulating state after mark_expired)
        connection.status = ConnectionStatus.EXPIRED

        # Assert
        assert connection.is_connected() is False

    def test_is_connected_false_when_disconnected(self):
        """Test is_connected returns False for DISCONNECTED status."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.DISCONNECTED)

        # Assert
        assert connection.is_connected() is False


@pytest.mark.unit
class TestProviderConnectionNeedsReauthentication:
    """Test ProviderConnection.needs_reauthentication() query method."""

    def test_needs_reauthentication_false_when_active(self):
        """Test needs_reauthentication returns False for ACTIVE."""
        # Arrange
        credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Assert
        assert connection.needs_reauthentication() is False

    def test_needs_reauthentication_true_when_expired(self):
        """Test needs_reauthentication returns True for EXPIRED."""
        # Arrange
        credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )
        connection.status = ConnectionStatus.EXPIRED

        # Assert
        assert connection.needs_reauthentication() is True

    def test_needs_reauthentication_true_when_revoked(self):
        """Test needs_reauthentication returns True for REVOKED."""
        # Arrange
        credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )
        connection.status = ConnectionStatus.REVOKED

        # Assert
        assert connection.needs_reauthentication() is True

    def test_needs_reauthentication_true_when_failed(self):
        """Test needs_reauthentication returns True for FAILED."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.FAILED)

        # Assert
        assert connection.needs_reauthentication() is True

    def test_needs_reauthentication_false_when_pending(self):
        """Test needs_reauthentication returns False for PENDING."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.PENDING)

        # Assert
        assert connection.needs_reauthentication() is False


@pytest.mark.unit
class TestProviderConnectionCredentialsExpiry:
    """Test credential expiry query methods."""

    def test_is_credentials_expired_false_when_no_credentials(self):
        """Test is_credentials_expired returns False when no credentials."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.PENDING)

        # Assert
        assert connection.is_credentials_expired() is False

    def test_is_credentials_expired_false_when_not_expired(self):
        """Test is_credentials_expired returns False for valid credentials."""
        # Arrange
        credentials = create_credentials(
            expires_at=datetime.now(UTC) + timedelta(hours=1)
        )
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Assert
        assert connection.is_credentials_expired() is False

    def test_is_credentials_expired_true_when_expired(self):
        """Test is_credentials_expired returns True for expired credentials."""
        # Arrange
        credentials = create_credentials(
            expires_at=datetime.now(UTC) - timedelta(hours=1)
        )
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Assert
        assert connection.is_credentials_expired() is True

    def test_is_credentials_expiring_soon_false_when_no_credentials(self):
        """Test is_credentials_expiring_soon returns False when no credentials."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.PENDING)

        # Assert
        assert connection.is_credentials_expiring_soon() is False

    def test_is_credentials_expiring_soon_false_when_not_expiring(self):
        """Test is_credentials_expiring_soon returns False when far from expiry."""
        # Arrange
        credentials = create_credentials(
            expires_at=datetime.now(UTC) + timedelta(hours=1)
        )
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Assert
        assert connection.is_credentials_expiring_soon() is False

    def test_is_credentials_expiring_soon_true_when_near_expiry(self):
        """Test is_credentials_expiring_soon returns True within threshold."""
        # Arrange
        credentials = create_credentials(
            expires_at=datetime.now(UTC) + timedelta(minutes=3)
        )
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Assert
        assert connection.is_credentials_expiring_soon() is True


@pytest.mark.unit
class TestProviderConnectionCanSync:
    """Test ProviderConnection.can_sync() query method."""

    def test_can_sync_true_when_connected_and_not_expired(self):
        """Test can_sync returns True for active connection with valid credentials."""
        # Arrange
        credentials = create_credentials(
            expires_at=datetime.now(UTC) + timedelta(hours=1)
        )
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Assert
        assert connection.can_sync() is True

    def test_can_sync_false_when_not_connected(self):
        """Test can_sync returns False when not connected."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.PENDING)

        # Assert
        assert connection.can_sync() is False

    def test_can_sync_false_when_credentials_expired(self):
        """Test can_sync returns False when credentials expired."""
        # Arrange
        credentials = create_credentials(
            expires_at=datetime.now(UTC) - timedelta(hours=1)
        )
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Assert
        assert connection.can_sync() is False


@pytest.mark.unit
class TestProviderConnectionMarkConnected:
    """Test ProviderConnection.mark_connected() state transition."""

    def test_mark_connected_success_from_pending(self):
        """Test mark_connected succeeds from PENDING status."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.PENDING)
        credentials = create_credentials()
        original_updated_at = connection.updated_at

        # Act
        result = connection.mark_connected(credentials)

        # Assert
        assert isinstance(result, Success)
        assert connection.status == ConnectionStatus.ACTIVE
        assert connection.credentials == credentials
        assert connection.connected_at is not None
        assert connection.updated_at > original_updated_at

    def test_mark_connected_success_from_expired(self):
        """Test mark_connected succeeds from EXPIRED status."""
        # Arrange
        old_credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=old_credentials,
        )
        connection.status = ConnectionStatus.EXPIRED
        new_credentials = create_credentials()

        # Act
        result = connection.mark_connected(new_credentials)

        # Assert
        assert isinstance(result, Success)
        assert connection.status == ConnectionStatus.ACTIVE
        assert connection.credentials == new_credentials

    def test_mark_connected_success_from_revoked(self):
        """Test mark_connected succeeds from REVOKED status."""
        # Arrange
        old_credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=old_credentials,
        )
        connection.status = ConnectionStatus.REVOKED
        new_credentials = create_credentials()

        # Act
        result = connection.mark_connected(new_credentials)

        # Assert
        assert isinstance(result, Success)
        assert connection.status == ConnectionStatus.ACTIVE

    def test_mark_connected_success_from_failed(self):
        """Test mark_connected succeeds from FAILED status."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.FAILED)
        credentials = create_credentials()

        # Act
        result = connection.mark_connected(credentials)

        # Assert
        assert isinstance(result, Success)
        assert connection.status == ConnectionStatus.ACTIVE

    def test_mark_connected_fails_from_active(self):
        """Test mark_connected fails from ACTIVE status."""
        # Arrange
        old_credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=old_credentials,
        )
        new_credentials = create_credentials()

        # Act
        result = connection.mark_connected(new_credentials)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ProviderConnectionError.CANNOT_TRANSITION_TO_ACTIVE

    def test_mark_connected_fails_from_disconnected(self):
        """Test mark_connected fails from DISCONNECTED status."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.DISCONNECTED)
        credentials = create_credentials()

        # Act
        result = connection.mark_connected(credentials)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ProviderConnectionError.CANNOT_TRANSITION_TO_ACTIVE

    def test_mark_connected_fails_with_none_credentials(self):
        """Test mark_connected fails when credentials is None."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.PENDING)

        # Act
        result = connection.mark_connected(None)  # type: ignore[arg-type]

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ProviderConnectionError.CREDENTIALS_REQUIRED

    def test_mark_connected_preserves_connected_at_on_reconnect(self):
        """Test mark_connected preserves connected_at on re-authentication."""
        # Arrange
        original_connected_at = datetime.now(UTC) - timedelta(days=30)
        old_credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=old_credentials,
            connected_at=original_connected_at,
        )
        connection.status = ConnectionStatus.EXPIRED
        new_credentials = create_credentials()

        # Act
        result = connection.mark_connected(new_credentials)

        # Assert
        assert isinstance(result, Success)
        assert connection.connected_at == original_connected_at


@pytest.mark.unit
class TestProviderConnectionMarkDisconnected:
    """Test ProviderConnection.mark_disconnected() state transition."""

    def test_mark_disconnected_success_from_active(self):
        """Test mark_disconnected succeeds from ACTIVE status."""
        # Arrange
        credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Act
        result = connection.mark_disconnected()

        # Assert
        assert isinstance(result, Success)
        assert connection.status == ConnectionStatus.DISCONNECTED
        assert connection.credentials is None

    def test_mark_disconnected_success_from_pending(self):
        """Test mark_disconnected succeeds from any status."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.PENDING)

        # Act
        result = connection.mark_disconnected()

        # Assert
        assert isinstance(result, Success)
        assert connection.status == ConnectionStatus.DISCONNECTED

    def test_mark_disconnected_clears_credentials(self):
        """Test mark_disconnected clears credentials."""
        # Arrange
        credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )
        assert connection.credentials is not None

        # Act
        connection.mark_disconnected()

        # Assert
        assert connection.credentials is None

    def test_mark_disconnected_updates_timestamp(self):
        """Test mark_disconnected updates updated_at."""
        # Arrange - create connection at a fixed time
        initial_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        with freeze_time(initial_time):
            credentials = create_credentials()
            connection = create_connection(
                status=ConnectionStatus.ACTIVE,
                credentials=credentials,
            )
        original_updated_at = connection.updated_at
        assert original_updated_at == initial_time

        # Act - call method at a later time
        later_time = datetime(2024, 1, 1, 12, 0, 1, tzinfo=UTC)
        with freeze_time(later_time):
            connection.mark_disconnected()

        # Assert - timestamp should be updated to the later time
        assert connection.updated_at == later_time
        assert connection.updated_at > original_updated_at


@pytest.mark.unit
class TestProviderConnectionMarkExpired:
    """Test ProviderConnection.mark_expired() state transition."""

    def test_mark_expired_success_from_active(self):
        """Test mark_expired succeeds from ACTIVE status."""
        # Arrange
        credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Act
        result = connection.mark_expired()

        # Assert
        assert isinstance(result, Success)
        assert connection.status == ConnectionStatus.EXPIRED

    def test_mark_expired_preserves_credentials(self):
        """Test mark_expired does NOT clear credentials (may have refresh token)."""
        # Arrange
        credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Act
        connection.mark_expired()

        # Assert
        assert connection.credentials is not None
        assert connection.credentials == credentials

    def test_mark_expired_fails_from_pending(self):
        """Test mark_expired fails from PENDING status."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.PENDING)

        # Act
        result = connection.mark_expired()

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ProviderConnectionError.CANNOT_TRANSITION_TO_EXPIRED

    def test_mark_expired_fails_from_disconnected(self):
        """Test mark_expired fails from DISCONNECTED status."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.DISCONNECTED)

        # Act
        result = connection.mark_expired()

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ProviderConnectionError.CANNOT_TRANSITION_TO_EXPIRED


@pytest.mark.unit
class TestProviderConnectionMarkRevoked:
    """Test ProviderConnection.mark_revoked() state transition."""

    def test_mark_revoked_success_from_active(self):
        """Test mark_revoked succeeds from ACTIVE status."""
        # Arrange
        credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Act
        result = connection.mark_revoked()

        # Assert
        assert isinstance(result, Success)
        assert connection.status == ConnectionStatus.REVOKED

    def test_mark_revoked_preserves_credentials(self):
        """Test mark_revoked does NOT clear credentials (audit trail)."""
        # Arrange
        credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Act
        connection.mark_revoked()

        # Assert
        assert connection.credentials is not None

    def test_mark_revoked_fails_from_pending(self):
        """Test mark_revoked fails from PENDING status."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.PENDING)

        # Act
        result = connection.mark_revoked()

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ProviderConnectionError.CANNOT_TRANSITION_TO_REVOKED


@pytest.mark.unit
class TestProviderConnectionMarkFailed:
    """Test ProviderConnection.mark_failed() state transition."""

    def test_mark_failed_success_from_pending(self):
        """Test mark_failed succeeds from PENDING status."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.PENDING)

        # Act
        result = connection.mark_failed()

        # Assert
        assert isinstance(result, Success)
        assert connection.status == ConnectionStatus.FAILED

    def test_mark_failed_fails_from_active(self):
        """Test mark_failed fails from ACTIVE status."""
        # Arrange
        credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Act
        result = connection.mark_failed()

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ProviderConnectionError.CANNOT_TRANSITION_TO_FAILED

    def test_mark_failed_updates_timestamp(self):
        """Test mark_failed updates updated_at."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.PENDING)
        original_updated_at = connection.updated_at

        # Act
        connection.mark_failed()

        # Assert
        assert connection.updated_at > original_updated_at


@pytest.mark.unit
class TestProviderConnectionUpdateCredentials:
    """Test ProviderConnection.update_credentials() method."""

    def test_update_credentials_success_when_active(self):
        """Test update_credentials succeeds for ACTIVE connection."""
        # Arrange
        old_credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=old_credentials,
        )
        new_credentials = create_credentials(
            encrypted_data=b"new_encrypted_data",
            expires_at=datetime.now(UTC) + timedelta(hours=2),
        )

        # Act
        result = connection.update_credentials(new_credentials)

        # Assert
        assert isinstance(result, Success)
        assert connection.credentials == new_credentials

    def test_update_credentials_fails_when_not_active(self):
        """Test update_credentials fails for non-ACTIVE connection."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.PENDING)
        credentials = create_credentials()

        # Act
        result = connection.update_credentials(credentials)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ProviderConnectionError.NOT_CONNECTED

    def test_update_credentials_fails_with_none(self):
        """Test update_credentials fails when credentials is None."""
        # Arrange
        old_credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=old_credentials,
        )

        # Act
        result = connection.update_credentials(None)  # type: ignore[arg-type]

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ProviderConnectionError.CREDENTIALS_REQUIRED

    def test_update_credentials_updates_timestamp(self):
        """Test update_credentials updates updated_at."""
        # Arrange
        old_credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=old_credentials,
        )
        original_updated_at = connection.updated_at
        new_credentials = create_credentials()

        # Act
        connection.update_credentials(new_credentials)

        # Assert
        assert connection.updated_at > original_updated_at


@pytest.mark.unit
class TestProviderConnectionRecordSync:
    """Test ProviderConnection.record_sync() method."""

    def test_record_sync_success_when_active(self):
        """Test record_sync succeeds for ACTIVE connection."""
        # Arrange
        credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )
        assert connection.last_sync_at is None

        # Act
        result = connection.record_sync()

        # Assert
        assert isinstance(result, Success)
        assert connection.last_sync_at is not None

    def test_record_sync_fails_when_not_active(self):
        """Test record_sync fails for non-ACTIVE connection."""
        # Arrange
        connection = create_connection(status=ConnectionStatus.PENDING)

        # Act
        result = connection.record_sync()

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ProviderConnectionError.NOT_CONNECTED

    def test_record_sync_updates_last_sync_at(self):
        """Test record_sync updates last_sync_at timestamp."""
        # Arrange
        credentials = create_credentials()
        old_sync_time = datetime.now(UTC) - timedelta(hours=1)
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
            last_sync_at=old_sync_time,
        )

        # Act
        connection.record_sync()

        # Assert
        assert connection.last_sync_at is not None
        assert connection.last_sync_at > old_sync_time

    def test_record_sync_updates_updated_at(self):
        """Test record_sync updates updated_at timestamp."""
        # Arrange
        credentials = create_credentials()
        connection = create_connection(
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )
        original_updated_at = connection.updated_at

        # Act
        connection.record_sync()

        # Assert
        assert connection.updated_at > original_updated_at
