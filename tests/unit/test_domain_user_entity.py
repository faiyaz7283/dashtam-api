"""Unit tests for User domain entity.

Tests cover:
- User creation with all required fields
- is_locked() business logic
- increment_failed_login() with lockout
- reset_failed_login() clearing lockout
- can_login() combined checks

Architecture:
- Unit tests for domain entity (no dependencies)
- Tests pure business logic
- Validates entity invariants and business rules
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID
from uuid_extensions import uuid7

import pytest

from src.domain.entities.user import User


def create_user(
    user_id: UUID | None = None,
    email: str = "test@example.com",
    password_hash: str = "hashed_password",
    is_verified: bool = True,
    is_active: bool = True,
    failed_login_attempts: int = 0,
    locked_until: datetime | None = None,
) -> User:
    """Helper to create User entities for testing."""
    now = datetime.now(UTC)
    return User(
        id=user_id or uuid7(),
        email=email,
        password_hash=password_hash,
        is_verified=is_verified,
        is_active=is_active,
        failed_login_attempts=failed_login_attempts,
        locked_until=locked_until,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.unit
class TestUserCreation:
    """Test User entity creation."""

    def test_user_created_with_all_required_fields(self):
        """Test User can be created with all required fields."""
        # Arrange
        user_id = uuid7()
        now = datetime.now(UTC)

        # Act
        user = User(
            id=user_id,
            email="test@example.com",
            password_hash="hashed_password_value",
            is_verified=False,
            is_active=True,
            failed_login_attempts=0,
            locked_until=None,
            created_at=now,
            updated_at=now,
        )

        # Assert
        assert user.id == user_id
        assert isinstance(user.id, UUID)
        assert user.email == "test@example.com"
        assert user.password_hash == "hashed_password_value"
        assert user.is_verified is False
        assert user.is_active is True
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
        assert user.created_at == now
        assert user.updated_at == now

    def test_user_created_as_verified(self):
        """Test User can be created with verified status."""
        # Act
        user = create_user(is_verified=True)

        # Assert
        assert user.is_verified is True

    def test_user_created_as_inactive(self):
        """Test User can be created with inactive status."""
        # Act
        user = create_user(is_active=False)

        # Assert
        assert user.is_active is False


@pytest.mark.unit
class TestUserIsLocked:
    """Test User.is_locked() business logic."""

    def test_is_locked_false_when_locked_until_is_none(self):
        """Test is_locked returns False when locked_until is None."""
        # Arrange
        user = create_user(locked_until=None)

        # Assert
        assert user.is_locked() is False

    def test_is_locked_true_when_locked_until_in_future(self):
        """Test is_locked returns True when locked_until is in future."""
        # Arrange
        future_time = datetime.now(UTC) + timedelta(minutes=10)
        user = create_user(locked_until=future_time)

        # Assert
        assert user.is_locked() is True

    def test_is_locked_false_when_locked_until_in_past(self):
        """Test is_locked returns False when locked_until is in past."""
        # Arrange
        past_time = datetime.now(UTC) - timedelta(minutes=10)
        user = create_user(locked_until=past_time)

        # Assert
        assert user.is_locked() is False


@pytest.mark.unit
class TestUserIncrementFailedLogin:
    """Test User.increment_failed_login() business logic."""

    def test_increment_failed_login_increases_counter(self):
        """Test increment_failed_login increases counter by 1."""
        # Arrange
        user = create_user(failed_login_attempts=0)

        # Act
        user.increment_failed_login()

        # Assert
        assert user.failed_login_attempts == 1

    def test_increment_failed_login_locks_after_5_attempts(self):
        """Test account locks after 5 failed attempts (business rule)."""
        # Arrange
        user = create_user(failed_login_attempts=4)
        assert user.is_locked() is False

        # Act - 5th failed attempt
        user.increment_failed_login()

        # Assert
        assert user.failed_login_attempts == 5
        assert user.is_locked() is True
        assert user.locked_until is not None
        # Lockout should be ~15 minutes in future
        assert user.locked_until > datetime.now(UTC)
        assert user.locked_until < datetime.now(UTC) + timedelta(minutes=16)

    def test_increment_failed_login_does_not_lock_before_5_attempts(self):
        """Test account does not lock before 5 failed attempts."""
        # Arrange
        user = create_user(failed_login_attempts=3)

        # Act
        user.increment_failed_login()

        # Assert
        assert user.failed_login_attempts == 4
        assert user.is_locked() is False
        assert user.locked_until is None


@pytest.mark.unit
class TestUserResetFailedLogin:
    """Test User.reset_failed_login() business logic."""

    def test_reset_failed_login_clears_counter(self):
        """Test reset_failed_login sets counter to 0."""
        # Arrange
        user = create_user(failed_login_attempts=3)

        # Act
        user.reset_failed_login()

        # Assert
        assert user.failed_login_attempts == 0

    def test_reset_failed_login_clears_lockout(self):
        """Test reset_failed_login clears locked_until."""
        # Arrange
        future_time = datetime.now(UTC) + timedelta(minutes=10)
        user = create_user(
            failed_login_attempts=5,
            locked_until=future_time,
        )
        assert user.is_locked() is True

        # Act
        user.reset_failed_login()

        # Assert
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
        assert user.is_locked() is False


@pytest.mark.unit
class TestUserCanLogin:
    """Test User.can_login() combined checks."""

    def test_can_login_true_when_verified_active_unlocked(self):
        """Test can_login returns True for verified, active, unlocked user."""
        # Arrange
        user = create_user(
            is_verified=True,
            is_active=True,
            locked_until=None,
        )

        # Assert
        assert user.can_login() is True

    def test_can_login_false_when_not_verified(self):
        """Test can_login returns False for unverified user."""
        # Arrange
        user = create_user(is_verified=False)

        # Assert
        assert user.can_login() is False

    def test_can_login_false_when_inactive(self):
        """Test can_login returns False for inactive user."""
        # Arrange
        user = create_user(is_active=False)

        # Assert
        assert user.can_login() is False

    def test_can_login_false_when_locked(self):
        """Test can_login returns False for locked user."""
        # Arrange
        future_time = datetime.now(UTC) + timedelta(minutes=10)
        user = create_user(locked_until=future_time)

        # Assert
        assert user.can_login() is False
