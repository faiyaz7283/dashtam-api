"""Integration tests for provider database operations.

These tests verify database CRUD operations and relationships using
a real PostgreSQL database with synchronous sessions for test isolation.
"""

import pytest
from sqlmodel import Session, select

from src.models.provider import Provider, ProviderConnection, ProviderStatus
from src.models.user import User


class TestProviderCRUD:
    """Test suite for provider CRUD operations."""

    def test_create_provider(self, db_session: Session, test_user: User):
        """Test creating a provider instance."""
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="My Schwab Account"
        )
        db_session.add(provider)
        db_session.commit()
        db_session.refresh(provider)

        # Verify provider was created
        assert provider.id is not None
        assert provider.user_id == test_user.id
        assert provider.provider_key == "schwab"
        assert provider.alias == "My Schwab Account"

    def test_create_provider_with_connection(
        self, db_session: Session, test_user: User
    ):
        """Test creating a provider with a connection."""
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Test Schwab"
        )
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(
            provider_id=provider.id, status=ProviderStatus.PENDING
        )
        db_session.add(connection)
        db_session.commit()
        db_session.refresh(provider)

        # Verify relationship
        assert provider.connection is not None
        assert provider.connection.status == ProviderStatus.PENDING
        assert provider.connection.provider_id == provider.id

    def test_list_user_providers(self, db_session: Session, test_user: User):
        """Test listing all providers for a user."""
        # Create multiple providers
        providers = [
            Provider(user_id=test_user.id, provider_key="schwab", alias="Schwab 1"),
            Provider(user_id=test_user.id, provider_key="schwab", alias="Schwab 2"),
        ]
        for provider in providers:
            db_session.add(provider)
        db_session.commit()

        # Query user's providers
        result = db_session.execute(
            select(Provider).where(Provider.user_id == test_user.id)
        )
        user_providers = result.scalars().all()

        assert len(user_providers) >= 2
        aliases = [p.alias for p in user_providers]
        assert "Schwab 1" in aliases
        assert "Schwab 2" in aliases

    def test_update_provider_alias(self, db_session: Session, test_user: User):
        """Test updating a provider's alias."""
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Old Name"
        )
        db_session.add(provider)
        db_session.commit()
        db_session.refresh(provider)

        # Update alias
        provider.alias = "New Name"
        db_session.commit()
        db_session.refresh(provider)

        assert provider.alias == "New Name"

    def test_delete_provider_cascades(self, db_session: Session, test_user: User):
        """Test that deleting a provider cascades to connection."""
        provider = Provider(user_id=test_user.id, provider_key="schwab", alias="Test")
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.commit()

        provider_id = provider.id
        connection_id = connection.id

        # Delete provider
        db_session.delete(provider)
        db_session.commit()

        # Verify provider is deleted
        result = db_session.execute(select(Provider).where(Provider.id == provider_id))
        assert result.scalar_one_or_none() is None

        # Verify connection is also deleted (cascade)
        result = db_session.execute(
            select(ProviderConnection).where(ProviderConnection.id == connection_id)
        )
        assert result.scalar_one_or_none() is None


class TestProviderConnectionOperations:
    """Test suite for provider connection operations."""

    def test_connection_status_lifecycle(self, db_session: Session, test_user: User):
        """Test connection status changes through lifecycle."""
        provider = Provider(user_id=test_user.id, provider_key="schwab", alias="Test")
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.commit()
        db_session.refresh(connection)

        # Initial status
        assert connection.status == ProviderStatus.PENDING

        # Mark as connected
        connection.mark_connected()
        db_session.commit()
        db_session.refresh(connection)

        assert connection.status == ProviderStatus.ACTIVE
        assert connection.connected_at is not None

    def test_connection_status_changes(self, db_session: Session, test_user: User):
        """Test changing connection status."""
        provider = Provider(user_id=test_user.id, provider_key="schwab", alias="Test")
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(
            provider_id=provider.id, status=ProviderStatus.PENDING
        )
        db_session.add(connection)
        db_session.commit()
        db_session.refresh(connection)

        # Pending status
        assert connection.status == ProviderStatus.PENDING

        # Change to Active status
        connection.status = ProviderStatus.ACTIVE
        db_session.commit()
        db_session.refresh(connection)

        assert connection.status == ProviderStatus.ACTIVE

    def test_connection_error_tracking(self, db_session: Session, test_user: User):
        """Test tracking connection errors."""
        provider = Provider(user_id=test_user.id, provider_key="schwab", alias="Test")
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(
            provider_id=provider.id, status=ProviderStatus.ACTIVE
        )
        db_session.add(connection)
        db_session.commit()
        db_session.refresh(connection)

        # Simulate errors
        connection.error_count = 3
        connection.error_message = "Token refresh failed"
        connection.status = ProviderStatus.ERROR
        db_session.commit()
        db_session.refresh(connection)

        assert connection.error_count == 3
        assert connection.error_message == "Token refresh failed"
        assert connection.status == ProviderStatus.ERROR


class TestProviderUserRelationship:
    """Test suite for provider-user relationships."""

    def test_user_can_have_multiple_providers(
        self, db_session: Session, test_user: User
    ):
        """Test that a user can have multiple provider instances."""
        providers = [
            Provider(user_id=test_user.id, provider_key="schwab", alias=f"Schwab {i}")
            for i in range(3)
        ]
        for provider in providers:
            db_session.add(provider)
        db_session.commit()

        # Query user's providers
        result = db_session.execute(
            select(Provider).where(Provider.user_id == test_user.id)
        )
        user_providers = result.scalars().all()

        assert len(user_providers) >= 3

    def test_provider_belongs_to_user(self, db_session: Session, test_user: User):
        """Test that provider correctly references its user."""
        provider = Provider(user_id=test_user.id, provider_key="schwab", alias="Test")
        db_session.add(provider)
        db_session.commit()
        db_session.refresh(provider)

        # Load provider with user relationship
        from sqlalchemy.orm import selectinload

        result = db_session.execute(
            select(Provider)
            .options(selectinload(Provider.user))
            .where(Provider.id == provider.id)
        )
        loaded_provider = result.scalar_one()

        assert loaded_provider.user is not None
        assert loaded_provider.user.id == test_user.id
        assert loaded_provider.user.email == test_user.email

    def test_unique_alias_per_user_enforced(self, db_session: Session, test_user: User):
        """Test that unique alias constraint is enforced at database level."""
        from sqlalchemy.exc import IntegrityError

        provider1 = Provider(
            user_id=test_user.id, provider_key="schwab", alias="My Account"
        )
        db_session.add(provider1)
        db_session.commit()

        # Try to create another with same alias - should fail with IntegrityError
        provider2 = Provider(
            user_id=test_user.id, provider_key="schwab", alias="My Account"
        )
        db_session.add(provider2)

        # This should raise an IntegrityError due to unique constraint
        with pytest.raises(IntegrityError, match="unique_user_provider_alias"):
            db_session.commit()

        # Rollback the failed transaction
        db_session.rollback()
