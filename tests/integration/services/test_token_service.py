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
    """Integration tests for token storage with real database and encryption.

    Tests OAuth token CRUD operations with real PostgreSQL database,
    encryption service, and database relationships. Uses synchronous
    SQLModel sessions for test isolation.
    """

    def test_create_and_encrypt_token(self, db_session: Session, test_user: User):
        """Test end-to-end token creation with AES-256 encryption.

        Verifies that:
        - Provider, connection, and token created in database
        - Access and refresh tokens encrypted before storage
        - Encrypted values stored correctly (not plaintext)
        - Decryption returns original token values
        - Timezone-aware expiry timestamp stored

        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture

        Note:
            Integration test: real database + real encryption service.
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
        assert abs((token.expires_at - expires_at).total_seconds()) < 1

        # Verify decryption works
        decrypted_access = encryption_service.decrypt(token.access_token_encrypted)
        decrypted_refresh = encryption_service.decrypt(token.refresh_token_encrypted)
        assert decrypted_access == "test_access_token_123"
        assert decrypted_refresh == "test_refresh_token_456"

    def test_token_without_refresh_token(self, db_session: Session, test_user: User):
        """Test token storage when provider doesn't issue refresh token.

        Verifies that:
        - Token stored with only access token
        - refresh_token_encrypted field is None
        - No errors for missing refresh token
        - Expiry timestamp stored correctly

        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture

        Note:
            Some OAuth providers only issue access tokens.
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
        assert abs((token.expires_at - expires_at).total_seconds()) < 1

    def test_token_expiry_detection(self, db_session: Session, test_user: User):
        """Test token expiry detection with timezone-aware datetimes (TIMESTAMPTZ).

        Verifies that:
        - Expired token (past datetime) detected correctly
        - needs_refresh property returns True
        - is_expired property returns True
        - Timezone-aware comparison works (UTC)
        - Database TIMESTAMPTZ compliance validated

        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture

        Note:
            P0 requirement: timezone-aware datetimes for PCI-DSS compliance.
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
        """Test token update via update_tokens() method (rotation).

        Verifies that:
        - update_tokens() method updates encrypted tokens
        - New access and refresh tokens stored
        - expires_at updated based on expires_in
        - refresh_count incremented
        - Old tokens replaced with new encrypted values

        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture

        Note:
            Simulates OAuth token refresh/rotation flow.
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
        """Test SQLModel relationship between ProviderConnection and ProviderToken.

        Verifies that:
        - One-to-one relationship loaded correctly
        - selectinload() eager loading works
        - connection.token relationship populated
        - Foreign key relationship intact

        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture

        Note:
            Tests database relationship integrity.
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
        """Test cascade delete from ProviderConnection to ProviderToken.

        Verifies that:
        - Deleting connection also deletes token (CASCADE)
        - Foreign key constraint enforced
        - No orphaned tokens remain
        - Database referential integrity maintained

        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture

        Note:
            Critical: prevents orphaned tokens in database.
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
        """Test ProviderAuditLog creation for token operations (compliance).

        Verifies that:
        - Audit log entry created for token operations
        - action field set correctly ("token_created")
        - user_id captured for accountability
        - details JSONB field stores metadata
        - Audit trail for security/compliance

        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture

        Note:
            Required for PCI-DSS and SOC 2 compliance.
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
        """Test encryption/decryption consistency (AES-256 Fernet).

        Verifies that:
        - Encrypt → store → retrieve → decrypt returns original value
        - Encrypted value != plaintext (encryption working)
        - Decrypted value == original plaintext (decryption working)
        - No data corruption in roundtrip

        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture

        Note:
            Critical security test: encryption must be reversible.
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
        """Test querying tokens by connection_id (database indexing).

        Verifies that:
        - Multiple tokens created for different connections
        - Query by connection_id returns correct token
        - No cross-contamination between connections
        - Database index on connection_id working

        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture

        Note:
            Tests database query performance and correctness.
        """
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
        """Test refresh_count field increments on token updates.

        Verifies that:
        - refresh_count starts at 0
        - update_tokens() increments refresh_count
        - Multiple updates increment sequentially (0 → 1 → 2)
        - Audit trail for token refresh operations

        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture

        Note:
            Tracking metric for token refresh operations.
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
