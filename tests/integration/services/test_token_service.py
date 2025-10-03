"""Integration tests for token storage and encryption.

These tests verify token storage, encryption, and audit logging
operations with real database interactions using synchronous sessions
for test isolation.

Note: These tests focus on database operations and encryption rather than
the async TokenService directly, since integration tests use sync sessions.
"""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from src.models.provider import (
    Provider,
    ProviderAuditLog,
    ProviderConnection,
    ProviderToken,
)
from src.models.user import User
from src.services.encryption import EncryptionService


class TestTokenStorageIntegration:
    """Integration tests for token storage with real database and encryption."""

    def test_create_and_encrypt_token(self, db_session: Session, test_user: User):
        """Test creating a token with encrypted values."""
        # Create provider and connection
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Test Schwab"
        )
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.flush()

        # Encrypt tokens
        encryption_service = EncryptionService()
        encrypted_access = encryption_service.encrypt("test_access_token_123")
        encrypted_refresh = encryption_service.encrypt("test_refresh_token_456")

        # Create token
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        token = ProviderToken(
            connection_id=connection.id,
            access_token_encrypted=encrypted_access,
            refresh_token_encrypted=encrypted_refresh,
            expires_at=expires_at,
            token_type="Bearer",
            scope="read write",
        )
        db_session.add(token)
        db_session.commit()
        db_session.refresh(token)

        # Verify token is stored
        assert token.id is not None
        assert token.access_token_encrypted != "test_access_token_123"
        assert token.refresh_token_encrypted != "test_refresh_token_456"
        # Database now stores timezone-aware datetimes (TIMESTAMPTZ)
        # Both token.expires_at and expires_at are timezone-aware
        assert (
            abs((token.expires_at - expires_at).total_seconds())
            < 1
        )

        # Verify decryption works
        decrypted_access = encryption_service.decrypt(token.access_token_encrypted)
        decrypted_refresh = encryption_service.decrypt(token.refresh_token_encrypted)
        assert decrypted_access == "test_access_token_123"
        assert decrypted_refresh == "test_refresh_token_456"

    def test_token_without_refresh_token(self, db_session: Session, test_user: User):
        """Test creating a token without refresh token."""
        # Create provider and connection
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Test Schwab"
        )
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.flush()

        # Encrypt access token only
        encryption_service = EncryptionService()
        encrypted_access = encryption_service.encrypt("test_access_token_only")

        # Create token without refresh token
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        token = ProviderToken(
            connection_id=connection.id,
            access_token_encrypted=encrypted_access,
            refresh_token_encrypted=None,  # No refresh token
            expires_at=expires_at,
            token_type="Bearer",
        )
        db_session.add(token)
        db_session.commit()
        db_session.refresh(token)

        # Verify token is stored correctly
        assert token.access_token_encrypted is not None
        assert token.refresh_token_encrypted is None
        # Database now stores timezone-aware datetimes (TIMESTAMPTZ)
        assert (
            abs((token.expires_at - expires_at).total_seconds())
            < 1
        )

    def test_token_expiry_detection(self, db_session: Session, test_user: User):
        """Test that token expiry can be correctly identified.

        Database now uses TIMESTAMP WITH TIME ZONE for financial compliance.
        All datetime comparisons use timezone-aware datetimes.
        """
        # Create provider and connection
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Test Schwab"
        )
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.flush()

        encryption_service = EncryptionService()

        # Create expired token using timezone-aware datetime
        expired_at = datetime.now(timezone.utc) - timedelta(hours=1)
        expired_token = ProviderToken(
            connection_id=connection.id,
            access_token_encrypted=encryption_service.encrypt("expired_token"),
            expires_at=expired_at,
        )
        db_session.add(expired_token)
        db_session.commit()
        db_session.refresh(expired_token)

        # Verify expiry detection works with timezone-aware datetimes
        assert expired_token.needs_refresh is True
        assert expired_token.is_expired is True
        # Verify the stored datetime is in the past
        now_aware = datetime.now(timezone.utc)
        assert expired_token.expires_at < now_aware

    def test_token_update_mechanism(self, db_session: Session, test_user: User):
        """Test updating token values using the update_tokens method."""
        # Create provider and connection
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Test Schwab"
        )
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.flush()

        encryption_service = EncryptionService()

        # Create initial token
        old_expires = datetime.now(timezone.utc) - timedelta(minutes=10)
        token = ProviderToken(
            connection_id=connection.id,
            access_token_encrypted=encryption_service.encrypt("old_access"),
            refresh_token_encrypted=encryption_service.encrypt("old_refresh"),
            expires_at=old_expires,
        )
        db_session.add(token)
        db_session.commit()
        db_session.refresh(token)

        # Update token using update_tokens method
        new_encrypted_access = encryption_service.encrypt("new_access")
        new_encrypted_refresh = encryption_service.encrypt("new_refresh")
        token.update_tokens(
            access_token_encrypted=new_encrypted_access,
            refresh_token_encrypted=new_encrypted_refresh,
            expires_in=3600,
        )
        db_session.commit()
        db_session.refresh(token)

        # Verify token was updated
        assert encryption_service.decrypt(token.access_token_encrypted) == "new_access"
        assert (
            encryption_service.decrypt(token.refresh_token_encrypted) == "new_refresh"
        )
        # Database now stores timezone-aware datetimes (TIMESTAMPTZ)
        # Both token.expires_at and old_expires are timezone-aware
        assert token.expires_at > old_expires
        assert token.refresh_count == 1

    def test_token_relationship_with_connection(
        self, db_session: Session, test_user: User
    ):
        """Test that token correctly relates to connection."""
        # Create provider and connection
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Test Schwab"
        )
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.flush()

        encryption_service = EncryptionService()

        # Create token
        token = ProviderToken(
            connection_id=connection.id,
            access_token_encrypted=encryption_service.encrypt("test_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(token)
        db_session.commit()

        # Load connection with token relationship
        from sqlalchemy.orm import selectinload

        result = db_session.execute(
            select(ProviderConnection)
            .options(selectinload(ProviderConnection.token))
            .where(ProviderConnection.id == connection.id)
        )
        loaded_connection = result.scalar_one()

        # Verify relationship
        assert loaded_connection.token is not None
        assert loaded_connection.token.id == token.id
        assert loaded_connection.token.connection_id == connection.id

    def test_token_cascade_delete(self, db_session: Session, test_user: User):
        """Test that deleting a connection cascades to token."""
        # Create provider and connection
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Test Schwab"
        )
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.flush()

        encryption_service = EncryptionService()

        # Create token
        token = ProviderToken(
            connection_id=connection.id,
            access_token_encrypted=encryption_service.encrypt("test_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(token)
        db_session.commit()

        token_id = token.id
        connection_id = connection.id

        # Delete connection
        db_session.delete(connection)
        db_session.commit()

        # Verify connection is deleted
        result = db_session.execute(
            select(ProviderConnection).where(ProviderConnection.id == connection_id)
        )
        assert result.scalar_one_or_none() is None

        # Verify token is also deleted (cascade)
        result = db_session.execute(
            select(ProviderToken).where(ProviderToken.id == token_id)
        )
        assert result.scalar_one_or_none() is None

    def test_audit_log_creation_for_token_operations(
        self, db_session: Session, test_user: User
    ):
        """Test that audit logs are created for token operations."""
        # Create provider and connection
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Test Schwab"
        )
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.flush()

        # Create audit log for token creation
        audit_log = ProviderAuditLog(
            connection_id=connection.id,
            user_id=test_user.id,
            action="token_created",
            details={
                "provider_key": "schwab",
                "has_refresh_token": True,
                "expires_in": 3600,
                "status": "success",  # Store status in details
            },
        )
        db_session.add(audit_log)
        db_session.commit()

        # Query audit log
        result = db_session.execute(
            select(ProviderAuditLog)
            .where(ProviderAuditLog.connection_id == connection.id)
            .order_by(ProviderAuditLog.created_at.desc())
        )
        logs = result.scalars().all()

        # Verify audit log
        assert len(logs) == 1
        assert logs[0].action == "token_created"
        assert logs[0].user_id == test_user.id
        assert "has_refresh_token" in logs[0].details
        assert logs[0].details["status"] == "success"

    def test_encryption_consistency(self, db_session: Session, test_user: User):
        """Test that encryption and decryption are consistent."""
        # Create provider and connection
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Test Schwab"
        )
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.flush()

        encryption_service = EncryptionService()
        original_token = "my_secret_access_token_12345"

        # Encrypt and store
        encrypted = encryption_service.encrypt(original_token)
        token = ProviderToken(
            connection_id=connection.id,
            access_token_encrypted=encrypted,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(token)
        db_session.commit()
        db_session.refresh(token)

        # Retrieve and decrypt
        decrypted = encryption_service.decrypt(token.access_token_encrypted)

        # Verify consistency
        assert decrypted == original_token
        assert token.access_token_encrypted != original_token

    def test_query_tokens_by_connection(self, db_session: Session, test_user: User):
        """Test querying tokens by connection ID."""
        # Create multiple providers and connections
        providers = []
        tokens = []

        encryption_service = EncryptionService()

        for i in range(3):
            provider = Provider(
                user_id=test_user.id,
                provider_key="schwab",
                alias=f"Schwab {i}",
            )
            db_session.add(provider)
            db_session.flush()

            connection = ProviderConnection(provider_id=provider.id)
            db_session.add(connection)
            db_session.flush()

            token = ProviderToken(
                connection_id=connection.id,
                access_token_encrypted=encryption_service.encrypt(f"token_{i}"),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
            db_session.add(token)
            providers.append(provider)
            tokens.append(token)

        db_session.commit()

        # Query tokens for specific connection
        target_connection = providers[1].connection
        result = db_session.execute(
            select(ProviderToken).where(
                ProviderToken.connection_id == target_connection.id
            )
        )
        found_token = result.scalar_one()

        # Verify correct token is found
        assert found_token.id == tokens[1].id
        decrypted = encryption_service.decrypt(found_token.access_token_encrypted)
        assert decrypted == "token_1"

    def test_token_refresh_count_increments(self, db_session: Session, test_user: User):
        """Test that token refresh count increments correctly."""
        # Create provider and connection
        provider = Provider(
            user_id=test_user.id, provider_key="schwab", alias="Test Schwab"
        )
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.flush()

        encryption_service = EncryptionService()

        # Create initial token
        token = ProviderToken(
            connection_id=connection.id,
            access_token_encrypted=encryption_service.encrypt("initial_token"),
            refresh_token_encrypted=encryption_service.encrypt("refresh_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(token)
        db_session.commit()
        db_session.refresh(token)

        # Verify initial refresh count is 0
        assert token.refresh_count == 0

        # Simulate multiple refreshes
        for i in range(3):
            token.update_tokens(
                access_token_encrypted=encryption_service.encrypt(
                    f"refreshed_token_{i}"
                ),
                refresh_token_encrypted=encryption_service.encrypt(f"refresh_{i}"),
                expires_in=3600,
            )
            db_session.commit()
            db_session.refresh(token)

        # Verify refresh count incremented
        assert token.refresh_count == 3

        # Verify last token is stored
        decrypted = encryption_service.decrypt(token.access_token_encrypted)
        assert decrypted == "refreshed_token_2"
