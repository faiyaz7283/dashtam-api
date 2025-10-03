"""Database integration tests for model persistence.

This module tests actual database operations with real database connections:
- User CRUD operations
- Provider CRUD operations
- Provider connection cascade operations
- Token storage and retrieval
- Audit log persistence
- Relationship loading and eager loading
- Database constraints validation
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from sqlmodel import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from src.models.user import User
from src.models.provider import (
    Provider,
    ProviderConnection,
    ProviderToken,
    ProviderAuditLog,
    ProviderStatus,
)


class TestUserCRUDOperations:
    """Test User model CRUD operations with real database."""

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_user_create_and_read(self, db_session):
        """Test creating and reading users from database."""
        # Create user
        user = User(
            email="crud_test@example.com", name="CRUD Test User", is_verified=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Verify user was created with proper fields
        assert user.id is not None
        assert user.email == "crud_test@example.com"
        assert user.name == "CRUD Test User"
        assert user.is_verified is True
        assert user.created_at is not None
        assert user.updated_at is not None

        # Test reading user back from database
        result = await db_session.execute(
            select(User).where(User.email == "crud_test@example.com")
        )
        retrieved_user = result.scalar_one_or_none()

        assert retrieved_user is not None
        assert retrieved_user.id == user.id
        assert retrieved_user.email == user.email
        assert retrieved_user.name == user.name

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_user_update_operations(self, db_session, test_user):
        """Test updating user records."""
        original_updated_at = test_user.updated_at

        # Update user
        test_user.name = "Updated Test User"
        test_user.is_verified = False
        await db_session.commit()
        await db_session.refresh(test_user)

        # Verify update
        assert test_user.name == "Updated Test User"
        assert test_user.is_verified is False
        assert test_user.updated_at > original_updated_at

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_user_delete_operations(self, db_session):
        """Test deleting user records."""
        # Create temporary user
        user = User(email="delete_test@example.com", name="Delete Test")
        db_session.add(user)
        await db_session.commit()
        user_id = user.id

        # Delete user
        await db_session.delete(user)
        await db_session.commit()

        # Verify deletion
        result = await db_session.execute(select(User).where(User.id == user_id))
        deleted_user = result.scalar_one_or_none()
        assert deleted_user is None

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_user_email_uniqueness_constraint(self, db_session, test_user):
        """Test that email uniqueness is enforced at database level."""
        duplicate_user = User(
            email=test_user.email,  # Same email
            name="Duplicate User",
        )
        db_session.add(duplicate_user)

        # Should raise integrity error
        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_user_active_providers_relationship(self, db_session, test_user):
        """Test user relationship with providers."""
        # Create providers for user
        provider1 = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Schwab Account 1"
        )
        provider2 = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Schwab Account 2"
        )
        db_session.add_all([provider1, provider2])
        await db_session.commit()

        # Load user with providers
        result = await db_session.execute(
            select(User)
            .options(selectinload(User.providers))
            .where(User.id == test_user.id)
        )
        user_with_providers = result.scalar_one()

        # Verify relationship
        assert len(user_with_providers.providers) == 2
        provider_aliases = {p.alias for p in user_with_providers.providers}
        assert "Schwab Account 1" in provider_aliases
        assert "Schwab Account 2" in provider_aliases


class TestProviderCRUDOperations:
    """Test Provider model CRUD operations with real database."""

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_provider_create_and_read(self, db_session, test_user):
        """Test creating and reading providers."""
        provider = Provider(
            user_id=test_user.id,
            provider_key="schwab",
            alias="Integration Test Provider",
        )
        db_session.add(provider)
        await db_session.commit()
        await db_session.refresh(provider)

        # Verify provider creation
        assert provider.id is not None
        assert provider.user_id == test_user.id
        assert provider.provider_key == "schwab"
        assert provider.alias == "Integration Test Provider"
        assert provider.created_at is not None

        # Read back from database
        result = await db_session.execute(
            select(Provider).where(Provider.id == provider.id)
        )
        retrieved_provider = result.scalar_one()

        assert retrieved_provider.alias == "Integration Test Provider"
        assert retrieved_provider.user_id == test_user.id

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_provider_user_alias_uniqueness(self, db_session, test_user):
        """Test that user can't have duplicate aliases."""
        # Create first provider
        provider1 = Provider(
            user_id=test_user.id, provider_key="schwab", alias="My Schwab Account"
        )
        db_session.add(provider1)
        await db_session.commit()

        # Try to create duplicate alias for same user
        provider2 = Provider(
            user_id=test_user.id,
            provider_key="schwab",
            alias="My Schwab Account",  # Same alias
        )
        db_session.add(provider2)

        # Should raise integrity error
        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_provider_update_operations(self, db_session, test_provider):
        """Test updating provider records."""
        original_updated_at = test_provider.updated_at

        # Update provider
        test_provider.alias = "Updated Provider Alias"
        await db_session.commit()
        await db_session.refresh(test_provider)

        # Verify update
        assert test_provider.alias == "Updated Provider Alias"
        assert test_provider.updated_at > original_updated_at


class TestProviderConnectionOperations:
    """Test ProviderConnection model operations and cascading."""

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_connection_creation_and_relationship(
        self, db_session, test_provider
    ):
        """Test creating provider connections."""
        connection = ProviderConnection(
            provider_id=test_provider.id,
            status=ProviderStatus.ACTIVE,
            accounts_count=3,
            accounts_list=["12345", "67890", "11111"],
        )
        db_session.add(connection)
        await db_session.commit()
        await db_session.refresh(connection)

        # Verify connection
        assert connection.id is not None
        assert connection.provider_id == test_provider.id
        assert connection.status == ProviderStatus.ACTIVE
        assert connection.accounts_count == 3
        assert len(connection.accounts_list) == 3

        # Test relationship loading
        result = await db_session.execute(
            select(Provider)
            .options(selectinload(Provider.connection))
            .where(Provider.id == test_provider.id)
        )
        provider_with_connection = result.scalar_one()

        assert provider_with_connection.connection is not None
        assert provider_with_connection.connection.id == connection.id

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_connection_status_updates(
        self, db_session, test_provider_with_connection
    ):
        """Test connection status management."""
        connection = test_provider_with_connection.connection

        # Test status transitions
        connection.status = ProviderStatus.ERROR
        connection.error_message = "Test error message"
        connection.error_count = 1
        await db_session.commit()

        # Verify status update
        await db_session.refresh(connection)
        assert connection.status == ProviderStatus.ERROR
        assert connection.error_message == "Test error message"
        assert connection.error_count == 1

        # Test connection recovery
        connection.mark_connected()
        await db_session.commit()
        await db_session.refresh(connection)

        assert connection.status == ProviderStatus.ACTIVE
        assert connection.error_count == 0
        assert connection.error_message is None

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_connection_cascade_delete(self, db_session, test_user):
        """Test that deleting provider cascades to connection."""
        # Create provider with connection
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Cascade Test Provider"
        )
        db_session.add(provider)
        await db_session.flush()  # Get provider.id

        connection = ProviderConnection(
            provider_id=provider.id, status=ProviderStatus.ACTIVE
        )
        db_session.add(connection)
        await db_session.commit()

        connection_id = connection.id

        # Delete provider
        await db_session.delete(provider)
        await db_session.commit()

        # Verify cascade delete
        result = await db_session.execute(
            select(ProviderConnection).where(ProviderConnection.id == connection_id)
        )
        deleted_connection = result.scalar_one_or_none()
        assert deleted_connection is None


class TestTokenStorageAndRetrieval:
    """Test ProviderToken storage and retrieval operations."""

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_token_creation_and_storage(
        self, db_session, test_provider_with_connection
    ):
        """Test creating and storing encrypted tokens."""
        connection = test_provider_with_connection.connection

        token = ProviderToken(
            connection_id=connection.id,
            access_token_encrypted="encrypted_access_token_data",
            refresh_token_encrypted="encrypted_refresh_token_data",
            id_token="jwt_id_token_12345",
            token_type="Bearer",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            scope="api read write",
            refresh_count=0,
        )
        db_session.add(token)
        await db_session.commit()
        await db_session.refresh(token)

        # Verify token storage
        assert token.id is not None
        assert token.connection_id == connection.id
        assert token.access_token_encrypted == "encrypted_access_token_data"
        assert token.refresh_token_encrypted == "encrypted_refresh_token_data"
        assert token.id_token == "jwt_id_token_12345"
        assert token.scope == "api read write"
        assert token.refresh_count == 0

        # Test token properties
        assert token.is_expired is False
        assert token.is_expiring_soon is False
        assert token.needs_refresh is False

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_token_expiration_logic(
        self, db_session, test_provider_with_connection
    ):
        """Test token expiration detection."""
        connection = test_provider_with_connection.connection

        # Create expired token
        expired_token = ProviderToken(
            connection_id=connection.id,
            access_token_encrypted="expired_token",
            expires_at=datetime.utcnow() - timedelta(minutes=10),
        )
        db_session.add(expired_token)
        await db_session.commit()
        await db_session.refresh(expired_token)

        # Test expiration properties
        assert expired_token.is_expired is True
        assert expired_token.needs_refresh is True

        # Create token expiring soon
        expiring_token = ProviderToken(
            connection_id=connection.id,
            access_token_encrypted="expiring_token",
            expires_at=datetime.utcnow()
            + timedelta(minutes=3),  # Within 5 minute window
        )
        db_session.add(expiring_token)
        await db_session.commit()
        await db_session.refresh(expiring_token)

        assert expiring_token.is_expired is False
        assert expiring_token.is_expiring_soon is True
        assert expiring_token.needs_refresh is True

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_token_refresh_updates(
        self, db_session, test_provider_with_connection
    ):
        """Test token update operations during refresh."""
        connection = test_provider_with_connection.connection

        token = ProviderToken(
            connection_id=connection.id,
            access_token_encrypted="old_access_token",
            refresh_token_encrypted="old_refresh_token",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
            refresh_count=5,
        )
        db_session.add(token)
        await db_session.commit()

        # Simulate token refresh
        token.update_tokens(
            access_token_encrypted="new_access_token",
            refresh_token_encrypted="new_refresh_token",
            expires_in=3600,
            id_token="new_id_token",
        )
        await db_session.commit()
        await db_session.refresh(token)

        # Verify updates
        assert token.access_token_encrypted == "new_access_token"
        assert token.refresh_token_encrypted == "new_refresh_token"
        assert token.id_token == "new_id_token"
        assert token.refresh_count == 6
        assert token.last_refreshed_at is not None
        assert token.expires_at > datetime.utcnow()

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_token_connection_relationship(
        self, db_session, test_provider_with_connection
    ):
        """Test token relationship with connection."""
        connection = test_provider_with_connection.connection

        token = ProviderToken(
            connection_id=connection.id,
            access_token_encrypted="relationship_test_token",
        )
        db_session.add(token)
        await db_session.commit()

        # Load connection with token
        result = await db_session.execute(
            select(ProviderConnection)
            .options(selectinload(ProviderConnection.token))
            .where(ProviderConnection.id == connection.id)
        )
        connection_with_token = result.scalar_one()

        assert connection_with_token.token is not None
        assert (
            connection_with_token.token.access_token_encrypted
            == "relationship_test_token"
        )


class TestAuditLogPersistence:
    """Test ProviderAuditLog persistence and querying."""

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_audit_log_creation(
        self, db_session, test_provider_with_connection, test_user
    ):
        """Test creating audit log entries."""
        connection = test_provider_with_connection.connection

        audit_log = ProviderAuditLog(
            connection_id=connection.id,
            user_id=test_user.id,
            action="test_action",
            details={
                "test_key": "test_value",
                "provider_key": "schwab",
                "success": True,
            },
            ip_address="192.168.1.100",
            user_agent="Test Browser 1.0",
        )
        db_session.add(audit_log)
        await db_session.commit()
        await db_session.refresh(audit_log)

        # Verify audit log
        assert audit_log.id is not None
        assert audit_log.connection_id == connection.id
        assert audit_log.user_id == test_user.id
        assert audit_log.action == "test_action"
        assert audit_log.details["test_key"] == "test_value"
        assert audit_log.details["success"] is True
        assert audit_log.ip_address == "192.168.1.100"
        assert audit_log.user_agent == "Test Browser 1.0"
        assert audit_log.created_at is not None

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_audit_log_factory_method(
        self, db_session, test_provider_with_connection, test_user
    ):
        """Test audit log factory method."""
        connection = test_provider_with_connection.connection

        audit_log = ProviderAuditLog.log_action(
            connection_id=connection.id,
            user_id=test_user.id,
            action="factory_test",
            details={"method": "factory"},
            ip_address="10.0.0.1",
        )
        db_session.add(audit_log)
        await db_session.commit()

        # Verify factory-created log
        assert audit_log.action == "factory_test"
        assert audit_log.details["method"] == "factory"
        assert audit_log.ip_address == "10.0.0.1"

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_audit_log_querying(
        self, db_session, test_provider_with_connection, test_user
    ):
        """Test querying audit logs."""
        connection = test_provider_with_connection.connection

        # Create multiple audit logs
        actions = ["action_1", "action_2", "action_3"]
        for action in actions:
            audit_log = ProviderAuditLog(
                connection_id=connection.id,
                user_id=test_user.id,
                action=action,
                details={"action_type": action},
            )
            db_session.add(audit_log)

        await db_session.commit()

        # Query all logs for this connection
        result = await db_session.execute(
            select(ProviderAuditLog)
            .where(ProviderAuditLog.connection_id == connection.id)
            .order_by(ProviderAuditLog.created_at.desc())
        )
        all_logs = result.scalars().all()

        assert len(all_logs) == 3

        # Query specific action
        result = await db_session.execute(
            select(ProviderAuditLog).where(
                ProviderAuditLog.connection_id == connection.id,
                ProviderAuditLog.action == "action_2",
            )
        )
        specific_log = result.scalar_one()

        assert specific_log.action == "action_2"
        assert specific_log.details["action_type"] == "action_2"


class TestRelationshipLoading:
    """Test complex relationship loading and eager loading."""

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_full_provider_relationship_loading(self, db_session, test_user):
        """Test loading complete provider relationship chain."""
        # Create provider with full relationship chain
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Full Chain Test"
        )
        db_session.add(provider)
        await db_session.flush()

        connection = ProviderConnection(
            provider_id=provider.id, status=ProviderStatus.ACTIVE, accounts_count=2
        )
        db_session.add(connection)
        await db_session.flush()

        token = ProviderToken(
            connection_id=connection.id, access_token_encrypted="full_chain_token"
        )
        db_session.add(token)

        audit_log = ProviderAuditLog(
            connection_id=connection.id, user_id=test_user.id, action="full_chain_test"
        )
        db_session.add(audit_log)
        await db_session.commit()

        # Load with all relationships
        result = await db_session.execute(
            select(Provider)
            .options(
                selectinload(Provider.connection).selectinload(
                    ProviderConnection.token
                ),
                selectinload(Provider.connection).selectinload(
                    ProviderConnection.audit_logs
                ),
            )
            .where(Provider.id == provider.id)
        )
        full_provider = result.scalar_one()

        # Verify all relationships loaded
        assert full_provider.connection is not None
        assert full_provider.connection.token is not None
        assert len(full_provider.connection.audit_logs) == 1
        assert (
            full_provider.connection.token.access_token_encrypted == "full_chain_token"
        )
        assert full_provider.connection.audit_logs[0].action == "full_chain_test"

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_user_providers_with_connections(self, db_session, test_user):
        """Test loading user with all providers and their connections."""
        # Create multiple providers with connections
        for i in range(3):
            provider = Provider(
                user_id=test_user.id, provider_key="schwab", alias=f"Provider {i}"
            )
            db_session.add(provider)
            await db_session.flush()

            connection = ProviderConnection(
                provider_id=provider.id, status=ProviderStatus.ACTIVE
            )
            db_session.add(connection)

        await db_session.commit()

        # Load user with all providers and connections
        result = await db_session.execute(
            select(User)
            .options(selectinload(User.providers).selectinload(Provider.connection))
            .where(User.id == test_user.id)
        )
        user_with_all = result.scalar_one()

        # Verify relationships
        assert len(user_with_all.providers) == 3
        for provider in user_with_all.providers:
            assert provider.connection is not None
            assert provider.connection.status == ProviderStatus.ACTIVE


class TestDatabaseConstraints:
    """Test database constraints and validation."""

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_foreign_key_constraints(self, db_session):
        """Test foreign key constraint enforcement."""
        fake_user_id = uuid4()

        # Try to create provider with invalid user_id
        provider = Provider(
            user_id=fake_user_id, provider_key="schwab", alias="Invalid User Provider"
        )
        db_session.add(provider)

        # Should raise foreign key constraint error
        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_required_field_constraints(self, db_session, test_user):
        """Test that required fields are enforced."""
        # Try to create provider without required fields
        incomplete_provider = Provider(user_id=test_user.id)
        # Missing provider_key and alias
        db_session.add(incomplete_provider)

        # Should raise constraint error
        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    @pytest.mark.database
    async def test_unique_constraint_validation(self, db_session, test_user):
        """Test unique constraint enforcement."""
        # Create first provider
        provider1 = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Unique Test"
        )
        db_session.add(provider1)
        await db_session.commit()

        # Try to create second provider with same user/alias combination
        provider2 = Provider(
            user_id=test_user.id,
            provider_key="plaid",  # Different provider_key
            alias="Unique Test",  # Same alias - should fail
        )
        db_session.add(provider2)

        # Should raise unique constraint error
        with pytest.raises(IntegrityError):
            await db_session.commit()
