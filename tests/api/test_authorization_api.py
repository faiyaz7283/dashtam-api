"""API tests for authorization dependencies.

Tests cover:
- require_permission() dependency returns 403 for unauthorized access
- require_casbin_role() dependency returns 403 for insufficient role
- require_any_permission() allows access if any permission matches
- require_all_permissions() requires all permissions to match
- Successful access with proper roles

Architecture:
- Uses real app with dependency overrides
- Mocks authorization service to control permission/role checks
- Tests HTTP status codes and error responses

Test Strategy:
    This file tests authorization DEPENDENCIES in isolation by adding test
    endpoints to the real app and mocking the authorization service. This
    validates that authorization dependencies work correctly before real
    endpoints use them.

    Test Levels:
    1. Dependency isolation tests (this file) - Validates dependencies work
    2. Real endpoint tests (future) - Validates real endpoints use auth correctly

Reference:
    - src/presentation/api/middleware/authorization_dependencies.py
    - docs/architecture/authorization-architecture.md
"""

from typing import Annotated
from unittest.mock import AsyncMock
from uuid_extensions import uuid7

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from src.domain.enums import UserRole
from src.main import app
from src.presentation.routers.api.middleware.authorization_dependencies import (
    require_permission,
    require_casbin_role,
    require_any_permission,
    require_all_permissions,
)


# =============================================================================
# Test Endpoints Setup
# =============================================================================


def setup_test_endpoints():
    """Add test endpoints to the real app for authorization testing."""
    from src.main import app

    # Endpoint protected by require_permission
    @app.get("/test/accounts")
    async def list_accounts(
        _: Annotated[None, Depends(require_permission("accounts", "read"))],
    ):
        return {"accounts": []}

    @app.post("/test/accounts")
    async def create_account(
        _: Annotated[None, Depends(require_permission("accounts", "write"))],
    ):
        return {"created": True}

    # Endpoint protected by require_casbin_role
    @app.get("/test/admin/users")
    async def list_users(
        _: Annotated[None, Depends(require_casbin_role("admin"))],
    ):
        return {"users": []}

    @app.get("/test/user/profile")
    async def get_profile(
        _: Annotated[None, Depends(require_casbin_role("user"))],
    ):
        return {"profile": {}}

    # Endpoint protected by require_any_permission (variadic args)
    @app.get("/test/reports")
    async def view_reports(
        _: Annotated[
            None,
            Depends(
                require_any_permission(
                    ("reports", "read"),
                    ("admin", "read"),
                )
            ),
        ],
    ):
        return {"reports": []}

    # Endpoint protected by require_all_permissions (variadic args)
    @app.post("/test/admin/security")
    async def update_security(
        _: Annotated[
            None,
            Depends(
                require_all_permissions(
                    ("admin", "read"),
                    ("security", "write"),
                )
            ),
        ],
    ):
        return {"updated": True}

    # Edge case endpoints
    @app.get("/test/empty-any")
    async def empty_any(
        _: Annotated[None, Depends(require_any_permission())],
    ):
        return {"ok": True}

    @app.get("/test/empty-all")
    async def empty_all(
        _: Annotated[None, Depends(require_all_permissions())],
    ):
        return {"ok": True}


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module", autouse=True)
def setup_endpoints():
    """Setup test endpoints once for the entire module."""
    setup_test_endpoints()


@pytest.fixture
def mock_authorization():
    """Create a mock authorization service."""
    mock = AsyncMock()
    mock.check_permission = AsyncMock(return_value=False)
    mock.has_role = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def mock_current_user():
    """Create a mock current user."""
    return {
        "id": uuid7(),
        "email": "test@example.com",
        "role": UserRole.USER,
    }


# =============================================================================
# Helper Functions
# =============================================================================


def create_client_with_mocks(
    authorization_mock: AsyncMock,
    test_user_id: str,
) -> TestClient:
    """Create a TestClient with mocked dependencies."""
    # Override dependencies
    from src.core.container import get_authorization
    from src.presentation.routers.api.middleware.auth_dependencies import (
        get_current_user,
    )

    # Capture user_id in closure
    _user_id = test_user_id

    async def mock_get_authorization():
        return authorization_mock

    async def mock_get_current_user():
        # Use a simple object instead of class to avoid scoping issues
        class MockUser:
            def __init__(self, uid: str) -> None:
                self.user_id = uid

        return MockUser(_user_id)

    app.dependency_overrides[get_authorization] = mock_get_authorization
    app.dependency_overrides[get_current_user] = mock_get_current_user

    return TestClient(app, raise_server_exceptions=False)


# =============================================================================
# require_permission Tests
# =============================================================================


@pytest.mark.api
class TestRequirePermission:
    """Test require_permission dependency."""

    def test_returns_403_when_permission_denied(self, mock_authorization):
        """Test that 403 is returned when permission check fails."""
        user_id = uuid7()
        mock_authorization.check_permission.return_value = False

        client = create_client_with_mocks(mock_authorization, str(user_id))

        response = client.get("/test/accounts")

        assert response.status_code == 403
        # Error message format: "Permission denied: {resource}:{action}"
        assert "denied" in response.json()["detail"].lower()

    def test_allows_access_when_permission_granted(self, mock_authorization):
        """Test that access is allowed when permission check passes."""
        user_id = uuid7()
        mock_authorization.check_permission.return_value = True

        client = create_client_with_mocks(mock_authorization, str(user_id))

        response = client.get("/test/accounts")

        assert response.status_code == 200
        assert response.json() == {"accounts": []}

    def test_checks_correct_resource_and_action(self, mock_authorization):
        """Test that correct resource and action are passed to check."""
        user_id = uuid7()
        mock_authorization.check_permission.return_value = False

        client = create_client_with_mocks(mock_authorization, str(user_id))

        client.post("/test/accounts")

        # Verify check_permission was called with correct args
        mock_authorization.check_permission.assert_called()
        call_kwargs = mock_authorization.check_permission.call_args.kwargs
        assert call_kwargs["resource"] == "accounts"
        assert call_kwargs["action"] == "write"


# =============================================================================
# require_casbin_role Tests
# =============================================================================


@pytest.mark.api
class TestRequireCasbinRole:
    """Test require_casbin_role dependency."""

    def test_returns_403_when_role_not_assigned(self, mock_authorization):
        """Test that 403 is returned when user doesn't have role."""
        user_id = uuid7()
        mock_authorization.has_role.return_value = False

        client = create_client_with_mocks(mock_authorization, str(user_id))

        response = client.get("/test/admin/users")

        assert response.status_code == 403
        # Error message format: "Role '{role}' required"
        assert "required" in response.json()["detail"].lower()

    def test_allows_access_when_role_assigned(self, mock_authorization):
        """Test that access is allowed when user has role."""
        user_id = uuid7()
        mock_authorization.has_role.return_value = True

        client = create_client_with_mocks(mock_authorization, str(user_id))

        response = client.get("/test/admin/users")

        assert response.status_code == 200
        assert response.json() == {"users": []}

    def test_checks_correct_role(self, mock_authorization):
        """Test that correct role is passed to has_role check."""
        user_id = uuid7()
        mock_authorization.has_role.return_value = False

        client = create_client_with_mocks(mock_authorization, str(user_id))

        client.get("/test/user/profile")

        # Verify has_role was called with correct role
        mock_authorization.has_role.assert_called()
        call_kwargs = mock_authorization.has_role.call_args.kwargs
        assert call_kwargs.get("role") == "user"


# =============================================================================
# require_any_permission Tests
# =============================================================================


@pytest.mark.api
class TestRequireAnyPermission:
    """Test require_any_permission dependency."""

    def test_returns_403_when_no_permissions_match(self, mock_authorization):
        """Test that 403 is returned when no permissions match."""
        user_id = uuid7()
        mock_authorization.check_permission.return_value = False

        client = create_client_with_mocks(mock_authorization, str(user_id))

        response = client.get("/test/reports")

        assert response.status_code == 403

    def test_allows_access_when_first_permission_matches(self, mock_authorization):
        """Test that access is allowed when first permission matches."""
        user_id = uuid7()

        # First permission matches, second doesn't
        async def side_effect(user_id, resource, action):
            return resource == "reports" and action == "read"

        mock_authorization.check_permission.side_effect = side_effect

        client = create_client_with_mocks(mock_authorization, str(user_id))

        response = client.get("/test/reports")

        assert response.status_code == 200

    def test_allows_access_when_second_permission_matches(self, mock_authorization):
        """Test that access is allowed when second permission matches."""
        user_id = uuid7()

        # First permission doesn't match, second does
        async def side_effect(user_id, resource, action):
            return resource == "admin" and action == "read"

        mock_authorization.check_permission.side_effect = side_effect

        client = create_client_with_mocks(mock_authorization, str(user_id))

        response = client.get("/test/reports")

        assert response.status_code == 200


# =============================================================================
# require_all_permissions Tests
# =============================================================================


@pytest.mark.api
class TestRequireAllPermissions:
    """Test require_all_permissions dependency."""

    def test_returns_403_when_first_permission_missing(self, mock_authorization):
        """Test that 403 is returned when first permission is missing."""
        user_id = uuid7()

        # First permission fails
        async def side_effect(user_id, resource, action):
            return not (resource == "admin" and action == "read")

        mock_authorization.check_permission.side_effect = side_effect

        client = create_client_with_mocks(mock_authorization, str(user_id))

        response = client.post("/test/admin/security")

        assert response.status_code == 403

    def test_returns_403_when_second_permission_missing(self, mock_authorization):
        """Test that 403 is returned when second permission is missing."""
        user_id = uuid7()

        # Second permission fails
        async def side_effect(user_id, resource, action):
            return not (resource == "security" and action == "write")

        mock_authorization.check_permission.side_effect = side_effect

        client = create_client_with_mocks(mock_authorization, str(user_id))

        response = client.post("/test/admin/security")

        assert response.status_code == 403

    def test_allows_access_when_all_permissions_granted(self, mock_authorization):
        """Test that access is allowed when all permissions granted."""
        user_id = uuid7()
        mock_authorization.check_permission.return_value = True

        client = create_client_with_mocks(mock_authorization, str(user_id))

        response = client.post("/test/admin/security")

        assert response.status_code == 200
        assert response.json() == {"updated": True}


# =============================================================================
# Error Response Format Tests
# =============================================================================


@pytest.mark.api
class TestErrorResponseFormat:
    """Test that error responses follow RFC 7807 format."""

    def test_403_response_has_correct_structure(self, mock_authorization):
        """Test that 403 response has proper error structure."""
        user_id = uuid7()
        mock_authorization.check_permission.return_value = False

        client = create_client_with_mocks(mock_authorization, str(user_id))

        response = client.get("/test/accounts")

        assert response.status_code == 403
        body = response.json()
        assert "detail" in body

    def test_403_response_includes_error_message(self, mock_authorization):
        """Test that 403 response includes meaningful error message."""
        user_id = uuid7()
        mock_authorization.has_role.return_value = False

        client = create_client_with_mocks(mock_authorization, str(user_id))

        response = client.get("/test/admin/users")

        assert response.status_code == 403
        body = response.json()
        # Error message should indicate what's required
        # Format is "Role '{role}' required" or "Permission denied: {r}:{a}"
        assert (
            "required" in body["detail"].lower() or "denied" in body["detail"].lower()
        )


# =============================================================================
# Role Hierarchy Tests
# =============================================================================


@pytest.mark.api
class TestRoleHierarchy:
    """Test that role hierarchy is respected in API access."""

    def test_admin_can_access_user_endpoints(self, mock_authorization):
        """Test that admin role can access user-level endpoints."""
        user_id = uuid7()

        # Admin has both admin and user roles
        # Note: authorization calls use keyword args (user_id=..., role=...)
        async def has_role_side_effect(*, user_id, role):
            return role in ["admin", "user", "readonly"]

        mock_authorization.has_role.side_effect = has_role_side_effect

        client = create_client_with_mocks(mock_authorization, str(user_id))

        # Admin should access user endpoint
        response = client.get("/test/user/profile")

        assert response.status_code == 200

    def test_user_cannot_access_admin_endpoints(self, mock_authorization):
        """Test that user role cannot access admin-level endpoints."""
        user_id = uuid7()

        # User doesn't have admin role
        # Note: authorization calls use keyword args (user_id=..., role=...)
        async def has_role_side_effect(*, user_id, role):
            return role in ["user", "readonly"]

        mock_authorization.has_role.side_effect = has_role_side_effect

        client = create_client_with_mocks(mock_authorization, str(user_id))

        # User should be denied admin endpoint
        response = client.get("/test/admin/users")

        assert response.status_code == 403


# =============================================================================
# Edge Cases Tests
# =============================================================================


@pytest.mark.api
class TestEdgeCases:
    """Test edge cases in authorization."""

    def test_empty_permission_list_for_any(self):
        """Test require_any_permission with no permissions.

        Note: require_any_permission uses variadic args, so "empty" means
        no arguments passed. With no permissions to check, all users are denied.
        """
        mock_auth = AsyncMock()
        client = create_client_with_mocks(mock_auth, str(uuid7()))

        # Empty permission list should deny access (no permissions to satisfy)
        response = client.get("/test/empty-any")

        # Should return 403 as no permissions to check
        assert response.status_code == 403

    def test_empty_permission_list_for_all(self):
        """Test require_all_permissions with no permissions.

        Note: require_all_permissions uses variadic args, so "empty" means
        no arguments passed. With no permissions required, access is granted.
        """
        mock_auth = AsyncMock()
        client = create_client_with_mocks(mock_auth, str(uuid7()))

        # Empty permission list means all (zero) permissions satisfied
        response = client.get("/test/empty-all")

        # Should allow access as all zero permissions are satisfied
        assert response.status_code == 200
