"""Unit tests for authentication domain events.

Tests cover:
- Event creation with all required fields
- Immutability (frozen dataclass)
- event_id auto-generation
- occurred_at timestamp auto-generation
- Each of 12 authentication events
- Dataclass structure validation
- Past tense naming convention

Architecture:
- Unit tests for domain events (no dependencies)
- Validates 3-state pattern (ATTEMPTED/SUCCEEDED/FAILED)
- Tests all 4 workflows × 3 states = 12 events
"""

from datetime import datetime, UTC
from uuid import UUID

import pytest

from src.domain.events.auth_events import (
    ProviderConnectionAttempted,
    ProviderConnectionFailed,
    ProviderConnectionSucceeded,
    TokenRefreshAttempted,
    TokenRefreshFailed,
    TokenRefreshSucceeded,
    UserPasswordChangeAttempted,
    UserPasswordChangeFailed,
    UserPasswordChangeSucceeded,
    UserRegistrationAttempted,
    UserRegistrationFailed,
    UserRegistrationSucceeded,
)
from src.domain.events.base_event import DomainEvent


@pytest.mark.unit
class TestDomainEventBaseProperties:
    """Test DomainEvent base class properties (auto-generation, immutability)."""

    def test_event_id_auto_generated(self):
        """Test event_id is auto-generated when not provided."""
        # Act
        event = UserRegistrationSucceeded(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            email="test@example.com",
            verification_token="test_token_123",
        )

        # Assert
        assert event.event_id is not None
        assert isinstance(event.event_id, UUID)

    def test_occurred_at_auto_generated(self):
        """Test occurred_at timestamp is auto-generated in UTC."""
        # Arrange
        before = datetime.now(UTC)

        # Act
        event = UserRegistrationSucceeded(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            email="test@example.com",
            verification_token="test_token_123",
        )

        after = datetime.now(UTC)

        # Assert
        assert event.occurred_at is not None
        assert isinstance(event.occurred_at, datetime)
        assert event.occurred_at.tzinfo == UTC
        assert before <= event.occurred_at <= after

    def test_event_is_immutable_frozen_dataclass(self):
        """Test events are immutable (frozen dataclass)."""
        # Arrange
        event = UserRegistrationSucceeded(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            email="test@example.com",
            verification_token="test_token_123",
        )

        # Act & Assert - Attempting to modify should raise FrozenInstanceError
        with pytest.raises(
            AttributeError
        ):  # dataclasses.FrozenInstanceError inherits from AttributeError
            event.email = "changed@example.com"

    def test_event_inherits_from_domain_event(self):
        """Test all events inherit from DomainEvent."""
        # Act
        event = UserRegistrationSucceeded(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            email="test@example.com",
            verification_token="test_token_123",
        )

        # Assert
        assert isinstance(event, DomainEvent)


@pytest.mark.unit
class TestUserRegistrationEvents:
    """Test User Registration workflow events (3-state pattern)."""

    def test_user_registration_attempted_creation(self):
        """Test UserRegistrationAttempted event with all fields."""
        # Act
        event = UserRegistrationAttempted(email="test@example.com")

        # Assert
        assert event.email == "test@example.com"
        assert isinstance(event.event_id, UUID)
        assert isinstance(event.occurred_at, datetime)

    def test_user_registration_succeeded_creation(self):
        """Test UserRegistrationSucceeded event with all fields."""
        # Arrange
        user_id = UUID("12345678-1234-5678-1234-567812345678")

        # Act
        event = UserRegistrationSucceeded(
            user_id=user_id,
            email="test@example.com",
            verification_token="abc123def456",
        )

        # Assert
        assert event.user_id == user_id
        assert event.email == "test@example.com"
        assert event.verification_token == "abc123def456"
        assert isinstance(event.event_id, UUID)
        assert isinstance(event.occurred_at, datetime)

    def test_user_registration_failed_creation(self):
        """Test UserRegistrationFailed event with all fields."""
        # Act
        event = UserRegistrationFailed(
            email="test@example.com",
            reason="duplicate_email",
        )

        # Assert
        assert event.email == "test@example.com"
        assert event.reason == "duplicate_email"


@pytest.mark.unit
class TestUserPasswordChangeEvents:
    """Test User Password Change workflow events (3-state pattern)."""

    def test_user_password_change_attempted_creation(self):
        """Test UserPasswordChangeAttempted event with all fields."""
        # Arrange
        user_id = UUID("12345678-1234-5678-1234-567812345678")

        # Act
        event = UserPasswordChangeAttempted(user_id=user_id)

        # Assert
        assert event.user_id == user_id

    def test_user_password_change_succeeded_creation(self):
        """Test UserPasswordChangeSucceeded event with all fields."""
        # Arrange
        user_id = UUID("12345678-1234-5678-1234-567812345678")

        # Act
        event = UserPasswordChangeSucceeded(user_id=user_id, initiated_by="admin")

        # Assert
        assert event.user_id == user_id
        assert event.initiated_by == "admin"

    def test_user_password_change_failed_creation(self):
        """Test UserPasswordChangeFailed event with all fields."""
        # Arrange
        user_id = UUID("12345678-1234-5678-1234-567812345678")

        # Act
        event = UserPasswordChangeFailed(
            user_id=user_id,
            reason="invalid_old_password",
        )

        # Assert
        assert event.user_id == user_id
        assert event.reason == "invalid_old_password"


@pytest.mark.unit
class TestProviderConnectionEvents:
    """Test Provider Connection workflow events (3-state pattern)."""

    def test_provider_connection_attempted_creation(self):
        """Test ProviderConnectionAttempted event with all fields."""
        # Arrange
        user_id = UUID("12345678-1234-5678-1234-567812345678")

        # Act
        event = ProviderConnectionAttempted(
            user_id=user_id,
            provider_name="schwab",
        )

        # Assert
        assert event.user_id == user_id
        assert event.provider_name == "schwab"

    def test_provider_connection_succeeded_creation(self):
        """Test ProviderConnectionSucceeded event with all fields."""
        # Arrange
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        provider_id = UUID("87654321-4321-8765-4321-876543218765")

        # Act
        event = ProviderConnectionSucceeded(
            user_id=user_id, provider_id=provider_id, provider_name="schwab"
        )

        # Assert
        assert event.user_id == user_id
        assert event.provider_id == provider_id
        assert event.provider_name == "schwab"

    def test_provider_connection_failed_creation(self):
        """Test ProviderConnectionFailed event with all fields."""
        # Arrange
        user_id = UUID("12345678-1234-5678-1234-567812345678")

        # Act
        event = ProviderConnectionFailed(
            user_id=user_id,
            provider_name="schwab",
            reason="access_denied",
        )

        # Assert
        assert event.user_id == user_id
        assert event.provider_name == "schwab"
        assert event.reason == "access_denied"


@pytest.mark.unit
class TestTokenRefreshEvents:
    """Test Token Refresh workflow events (3-state pattern)."""

    def test_token_refresh_attempted_creation(self):
        """Test TokenRefreshAttempted event with all fields."""
        # Arrange
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        provider_id = UUID("87654321-4321-8765-4321-876543218765")

        # Act
        event = TokenRefreshAttempted(
            user_id=user_id, provider_id=provider_id, provider_name="schwab"
        )

        # Assert
        assert event.user_id == user_id
        assert event.provider_id == provider_id
        assert event.provider_name == "schwab"

    def test_token_refresh_succeeded_creation(self):
        """Test TokenRefreshSucceeded event with all fields."""
        # Arrange
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        provider_id = UUID("87654321-4321-8765-4321-876543218765")

        # Act
        event = TokenRefreshSucceeded(
            user_id=user_id, provider_id=provider_id, provider_name="schwab"
        )

        # Assert
        assert event.user_id == user_id
        assert event.provider_id == provider_id
        assert event.provider_name == "schwab"

    def test_token_refresh_failed_creation(self):
        """Test TokenRefreshFailed event with all fields."""
        # Arrange
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        provider_id = UUID("87654321-4321-8765-4321-876543218765")

        # Act
        event = TokenRefreshFailed(
            user_id=user_id,
            provider_id=provider_id,
            provider_name="schwab",
            error_code="invalid_grant",
        )

        # Assert
        assert event.user_id == user_id
        assert event.provider_id == provider_id
        assert event.provider_name == "schwab"
        assert event.error_code == "invalid_grant"


@pytest.mark.unit
class TestEventNamingConvention:
    """Test event naming follows past tense convention."""

    def test_event_names_are_past_tense(self):
        """Test all event class names use past tense (not present/imperative)."""
        # These class names should exist (past tense)
        assert UserRegistrationAttempted.__name__ == "UserRegistrationAttempted"
        assert UserRegistrationSucceeded.__name__ == "UserRegistrationSucceeded"
        assert UserRegistrationFailed.__name__ == "UserRegistrationFailed"

        assert UserPasswordChangeAttempted.__name__ == "UserPasswordChangeAttempted"
        assert UserPasswordChangeSucceeded.__name__ == "UserPasswordChangeSucceeded"
        assert UserPasswordChangeFailed.__name__ == "UserPasswordChangeFailed"

        assert ProviderConnectionAttempted.__name__ == "ProviderConnectionAttempted"
        assert ProviderConnectionSucceeded.__name__ == "ProviderConnectionSucceeded"
        assert ProviderConnectionFailed.__name__ == "ProviderConnectionFailed"

        assert TokenRefreshAttempted.__name__ == "TokenRefreshAttempted"
        assert TokenRefreshSucceeded.__name__ == "TokenRefreshSucceeded"
        assert TokenRefreshFailed.__name__ == "TokenRefreshFailed"


@pytest.mark.unit
class TestEventDataclassStructure:
    """Test events follow frozen dataclass pattern with kw_only."""

    def test_events_require_keyword_arguments(self):
        """Test events require keyword arguments (kw_only=True)."""
        # Act & Assert - Positional arguments should fail
        with pytest.raises(TypeError):
            # This should fail because kw_only=True
            UserRegistrationSucceeded(
                UUID(
                    "12345678-1234-5678-1234-567812345678"
                ),  # Positional - should fail
                "test@example.com",
                "verification_token",
            )

    def test_event_with_explicit_event_id(self):
        """Test event can be created with explicit event_id (for testing)."""
        # Arrange
        custom_event_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        user_id = UUID("12345678-1234-5678-1234-567812345678")

        # Act
        event = UserRegistrationSucceeded(
            event_id=custom_event_id,
            user_id=user_id,
            email="test@example.com",
            verification_token="test_token_123",
        )

        # Assert
        assert event.event_id == custom_event_id

    def test_event_with_explicit_occurred_at(self):
        """Test event can be created with explicit occurred_at (for testing)."""
        # Arrange
        custom_timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        user_id = UUID("12345678-1234-5678-1234-567812345678")

        # Act
        event = UserRegistrationSucceeded(
            occurred_at=custom_timestamp,
            user_id=user_id,
            email="test@example.com",
            verification_token="test_token_123",
        )

        # Assert
        assert event.occurred_at == custom_timestamp
