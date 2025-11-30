"""Unit tests for Provider domain events.

Tests cover:
- Event creation with all required fields
- Event immutability (frozen dataclasses)
- Event inheritance from DomainEvent
- Field validation (no missing attributes)
- All 9 provider events (3 workflows × 3 states)

Architecture:
- Unit tests for domain events (no dependencies)
- Tests pure event structure
- Validates all events follow 3-state pattern
"""

from uuid import uuid4

import pytest

from src.domain.events.provider_events import (
    ProviderConnectionAttempted,
    ProviderConnectionFailed,
    ProviderConnectionSucceeded,
    ProviderDisconnectionAttempted,
    ProviderDisconnectionFailed,
    ProviderDisconnectionSucceeded,
    ProviderTokenRefreshAttempted,
    ProviderTokenRefreshFailed,
    ProviderTokenRefreshSucceeded,
)


@pytest.mark.unit
class TestProviderConnectionAttempted:
    """Test ProviderConnectionAttempted event."""

    def test_event_created_with_all_required_fields(self):
        """Test event can be created with all required fields."""
        # Arrange
        user_id = uuid4()
        provider_id = uuid4()

        # Act
        event = ProviderConnectionAttempted(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug="schwab",
        )

        # Assert
        assert event.user_id == user_id
        assert event.provider_id == provider_id
        assert event.provider_slug == "schwab"
        assert event.occurred_at is not None
        assert event.event_id is not None

    def test_event_is_frozen(self):
        """Test event is immutable (frozen dataclass)."""
        # Arrange
        event = ProviderConnectionAttempted(
            user_id=uuid4(),
            provider_id=uuid4(),
            provider_slug="schwab",
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            event.user_id = uuid4()  # type: ignore[misc]


@pytest.mark.unit
class TestProviderConnectionSucceeded:
    """Test ProviderConnectionSucceeded event."""

    def test_event_created_with_all_required_fields(self):
        """Test event can be created with all required fields."""
        # Arrange
        user_id = uuid4()
        connection_id = uuid4()
        provider_id = uuid4()

        # Act
        event = ProviderConnectionSucceeded(
            user_id=user_id,
            connection_id=connection_id,
            provider_id=provider_id,
            provider_slug="schwab",
        )

        # Assert
        assert event.user_id == user_id
        assert event.connection_id == connection_id
        assert event.provider_id == provider_id
        assert event.provider_slug == "schwab"
        assert event.occurred_at is not None

    def test_event_is_frozen(self):
        """Test event is immutable (frozen dataclass)."""
        # Arrange
        event = ProviderConnectionSucceeded(
            user_id=uuid4(),
            connection_id=uuid4(),
            provider_id=uuid4(),
            provider_slug="schwab",
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            event.connection_id = uuid4()  # type: ignore[misc]


@pytest.mark.unit
class TestProviderConnectionFailed:
    """Test ProviderConnectionFailed event."""

    def test_event_created_with_all_required_fields(self):
        """Test event can be created with all required fields."""
        # Arrange
        user_id = uuid4()
        provider_id = uuid4()

        # Act
        event = ProviderConnectionFailed(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug="schwab",
            reason="oauth_error",
        )

        # Assert
        assert event.user_id == user_id
        assert event.provider_id == provider_id
        assert event.provider_slug == "schwab"
        assert event.reason == "oauth_error"
        assert event.occurred_at is not None

    def test_event_created_with_different_failure_reasons(self):
        """Test event supports various failure reasons."""
        # Arrange
        reasons = [
            "user_cancelled",
            "oauth_error",
            "invalid_credentials",
            "provider_unavailable",
        ]

        for reason in reasons:
            # Act
            event = ProviderConnectionFailed(
                user_id=uuid4(),
                provider_id=uuid4(),
                provider_slug="schwab",
                reason=reason,
            )

            # Assert
            assert event.reason == reason


@pytest.mark.unit
class TestProviderDisconnectionAttempted:
    """Test ProviderDisconnectionAttempted event."""

    def test_event_created_with_all_required_fields(self):
        """Test event can be created with all required fields."""
        # Arrange
        user_id = uuid4()
        connection_id = uuid4()
        provider_id = uuid4()

        # Act
        event = ProviderDisconnectionAttempted(
            user_id=user_id,
            connection_id=connection_id,
            provider_id=provider_id,
            provider_slug="schwab",
        )

        # Assert
        assert event.user_id == user_id
        assert event.connection_id == connection_id
        assert event.provider_id == provider_id
        assert event.provider_slug == "schwab"
        assert event.occurred_at is not None


@pytest.mark.unit
class TestProviderDisconnectionSucceeded:
    """Test ProviderDisconnectionSucceeded event."""

    def test_event_created_with_all_required_fields(self):
        """Test event can be created with all required fields."""
        # Arrange
        user_id = uuid4()
        connection_id = uuid4()
        provider_id = uuid4()

        # Act
        event = ProviderDisconnectionSucceeded(
            user_id=user_id,
            connection_id=connection_id,
            provider_id=provider_id,
            provider_slug="schwab",
        )

        # Assert
        assert event.user_id == user_id
        assert event.connection_id == connection_id
        assert event.provider_id == provider_id
        assert event.provider_slug == "schwab"
        assert event.occurred_at is not None


@pytest.mark.unit
class TestProviderDisconnectionFailed:
    """Test ProviderDisconnectionFailed event."""

    def test_event_created_with_all_required_fields(self):
        """Test event can be created with all required fields."""
        # Arrange
        user_id = uuid4()
        connection_id = uuid4()
        provider_id = uuid4()

        # Act
        event = ProviderDisconnectionFailed(
            user_id=user_id,
            connection_id=connection_id,
            provider_id=provider_id,
            provider_slug="schwab",
            reason="database_error",
        )

        # Assert
        assert event.user_id == user_id
        assert event.connection_id == connection_id
        assert event.provider_id == provider_id
        assert event.provider_slug == "schwab"
        assert event.reason == "database_error"


@pytest.mark.unit
class TestProviderTokenRefreshAttempted:
    """Test ProviderTokenRefreshAttempted event."""

    def test_event_created_with_all_required_fields(self):
        """Test event can be created with all required fields."""
        # Arrange
        user_id = uuid4()
        connection_id = uuid4()
        provider_id = uuid4()

        # Act
        event = ProviderTokenRefreshAttempted(
            user_id=user_id,
            connection_id=connection_id,
            provider_id=provider_id,
            provider_slug="schwab",
        )

        # Assert
        assert event.user_id == user_id
        assert event.connection_id == connection_id
        assert event.provider_id == provider_id
        assert event.provider_slug == "schwab"
        assert event.occurred_at is not None


@pytest.mark.unit
class TestProviderTokenRefreshSucceeded:
    """Test ProviderTokenRefreshSucceeded event."""

    def test_event_created_with_all_required_fields(self):
        """Test event can be created with all required fields."""
        # Arrange
        user_id = uuid4()
        connection_id = uuid4()
        provider_id = uuid4()

        # Act
        event = ProviderTokenRefreshSucceeded(
            user_id=user_id,
            connection_id=connection_id,
            provider_id=provider_id,
            provider_slug="schwab",
        )

        # Assert
        assert event.user_id == user_id
        assert event.connection_id == connection_id
        assert event.provider_id == provider_id
        assert event.provider_slug == "schwab"
        assert event.occurred_at is not None


@pytest.mark.unit
class TestProviderTokenRefreshFailed:
    """Test ProviderTokenRefreshFailed event."""

    def test_event_created_with_all_required_fields(self):
        """Test event can be created with all required fields."""
        # Arrange
        user_id = uuid4()
        connection_id = uuid4()
        provider_id = uuid4()

        # Act
        event = ProviderTokenRefreshFailed(
            user_id=user_id,
            connection_id=connection_id,
            provider_id=provider_id,
            provider_slug="schwab",
            reason="refresh_token_expired",
            needs_user_action=True,
        )

        # Assert
        assert event.user_id == user_id
        assert event.connection_id == connection_id
        assert event.provider_id == provider_id
        assert event.provider_slug == "schwab"
        assert event.reason == "refresh_token_expired"
        assert event.needs_user_action is True

    def test_event_created_with_default_needs_user_action(self):
        """Test event defaults needs_user_action to False."""
        # Act
        event = ProviderTokenRefreshFailed(
            user_id=uuid4(),
            connection_id=uuid4(),
            provider_id=uuid4(),
            provider_slug="schwab",
            reason="network_error",
        )

        # Assert
        assert event.needs_user_action is False

    def test_event_created_with_different_failure_reasons(self):
        """Test event supports various failure reasons."""
        # Arrange
        reasons = [
            "refresh_token_expired",
            "provider_revoked",
            "network_error",
        ]

        for reason in reasons:
            # Act
            event = ProviderTokenRefreshFailed(
                user_id=uuid4(),
                connection_id=uuid4(),
                provider_id=uuid4(),
                provider_slug="schwab",
                reason=reason,
            )

            # Assert
            assert event.reason == reason
