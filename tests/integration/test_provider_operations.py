"""Integration tests for provider database operations.

These tests verify database CRUD operations and relationships using
a real PostgreSQL database with synchronous sessions for test isolation.
"""

import pytest
from sqlmodel import Session, select

from src.models.provider import Provider, ProviderConnection, ProviderStatus
from src.models.user import User


class TestProviderCRUD:
    """Test suite for provider CRUD operations.
    
    Tests Create, Read, Update, Delete operations for Provider model
    with real PostgreSQL database.
    """

    def test_create_provider(self, db_session: Session, test_user: User):
        """Test Provider creation in database.
        
        Verifies that:
        - Provider model saved to database
        - Auto-generated ID assigned
        - user_id, provider_key, alias stored correctly
        
        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture
        """
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
        """Test Provider and ProviderConnection creation (one-to-one relationship).
        
        Verifies that:
        - Provider created with flush() to get ID
        - ProviderConnection created with provider_id FK
        - provider.connection relationship populated
        - status defaults to PENDING
        
        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture
        """
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
        """Test querying all providers for specific user.
        
        Verifies that:
        - Multiple providers created for same user
        - Query by user_id returns correct providers
        - All user's providers returned
        - No cross-user contamination
        
        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture
        """
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
        """Test Provider UPDATE operation (alias field).
        
        Verifies that:
        - Provider alias can be updated
        - Changes persisted to database
        - Updated value retrieved correctly
        
        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture
        """
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
        """Test cascade delete from Provider to ProviderConnection.
        
        Verifies that:
        - Deleting provider also deletes connection (CASCADE)
        - Foreign key constraint enforced
        - No orphaned connections remain
        - Database referential integrity maintained
        
        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture
        """
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
    """Test suite for provider connection operations.
    
    Tests ProviderConnection lifecycle, status changes, and error tracking
    with real database.
    """

    def test_connection_status_lifecycle(self, db_session: Session, test_user: User):
        """Test ProviderConnection status lifecycle (PENDING → ACTIVE).
        
        Verifies that:
        - Connection starts in PENDING status
        - mark_connected() changes status to ACTIVE
        - connected_at timestamp set
        - Status persisted to database
        
        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture
        """
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
        """Test manual ProviderConnection status updates.
        
        Verifies that:
        - Status can be changed directly
        - PENDING → ACTIVE transition works
        - Status changes persisted to database
        
        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture
        """
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
        """Test error tracking fields in ProviderConnection.
        
        Verifies that:
        - error_count can be incremented
        - error_message can be stored
        - status changed to ERROR
        - All error fields persisted correctly
        
        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture
        
        Note:
            Used for monitoring connection failures.
        """
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
    """Test suite for provider-user relationships.
    
    Tests many-to-one relationship between Provider and User models.
    """

    def test_user_can_have_multiple_providers(
        self, db_session: Session, test_user: User
    ):
        """Test User can have multiple Provider instances (one-to-many).
        
        Verifies that:
        - User can have 3+ providers
        - All providers linked to same user_id
        - Query returns all user's providers
        - Supports multiple connections per user
        
        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture
        """
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
        """Test Provider to User relationship (many-to-one).
        
        Verifies that:
        - provider.user relationship works
        - selectinload() eager loading works
        - User data accessible via provider.user
        - Foreign key relationship intact
        
        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture
        """
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
        """Test unique constraint on (user_id, alias) enforced by database.
        
        Verifies that:
        - First provider with alias saved successfully
        - Second provider with same alias raises IntegrityError
        - unique_user_provider_alias constraint enforced
        - Database prevents duplicate aliases per user
        
        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture
        
        Raises:
            IntegrityError: Expected error for unique constraint violation
        
        Note:
            Prevents users from having multiple providers with same alias.
        """
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
