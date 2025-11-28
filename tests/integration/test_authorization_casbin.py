"""Integration tests for CasbinAdapter and RBAC policy enforcement.

Tests cover:
- Policy loading from database
- Permission checking with role hierarchy (enforcer direct)
- Role assignment and revocation
- CasbinAdapter with mocked dependencies

Architecture:
- Integration tests with REAL PostgreSQL database
- Tests actual Casbin enforcer with PostgreSQL adapter
- Two test levels:
  1. Enforcer direct tests - validate Casbin works with our policies
  2. Adapter tests - validate CasbinAdapter integrates correctly

Fixtures:
- casbin_enforcer: Real Casbin enforcer with PostgreSQL adapter (local)
- mock_cache, mock_audit, mock_event_bus, mock_logger: From conftest.py (centralized)

Reference:
    - src/infrastructure/authorization/casbin_adapter.py
    - docs/architecture/authorization-architecture.md
"""

import os
from uuid import uuid4

import pytest
import pytest_asyncio
import casbin
from casbin_async_sqlalchemy_adapter import Adapter as CasbinSQLAdapter

from src.core.config import settings
from src.infrastructure.authorization.casbin_adapter import CasbinAdapter


# =============================================================================
# Local Fixtures (Authorization-specific)
# =============================================================================
# Note: mock_cache, mock_audit, mock_event_bus, mock_logger are imported from
# tests/conftest.py automatically by pytest.


@pytest_asyncio.fixture
async def casbin_enforcer():
    """Create a Casbin enforcer with real PostgreSQL adapter.

    Uses the same model.conf as production but fresh database.
    This fixture is authorization-specific and not centralized.
    """
    # Model config path
    model_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "src",
        "infrastructure",
        "authorization",
        "model.conf",
    )

    # Create PostgreSQL adapter
    adapter = CasbinSQLAdapter(settings.database_url)

    # Create async enforcer
    enforcer = casbin.AsyncEnforcer(model_path, adapter)

    # Load existing policies from database (seeded by migrations)
    await enforcer.load_policy()

    yield enforcer


@pytest_asyncio.fixture
async def casbin_adapter(
    casbin_enforcer,
    mock_cache,
    mock_audit,
    mock_event_bus,
    mock_logger,
):
    """Create CasbinAdapter with real enforcer and mocked dependencies."""
    return CasbinAdapter(
        enforcer=casbin_enforcer,
        cache=mock_cache,
        audit=mock_audit,
        event_bus=mock_event_bus,
        logger=mock_logger,
    )


# =============================================================================
# Policy Loading Tests
# =============================================================================


@pytest.mark.integration
class TestPolicyLoading:
    """Test that policies are correctly loaded from database."""

    @pytest.mark.asyncio
    async def test_policies_loaded_from_database(self, casbin_enforcer):
        """Test that seeded policies are loaded from database."""
        # Check that policies exist (seeded by migrations)
        # Note: get_policy() is synchronous in casbin
        policies = casbin_enforcer.get_policy()

        # Should have permission policies (p rules)
        assert len(policies) > 0, "No policies loaded from database"

    @pytest.mark.asyncio
    async def test_role_hierarchy_loaded(self, casbin_enforcer):
        """Test that role hierarchy is loaded from database."""
        # Check role hierarchy (g rules)
        # admin inherits from user, user inherits from readonly
        # Note: get_grouping_policy() is synchronous in casbin
        roles = casbin_enforcer.get_grouping_policy()

        # Should have role inheritance rules
        assert len(roles) >= 2, "Role hierarchy not loaded"

        # Verify expected hierarchy exists
        role_pairs = [(r[0], r[1]) for r in roles]
        assert ("admin", "user") in role_pairs, "admin -> user inheritance missing"
        assert ("user", "readonly") in role_pairs, (
            "user -> readonly inheritance missing"
        )


# =============================================================================
# Enforcer Direct Tests (Validate Casbin Works)
# =============================================================================


@pytest.mark.integration
class TestEnforcerDirect:
    """Test Casbin enforcer directly without adapter layer.

    These tests validate that our RBAC policies and role hierarchy
    work correctly with the Casbin enforcer before testing through
    the CasbinAdapter layer.
    """

    @pytest.mark.asyncio
    async def test_readonly_can_read_accounts_direct(self, casbin_enforcer):
        """Test readonly role can read accounts (direct enforcer)."""
        user_id = str(uuid4())
        await casbin_enforcer.add_role_for_user(user_id, "readonly")

        # Test directly with enforcer (enforce is sync, even on AsyncEnforcer)
        allowed = casbin_enforcer.enforce(user_id, "accounts", "read")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_readonly_cannot_write_accounts_direct(self, casbin_enforcer):
        """Test readonly role cannot write to accounts (direct enforcer)."""
        user_id = str(uuid4())
        await casbin_enforcer.add_role_for_user(user_id, "readonly")

        allowed = casbin_enforcer.enforce(user_id, "accounts", "write")
        assert allowed is False

    @pytest.mark.asyncio
    async def test_user_inherits_readonly_direct(self, casbin_enforcer):
        """Test user role inherits readonly permissions (direct enforcer)."""
        user_id = str(uuid4())
        await casbin_enforcer.add_role_for_user(user_id, "user")

        # User should inherit readonly's read permission
        allowed = casbin_enforcer.enforce(user_id, "accounts", "read")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_user_can_write_accounts_direct(self, casbin_enforcer):
        """Test user role can write to accounts (direct enforcer)."""
        user_id = str(uuid4())
        await casbin_enforcer.add_role_for_user(user_id, "user")

        allowed = casbin_enforcer.enforce(user_id, "accounts", "write")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_admin_has_all_permissions_direct(self, casbin_enforcer):
        """Test admin role has all permissions (direct enforcer)."""
        user_id = str(uuid4())
        await casbin_enforcer.add_role_for_user(user_id, "admin")

        # Admin should have access to admin-only resources (enforce is sync)
        assert casbin_enforcer.enforce(user_id, "admin", "read") is True
        assert casbin_enforcer.enforce(user_id, "admin", "write") is True
        assert casbin_enforcer.enforce(user_id, "users", "write") is True

    @pytest.mark.asyncio
    async def test_user_cannot_access_admin_direct(self, casbin_enforcer):
        """Test user role cannot access admin resources (direct enforcer)."""
        user_id = str(uuid4())
        await casbin_enforcer.add_role_for_user(user_id, "user")

        allowed = casbin_enforcer.enforce(user_id, "admin", "read")
        assert allowed is False

    @pytest.mark.asyncio
    async def test_unassigned_user_denied_direct(self, casbin_enforcer):
        """Test user without role is denied (direct enforcer)."""
        user_id = str(uuid4())  # No role assigned

        allowed = casbin_enforcer.enforce(user_id, "accounts", "read")
        assert allowed is False


# =============================================================================
# CasbinAdapter Tests (With Mocked Dependencies)
# =============================================================================


@pytest.mark.integration
class TestCasbinAdapterPermissions:
    """Test CasbinAdapter permission checking.

    These tests use the CasbinAdapter with mocked cache/audit/events
    to validate the adapter correctly delegates to the enforcer.
    """

    @pytest.mark.asyncio
    async def test_adapter_checks_permission(self, casbin_adapter, casbin_enforcer):
        """Test adapter delegates permission check to enforcer."""
        user_id = uuid4()
        await casbin_enforcer.add_role_for_user(str(user_id), "readonly")

        allowed = await casbin_adapter.check_permission(
            user_id=user_id,
            resource="accounts",
            action="read",
        )

        assert allowed is True

    @pytest.mark.asyncio
    async def test_adapter_denies_unauthorized(self, casbin_adapter, casbin_enforcer):
        """Test adapter denies unauthorized access."""
        user_id = uuid4()
        await casbin_enforcer.add_role_for_user(str(user_id), "readonly")

        allowed = await casbin_adapter.check_permission(
            user_id=user_id,
            resource="accounts",
            action="write",
        )

        assert allowed is False

    @pytest.mark.asyncio
    async def test_adapter_denies_unassigned_user(self, casbin_adapter):
        """Test adapter denies user without any role."""
        user_id = uuid4()  # No role assigned

        allowed = await casbin_adapter.check_permission(
            user_id=user_id,
            resource="accounts",
            action="read",
        )

        assert allowed is False


# =============================================================================
# Role Operations Tests
# =============================================================================


@pytest.mark.integration
class TestRoleOperations:
    """Test role assignment and revocation."""

    @pytest.mark.asyncio
    async def test_get_roles_for_user(self, casbin_adapter, casbin_enforcer):
        """Test getting roles assigned to a user."""
        # Assign role
        user_id = uuid4()
        await casbin_enforcer.add_role_for_user(str(user_id), "user")

        # Get roles
        roles = await casbin_adapter.get_roles_for_user(user_id)

        assert "user" in roles

    @pytest.mark.asyncio
    async def test_has_role_returns_true_for_assigned_role(
        self, casbin_adapter, casbin_enforcer
    ):
        """Test has_role returns True for assigned role."""
        # Assign role
        user_id = uuid4()
        await casbin_enforcer.add_role_for_user(str(user_id), "admin")

        # Check has_role
        has_admin = await casbin_adapter.has_role(user_id, "admin")

        assert has_admin is True

    @pytest.mark.asyncio
    async def test_has_role_returns_false_for_unassigned_role(
        self, casbin_adapter, casbin_enforcer
    ):
        """Test has_role returns False for unassigned role."""
        # Assign user role (not admin)
        user_id = uuid4()
        await casbin_enforcer.add_role_for_user(str(user_id), "user")

        # Check for admin role
        has_admin = await casbin_adapter.has_role(user_id, "admin")

        assert has_admin is False

    @pytest.mark.asyncio
    async def test_assign_role_success(self, casbin_adapter, casbin_enforcer):
        """Test successful role assignment."""
        user_id = uuid4()
        admin_id = uuid4()

        # Assign role via adapter
        result = await casbin_adapter.assign_role(
            user_id=user_id,
            role="user",
            assigned_by=admin_id,
        )

        assert result is True

        # Verify assignment
        has_role = await casbin_adapter.has_role(user_id, "user")
        assert has_role is True

    @pytest.mark.asyncio
    async def test_assign_role_fails_if_already_has_role(
        self, casbin_adapter, casbin_enforcer
    ):
        """Test assigning same role twice returns False."""
        user_id = uuid4()
        admin_id = uuid4()

        # First assignment
        await casbin_adapter.assign_role(
            user_id=user_id,
            role="user",
            assigned_by=admin_id,
        )

        # Second assignment should fail
        result = await casbin_adapter.assign_role(
            user_id=user_id,
            role="user",
            assigned_by=admin_id,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_role_success(self, casbin_adapter, casbin_enforcer):
        """Test successful role revocation."""
        user_id = uuid4()
        admin_id = uuid4()

        # First assign role
        await casbin_enforcer.add_role_for_user(str(user_id), "user")

        # Revoke via adapter
        result = await casbin_adapter.revoke_role(
            user_id=user_id,
            role="user",
            revoked_by=admin_id,
            reason="Testing revocation",
        )

        assert result is True

        # Verify revocation
        has_role = await casbin_adapter.has_role(user_id, "user")
        assert has_role is False

    @pytest.mark.asyncio
    async def test_revoke_role_fails_if_not_assigned(
        self, casbin_adapter, casbin_enforcer
    ):
        """Test revoking unassigned role returns False."""
        user_id = uuid4()
        admin_id = uuid4()

        # Try to revoke role user doesn't have
        result = await casbin_adapter.revoke_role(
            user_id=user_id,
            role="admin",
            revoked_by=admin_id,
        )

        assert result is False


# =============================================================================
# Cache Integration Tests
# =============================================================================


@pytest.mark.integration
class TestCacheIntegration:
    """Test cache behavior during authorization checks."""

    @pytest.mark.asyncio
    async def test_permission_check_caches_result(
        self, casbin_adapter, casbin_enforcer, mock_cache
    ):
        """Test that permission check results are cached."""
        # Assign role
        user_id = uuid4()
        await casbin_enforcer.add_role_for_user(str(user_id), "readonly")

        # First check - should miss cache and set
        await casbin_adapter.check_permission(
            user_id=user_id,
            resource="accounts",
            action="read",
        )

        # Verify cache.set was called
        mock_cache.set.assert_called()

    @pytest.mark.asyncio
    async def test_role_change_invalidates_cache(
        self, casbin_adapter, casbin_enforcer, mock_cache
    ):
        """Test that role assignment invalidates user's cache."""
        user_id = uuid4()
        admin_id = uuid4()

        # Assign role
        await casbin_adapter.assign_role(
            user_id=user_id,
            role="user",
            assigned_by=admin_id,
        )

        # Verify cache invalidation was called
        mock_cache.delete_pattern.assert_called()


# =============================================================================
# Audit Integration Tests
# =============================================================================


@pytest.mark.integration
class TestAuditIntegration:
    """Test audit logging during authorization checks."""

    @pytest.mark.asyncio
    async def test_permission_check_audits_result(
        self, casbin_adapter, casbin_enforcer, mock_audit
    ):
        """Test that permission checks are audited."""
        # Assign role
        user_id = uuid4()
        await casbin_enforcer.add_role_for_user(str(user_id), "readonly")

        # Check permission
        await casbin_adapter.check_permission(
            user_id=user_id,
            resource="accounts",
            action="read",
        )

        # Verify audit.record was called
        mock_audit.record.assert_called()

        # Verify audit action
        call_kwargs = mock_audit.record.call_args.kwargs
        assert call_kwargs["user_id"] == user_id
        assert call_kwargs["resource_type"] == "authorization"


# =============================================================================
# Event Integration Tests
# =============================================================================


@pytest.mark.integration
class TestEventIntegration:
    """Test domain events during role operations."""

    @pytest.mark.asyncio
    async def test_assign_role_publishes_events(
        self, casbin_adapter, casbin_enforcer, mock_event_bus
    ):
        """Test that role assignment publishes domain events."""
        user_id = uuid4()
        admin_id = uuid4()

        # Assign role
        await casbin_adapter.assign_role(
            user_id=user_id,
            role="user",
            assigned_by=admin_id,
        )

        # Verify events published (attempt + success)
        assert mock_event_bus.publish.call_count >= 2

    @pytest.mark.asyncio
    async def test_revoke_role_publishes_events(
        self, casbin_adapter, casbin_enforcer, mock_event_bus
    ):
        """Test that role revocation publishes domain events."""
        user_id = uuid4()
        admin_id = uuid4()

        # First assign role
        await casbin_enforcer.add_role_for_user(str(user_id), "user")
        mock_event_bus.publish.reset_mock()

        # Revoke role
        await casbin_adapter.revoke_role(
            user_id=user_id,
            role="user",
            revoked_by=admin_id,
        )

        # Verify events published (attempt + success)
        assert mock_event_bus.publish.call_count >= 2
