"""Unit tests for application layer DTOs.

Tests all Data Transfer Objects (DTOs) in src/application/dtos/ following
established testing patterns.

DTOs covered:
    - AuthenticatedUser (auth_dtos.py)
    - AuthTokens (auth_dtos.py)
    - GlobalRotationResult (auth_dtos.py)
    - UserRotationResult (auth_dtos.py)
    - SyncAccountsResult (sync_dtos.py)
    - SyncTransactionsResult (sync_dtos.py)
    - SyncHoldingsResult (sync_dtos.py)
    - ImportResult (import_dtos.py)
"""

from typing import cast
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.application.dtos import (
    AuthenticatedUser,
    AuthTokens,
    GlobalRotationResult,
    ImportResult,
    SyncAccountsResult,
    SyncHoldingsResult,
    SyncTransactionsResult,
    UserRotationResult,
)


@pytest.mark.unit
class TestAuthenticatedUser:
    """Unit tests for AuthenticatedUser DTO."""

    def test_create_with_all_fields(self):
        """Test creating AuthenticatedUser with all fields."""
        # Arrange
        user_id = cast(UUID, uuid7())
        email = "user@example.com"
        roles = ["user", "admin"]

        # Act
        dto = AuthenticatedUser(
            user_id=user_id,
            email=email,
            roles=roles,
        )

        # Assert
        assert dto.user_id == user_id
        assert dto.email == email
        assert dto.roles == roles

    def test_is_immutable(self):
        """Test AuthenticatedUser is frozen (immutable)."""
        # Arrange
        dto = AuthenticatedUser(
            user_id=cast(UUID, uuid7()),
            email="user@example.com",
            roles=["user"],
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            dto.email = "different@example.com"  # type: ignore[misc]

    def test_uses_keyword_only_args(self):
        """Test AuthenticatedUser requires keyword arguments."""
        # Act & Assert - positional args should fail
        with pytest.raises(TypeError):
            AuthenticatedUser(  # type: ignore[misc]
                uuid7(),
                "user@example.com",
                ["user"],
            )


@pytest.mark.unit
class TestAuthTokens:
    """Unit tests for AuthTokens DTO."""

    def test_create_with_required_fields(self):
        """Test creating AuthTokens with required fields only."""
        # Act
        dto = AuthTokens(
            access_token="eyJ...",
            refresh_token="abc123...",
        )

        # Assert
        assert dto.access_token == "eyJ..."
        assert dto.refresh_token == "abc123..."
        assert dto.token_type == "bearer"  # Default value
        assert dto.expires_in == 900  # Default value (15 minutes)

    def test_create_with_custom_values(self):
        """Test creating AuthTokens with custom token_type and expires_in."""
        # Act
        dto = AuthTokens(
            access_token="eyJ...",
            refresh_token="abc123...",
            token_type="Bearer",
            expires_in=1800,
        )

        # Assert
        assert dto.token_type == "Bearer"
        assert dto.expires_in == 1800

    def test_is_immutable(self):
        """Test AuthTokens is frozen (immutable)."""
        # Arrange
        dto = AuthTokens(
            access_token="eyJ...",
            refresh_token="abc123...",
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            dto.access_token = "different"  # type: ignore[misc]


@pytest.mark.unit
class TestGlobalRotationResult:
    """Unit tests for GlobalRotationResult DTO."""

    def test_create_with_all_fields(self):
        """Test creating GlobalRotationResult with all fields."""
        # Act
        dto = GlobalRotationResult(
            previous_version=5,
            new_version=6,
            grace_period_seconds=300,
        )

        # Assert
        assert dto.previous_version == 5
        assert dto.new_version == 6
        assert dto.grace_period_seconds == 300

    def test_is_immutable(self):
        """Test GlobalRotationResult is frozen (immutable)."""
        # Arrange
        dto = GlobalRotationResult(
            previous_version=1,
            new_version=2,
            grace_period_seconds=60,
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            dto.new_version = 10  # type: ignore[misc]


@pytest.mark.unit
class TestUserRotationResult:
    """Unit tests for UserRotationResult DTO."""

    def test_create_with_all_fields(self):
        """Test creating UserRotationResult with all fields."""
        # Arrange
        user_id = cast(UUID, uuid7())

        # Act
        dto = UserRotationResult(
            user_id=user_id,
            previous_version=3,
            new_version=4,
        )

        # Assert
        assert dto.user_id == user_id
        assert dto.previous_version == 3
        assert dto.new_version == 4

    def test_is_immutable(self):
        """Test UserRotationResult is frozen (immutable)."""
        # Arrange
        dto = UserRotationResult(
            user_id=cast(UUID, uuid7()),
            previous_version=1,
            new_version=2,
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            dto.new_version = 10  # type: ignore[misc]


@pytest.mark.unit
class TestSyncAccountsResult:
    """Unit tests for SyncAccountsResult DTO."""

    def test_create_with_all_fields(self):
        """Test creating SyncAccountsResult with all fields."""
        # Act
        dto = SyncAccountsResult(
            created=5,
            updated=3,
            unchanged=10,
            errors=1,
            message="Sync completed: 5 created, 3 updated, 10 unchanged, 1 error",
        )

        # Assert
        assert dto.created == 5
        assert dto.updated == 3
        assert dto.unchanged == 10
        assert dto.errors == 1
        assert "5 created" in dto.message

    def test_is_not_frozen(self):
        """Test SyncAccountsResult is NOT frozen (mutable for builder pattern)."""
        # Arrange
        dto = SyncAccountsResult(
            created=0,
            updated=0,
            unchanged=0,
            errors=0,
            message="",
        )

        # Act - Should work (not frozen)
        dto.created = 5
        dto.message = "Updated"

        # Assert
        assert dto.created == 5
        assert dto.message == "Updated"


@pytest.mark.unit
class TestSyncTransactionsResult:
    """Unit tests for SyncTransactionsResult DTO."""

    def test_create_with_all_fields(self):
        """Test creating SyncTransactionsResult with all fields."""
        # Act
        dto = SyncTransactionsResult(
            created=100,
            updated=25,
            unchanged=500,
            errors=2,
            accounts_synced=3,
            message="Transactions synced across 3 accounts",
        )

        # Assert
        assert dto.created == 100
        assert dto.updated == 25
        assert dto.unchanged == 500
        assert dto.errors == 2
        assert dto.accounts_synced == 3
        assert "3 accounts" in dto.message


@pytest.mark.unit
class TestSyncHoldingsResult:
    """Unit tests for SyncHoldingsResult DTO."""

    def test_create_with_all_fields(self):
        """Test creating SyncHoldingsResult with all fields."""
        # Act
        dto = SyncHoldingsResult(
            created=10,
            updated=5,
            unchanged=20,
            deactivated=2,
            errors=0,
            message="Holdings sync completed",
        )

        # Assert
        assert dto.created == 10
        assert dto.updated == 5
        assert dto.unchanged == 20
        assert dto.deactivated == 2
        assert dto.errors == 0


@pytest.mark.unit
class TestImportResult:
    """Unit tests for ImportResult DTO."""

    def test_create_with_all_fields(self):
        """Test creating ImportResult with all fields."""
        # Arrange
        connection_id = cast(UUID, uuid7())

        # Act
        dto = ImportResult(
            connection_id=connection_id,
            accounts_created=1,
            accounts_updated=0,
            transactions_created=25,
            transactions_skipped=5,
            message="Imported from Chase_Activity.QFX",
        )

        # Assert
        assert dto.connection_id == connection_id
        assert dto.accounts_created == 1
        assert dto.accounts_updated == 0
        assert dto.transactions_created == 25
        assert dto.transactions_skipped == 5
        assert "Chase_Activity.QFX" in dto.message


@pytest.mark.unit
class TestDTOModuleExports:
    """Unit tests for DTO module __all__ exports."""

    def test_all_dtos_are_exported(self):
        """Test __all__ exports all DTOs."""
        from src.application import dtos

        expected_exports = {
            "AuthenticatedUser",
            "AuthTokens",
            "GlobalRotationResult",
            "UserRotationResult",
            "BalanceChange",
            "SyncAccountsResult",
            "SyncTransactionsResult",
            "SyncHoldingsResult",
            "ImportResult",
        }

        actual_exports = set(dtos.__all__)

        assert actual_exports == expected_exports

    def test_all_dtos_are_importable(self):
        """Test all DTOs can be imported from src.application.dtos."""
        from src.application.dtos import (
            AuthenticatedUser,
            AuthTokens,
            BalanceChange,
            GlobalRotationResult,
            ImportResult,
            SyncAccountsResult,
            SyncHoldingsResult,
            SyncTransactionsResult,
            UserRotationResult,
        )

        # All imports should work
        assert AuthenticatedUser is not None
        assert AuthTokens is not None
        assert BalanceChange is not None
        assert GlobalRotationResult is not None
        assert UserRotationResult is not None
        assert SyncAccountsResult is not None
        assert SyncTransactionsResult is not None
        assert SyncHoldingsResult is not None
        assert ImportResult is not None
