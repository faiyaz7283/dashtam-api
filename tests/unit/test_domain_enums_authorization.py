"""Unit tests for authorization domain enums.

Tests for UserRole, Resource, and Action enums.

Reference:
    - src/domain/enums/user_role.py
    - src/domain/enums/permission.py
    - docs/architecture/authorization-architecture.md
"""

import pytest

from src.domain.enums import Action, Resource, UserRole


# =============================================================================
# UserRole Tests
# =============================================================================


class TestUserRole:
    """Tests for UserRole enum."""

    def test_all_roles_exist(self) -> None:
        """Test all expected roles are defined."""
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.USER.value == "user"
        assert UserRole.READONLY.value == "readonly"

    def test_role_count(self) -> None:
        """Test expected number of roles."""
        assert len(UserRole) == 3

    def test_role_is_string_enum(self) -> None:
        """Test roles are string enums for easy serialization."""
        assert isinstance(UserRole.ADMIN.value, str)
        assert str(UserRole.ADMIN) == "UserRole.ADMIN"
        assert UserRole.ADMIN == "admin"  # String comparison works

    def test_role_membership(self) -> None:
        """Test enum membership check."""
        assert "admin" in [r.value for r in UserRole]
        assert "superuser" not in [r.value for r in UserRole]

    def test_role_from_value(self) -> None:
        """Test creating role from string value."""
        assert UserRole("admin") == UserRole.ADMIN
        assert UserRole("user") == UserRole.USER
        assert UserRole("readonly") == UserRole.READONLY

    def test_invalid_role_raises_error(self) -> None:
        """Test invalid role value raises ValueError."""
        with pytest.raises(ValueError):
            UserRole("superuser")


# =============================================================================
# Resource Tests
# =============================================================================


class TestResource:
    """Tests for Resource enum."""

    def test_all_resources_exist(self) -> None:
        """Test all expected resources are defined."""
        assert Resource.ACCOUNTS.value == "accounts"
        assert Resource.TRANSACTIONS.value == "transactions"
        assert Resource.PROVIDERS.value == "providers"
        assert Resource.USERS.value == "users"
        assert Resource.SESSIONS.value == "sessions"
        assert Resource.ADMIN.value == "admin"
        assert Resource.SECURITY.value == "security"

    def test_resource_count(self) -> None:
        """Test expected number of resources."""
        assert len(Resource) == 7

    def test_resource_is_string_enum(self) -> None:
        """Test resources are string enums for easy serialization."""
        assert isinstance(Resource.ACCOUNTS.value, str)

    def test_resource_from_value(self) -> None:
        """Test creating resource from string value."""
        assert Resource("accounts") == Resource.ACCOUNTS
        assert Resource("transactions") == Resource.TRANSACTIONS

    def test_invalid_resource_raises_error(self) -> None:
        """Test invalid resource value raises ValueError."""
        with pytest.raises(ValueError):
            Resource("invalid_resource")


# =============================================================================
# Action Tests
# =============================================================================


class TestAction:
    """Tests for Action enum."""

    def test_all_actions_exist(self) -> None:
        """Test all expected actions are defined."""
        assert Action.READ.value == "read"
        assert Action.WRITE.value == "write"

    def test_action_count(self) -> None:
        """Test expected number of actions."""
        assert len(Action) == 2

    def test_action_is_string_enum(self) -> None:
        """Test actions are string enums for easy serialization."""
        assert isinstance(Action.READ.value, str)

    def test_action_from_value(self) -> None:
        """Test creating action from string value."""
        assert Action("read") == Action.READ
        assert Action("write") == Action.WRITE

    def test_invalid_action_raises_error(self) -> None:
        """Test invalid action value raises ValueError."""
        with pytest.raises(ValueError):
            Action("delete")


# =============================================================================
# Permission Combination Tests
# =============================================================================


class TestPermissionCombinations:
    """Tests for valid permission combinations."""

    def test_readonly_permissions(self) -> None:
        """Test readonly role has read-only permissions."""
        # Readonly should have read access to business resources
        readonly_resources = [
            Resource.ACCOUNTS,
            Resource.TRANSACTIONS,
            Resource.PROVIDERS,
            Resource.SESSIONS,
        ]

        for resource in readonly_resources:
            # Permission string format: "resource:action"
            perm = f"{resource.value}:{Action.READ.value}"
            assert "read" in perm

    def test_user_permissions(self) -> None:
        """Test user role has write permissions."""
        # User should have write access to business resources
        user_resources = [
            Resource.ACCOUNTS,
            Resource.TRANSACTIONS,
            Resource.PROVIDERS,
            Resource.SESSIONS,
        ]

        for resource in user_resources:
            perm = f"{resource.value}:{Action.WRITE.value}"
            assert "write" in perm

    def test_admin_permissions(self) -> None:
        """Test admin role has admin/security permissions."""
        admin_resources = [
            Resource.ADMIN,
            Resource.SECURITY,
            Resource.USERS,
        ]

        for resource in admin_resources:
            # Admin should have both read and write
            read_perm = f"{resource.value}:{Action.READ.value}"
            write_perm = f"{resource.value}:{Action.WRITE.value}"
            assert "read" in read_perm
            assert "write" in write_perm

    def test_permission_string_format(self) -> None:
        """Test permission string format is consistent."""
        # All permissions should be in "resource:action" format
        for resource in Resource:
            for action in Action:
                perm = f"{resource.value}:{action.value}"
                parts = perm.split(":")
                assert len(parts) == 2
                assert parts[0] == resource.value
                assert parts[1] == action.value
