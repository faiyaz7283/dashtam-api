"""Integration tests for ProviderConnectionRepository.

Tests cover:
- Save and retrieve connection
- Find by ID
- Find by user ID
- Find by user and provider
- Find active by user
- Find expiring soon
- Delete connection
- Entity ↔ Model mapping (credentials)

Architecture:
- Integration tests with REAL PostgreSQL database
- Uses test_database fixture (fresh instance per test)
- Tests actual database operations, not mocked behavior
- Async tests for database operations
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from uuid_extensions import uuid7

from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.enums.credential_type import CredentialType
from src.domain.value_objects.provider_credentials import ProviderCredentials
from src.infrastructure.persistence.repositories.provider_connection_repository import (
    ProviderConnectionRepository,
)


# =============================================================================
# Test Helpers
# =============================================================================


def create_test_connection(
    connection_id=None,
    user_id=None,
    provider_id=None,
    provider_slug="schwab",
    status=ConnectionStatus.PENDING,
    alias=None,
    credentials=None,
    connected_at=None,
    last_sync_at=None,
):
    """Create a test ProviderConnection with all required fields.

    Note: provider_id MUST be a valid FK to providers table.
    Use schwab_provider fixture or provider_factory fixture.
    """
    now = datetime.now(UTC)
    return ProviderConnection(
        id=connection_id or uuid7(),
        user_id=user_id or uuid7(),
        provider_id=provider_id,  # Required - must be valid FK!
        provider_slug=provider_slug,
        status=status,
        alias=alias,
        credentials=credentials,
        connected_at=connected_at,
        last_sync_at=last_sync_at,
        created_at=now,
        updated_at=now,
    )


def create_test_credentials(
    encrypted_data=b"encrypted_oauth_tokens",
    credential_type=CredentialType.OAUTH2,
    expires_at=None,
):
    """Create test ProviderCredentials."""
    if expires_at is None:
        expires_at = datetime.now(UTC) + timedelta(hours=1)
    return ProviderCredentials(
        encrypted_data=encrypted_data,
        credential_type=credential_type,
        expires_at=expires_at,
    )


async def create_user_in_db(session, user_id=None, email=None):
    """Create a user in the database for FK constraint."""
    from src.infrastructure.persistence.models.user import User as UserModel

    user_id = user_id or uuid7()
    email = email or f"test_{user_id}@example.com"

    user = UserModel(
        id=user_id,
        email=email,
        password_hash="$2b$12$test_hash",
        is_verified=True,
        is_active=True,
        failed_login_attempts=0,
    )
    session.add(user)
    await session.commit()
    return user_id


# Fixtures schwab_provider and provider_factory are defined in conftest.py


@pytest_asyncio.fixture
async def provider_connection_repository(test_database):
    """Provide ProviderConnectionRepository with test database session."""
    async with test_database.get_session() as session:
        yield ProviderConnectionRepository(session=session)


# =============================================================================
# Test Classes
# =============================================================================


@pytest.mark.integration
class TestProviderConnectionRepositorySave:
    """Test ProviderConnectionRepository save operations."""

    @pytest.mark.asyncio
    async def test_save_connection_persists_to_database(
        self, test_database, schwab_provider
    ):
        """Test saving a connection persists it to the database."""
        # Arrange
        provider_id, provider_slug = schwab_provider
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        connection_id = uuid7()
        connection = create_test_connection(
            connection_id=connection_id,
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            status=ConnectionStatus.PENDING,
        )

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(connection)

        # Assert
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            found = await repo.find_by_id(connection_id)

            assert found is not None
            assert found.id == connection_id
            assert found.user_id == user_id
            assert found.provider_slug == provider_slug
            assert found.status == ConnectionStatus.PENDING

    @pytest.mark.asyncio
    async def test_save_connection_with_credentials(
        self, test_database, schwab_provider
    ):
        """Test saving a connection with credentials."""
        # Arrange
        provider_id, provider_slug = schwab_provider
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        credentials = create_test_credentials()
        connection = create_test_connection(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
            connected_at=datetime.now(UTC),
        )

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(connection)

        # Assert
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            found = await repo.find_by_id(connection.id)

            assert found is not None
            assert found.credentials is not None
            assert found.credentials.encrypted_data == credentials.encrypted_data
            assert found.credentials.credential_type == credentials.credential_type
            assert found.credentials.expires_at == credentials.expires_at

    @pytest.mark.asyncio
    async def test_save_connection_update_existing(
        self, test_database, schwab_provider
    ):
        """Test updating an existing connection."""
        # Arrange
        provider_id, provider_slug = schwab_provider
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        connection = create_test_connection(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            status=ConnectionStatus.PENDING,
            alias=None,
        )

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(connection)

        # Act - Update the connection
        credentials = create_test_credentials()
        connection.status = ConnectionStatus.ACTIVE
        connection.alias = "My Schwab Account"
        connection.credentials = credentials
        connection.connected_at = datetime.now(UTC)
        connection.updated_at = datetime.now(UTC)

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(connection)

        # Assert
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            found = await repo.find_by_id(connection.id)

            assert found is not None
            assert found.status == ConnectionStatus.ACTIVE
            assert found.alias == "My Schwab Account"
            assert found.credentials is not None
            assert found.connected_at is not None


@pytest.mark.integration
class TestProviderConnectionRepositoryFindById:
    """Test ProviderConnectionRepository find_by_id operations."""

    @pytest.mark.asyncio
    async def test_find_by_id_returns_connection(self, test_database, schwab_provider):
        """Test find_by_id returns existing connection."""
        # Arrange
        provider_id, provider_slug = schwab_provider
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        connection = create_test_connection(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
        )

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(connection)

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            found = await repo.find_by_id(connection.id)

        # Assert
        assert found is not None
        assert found.id == connection.id

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none_when_not_found(self, test_database):
        """Test find_by_id returns None for non-existent ID."""
        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            found = await repo.find_by_id(uuid7())

        # Assert
        assert found is None


@pytest.mark.integration
class TestProviderConnectionRepositoryFindByUserId:
    """Test ProviderConnectionRepository find_by_user_id operations."""

    @pytest.mark.asyncio
    async def test_find_by_user_id_returns_all_connections(
        self, test_database, provider_factory
    ):
        """Test find_by_user_id returns all user connections."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        # Create two different providers
        provider1_id, slug1 = await provider_factory("schwab")
        provider2_id, slug2 = await provider_factory("fidelity")

        conn1 = create_test_connection(
            user_id=user_id,
            provider_id=provider1_id,
            provider_slug=slug1,
        )
        conn2 = create_test_connection(
            user_id=user_id,
            provider_id=provider2_id,
            provider_slug=slug2,
        )

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(conn1)
            await repo.save(conn2)

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            connections = await repo.find_by_user_id(user_id)

        # Assert
        assert len(connections) == 2
        slugs = {c.provider_slug for c in connections}
        assert slugs == {slug1, slug2}

    @pytest.mark.asyncio
    async def test_find_by_user_id_returns_empty_list_when_none(self, test_database):
        """Test find_by_user_id returns empty list for user with no connections."""
        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            connections = await repo.find_by_user_id(uuid7())

        # Assert
        assert connections == []

    @pytest.mark.asyncio
    async def test_find_by_user_id_includes_all_statuses(
        self, test_database, provider_factory
    ):
        """Test find_by_user_id returns connections in all statuses."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        statuses = [
            ConnectionStatus.PENDING,
            ConnectionStatus.ACTIVE,
            ConnectionStatus.DISCONNECTED,
        ]
        connections = []
        for i, status in enumerate(statuses):
            # Create a unique provider for each connection
            provider_id, provider_slug = await provider_factory(f"provider_{i}")
            # ACTIVE status requires credentials at creation time (domain validation)
            credentials = (
                create_test_credentials() if status == ConnectionStatus.ACTIVE else None
            )
            conn = create_test_connection(
                user_id=user_id,
                provider_id=provider_id,
                provider_slug=provider_slug,
                status=status,
                credentials=credentials,
            )
            connections.append(conn)

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            for conn in connections:
                await repo.save(conn)

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            found = await repo.find_by_user_id(user_id)

        # Assert
        assert len(found) == 3
        found_statuses = {c.status for c in found}
        assert found_statuses == set(statuses)


@pytest.mark.integration
class TestProviderConnectionRepositoryFindByUserAndProvider:
    """Test ProviderConnectionRepository find_by_user_and_provider operations."""

    @pytest.mark.asyncio
    async def test_find_by_user_and_provider_returns_matching(
        self, test_database, provider_factory
    ):
        """Test find_by_user_and_provider returns matching connections."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        provider_id, provider_slug = await provider_factory("schwab")
        other_provider_id, other_slug = await provider_factory("fidelity")

        conn1 = create_test_connection(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
        )
        conn2 = create_test_connection(
            user_id=user_id,
            provider_id=other_provider_id,
            provider_slug=other_slug,
        )

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(conn1)
            await repo.save(conn2)

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            connections = await repo.find_by_user_and_provider(user_id, provider_id)

        # Assert
        assert len(connections) == 1
        assert connections[0].provider_id == provider_id

    @pytest.mark.asyncio
    async def test_find_by_user_and_provider_multiple_connections(
        self, test_database, schwab_provider
    ):
        """Test user can have multiple connections to same provider."""
        # Arrange
        provider_id, provider_slug = schwab_provider
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        conn1 = create_test_connection(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            alias="Personal Account",
        )
        conn2 = create_test_connection(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            alias="IRA Account",
        )

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(conn1)
            await repo.save(conn2)

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            connections = await repo.find_by_user_and_provider(user_id, provider_id)

        # Assert
        assert len(connections) == 2
        aliases = {c.alias for c in connections}
        assert aliases == {"Personal Account", "IRA Account"}


@pytest.mark.integration
class TestProviderConnectionRepositoryFindActiveByUser:
    """Test ProviderConnectionRepository find_active_by_user operations."""

    @pytest.mark.asyncio
    async def test_find_active_by_user_returns_only_active(
        self, test_database, provider_factory
    ):
        """Test find_active_by_user returns only active connections."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        # Create providers for each connection
        pending_pid, pending_slug = await provider_factory("pending")
        active_pid, active_slug = await provider_factory("active")
        expired_pid, expired_slug = await provider_factory("expired")

        # Create connections with different statuses
        pending = create_test_connection(
            user_id=user_id,
            provider_id=pending_pid,
            provider_slug=pending_slug,
            status=ConnectionStatus.PENDING,
        )
        active = create_test_connection(
            user_id=user_id,
            provider_id=active_pid,
            provider_slug=active_slug,
            status=ConnectionStatus.ACTIVE,
            credentials=create_test_credentials(),
        )
        expired = create_test_connection(
            user_id=user_id,
            provider_id=expired_pid,
            provider_slug=expired_slug,
            status=ConnectionStatus.EXPIRED,
            credentials=create_test_credentials(),
        )

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(pending)
            await repo.save(active)
            await repo.save(expired)

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            connections = await repo.find_active_by_user(user_id)

        # Assert
        assert len(connections) == 1
        assert connections[0].status == ConnectionStatus.ACTIVE
        assert connections[0].provider_slug == active_slug

    @pytest.mark.asyncio
    async def test_find_active_by_user_returns_empty_when_no_active(
        self, test_database, schwab_provider
    ):
        """Test find_active_by_user returns empty when no active connections."""
        # Arrange
        provider_id, provider_slug = schwab_provider
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        pending = create_test_connection(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            status=ConnectionStatus.PENDING,
        )

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(pending)

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            connections = await repo.find_active_by_user(user_id)

        # Assert
        assert connections == []


@pytest.mark.integration
class TestProviderConnectionRepositoryFindExpiringSoon:
    """Test ProviderConnectionRepository find_expiring_soon operations."""

    @pytest.mark.asyncio
    async def test_find_expiring_soon_returns_expiring(
        self, test_database, provider_factory
    ):
        """Test find_expiring_soon returns connections about to expire."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        # Create providers for connections
        expiring_pid, expiring_slug = await provider_factory("expiring")
        not_exp_pid, not_expiring_slug = await provider_factory("not_exp")

        # Connection expiring in 15 minutes (within 30 min threshold)
        expiring_soon = create_test_connection(
            user_id=user_id,
            provider_id=expiring_pid,
            provider_slug=expiring_slug,
            status=ConnectionStatus.ACTIVE,
            credentials=create_test_credentials(
                expires_at=datetime.now(UTC) + timedelta(minutes=15),
            ),
        )

        # Connection expiring in 2 hours (outside threshold)
        not_expiring = create_test_connection(
            user_id=user_id,
            provider_id=not_exp_pid,
            provider_slug=not_expiring_slug,
            status=ConnectionStatus.ACTIVE,
            credentials=create_test_credentials(
                expires_at=datetime.now(UTC) + timedelta(hours=2),
            ),
        )

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(expiring_soon)
            await repo.save(not_expiring)

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            all_connections = await repo.find_expiring_soon(minutes=30)
            # Filter to only our test connections
            our_connections = [
                c
                for c in all_connections
                if c.provider_slug in (expiring_slug, not_expiring_slug)
            ]

        # Assert - only the expiring one should be in results
        assert len(our_connections) == 1
        assert our_connections[0].provider_slug == expiring_slug

    @pytest.mark.asyncio
    async def test_find_expiring_soon_excludes_non_active(
        self, test_database, provider_factory
    ):
        """Test find_expiring_soon excludes non-active connections."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        # Create provider for connection
        provider_id, unique_slug = await provider_factory("expired")
        expired = create_test_connection(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=unique_slug,
            status=ConnectionStatus.EXPIRED,
            credentials=create_test_credentials(
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            ),
        )

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(expired)

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            connections = await repo.find_expiring_soon(minutes=30)

        # Assert - our EXPIRED connection should NOT be in the results
        # (Note: there may be ACTIVE connections from other tests)
        our_connection = [c for c in connections if c.provider_slug == unique_slug]
        assert our_connection == []

    @pytest.mark.asyncio
    async def test_find_expiring_soon_custom_threshold(
        self, test_database, provider_factory
    ):
        """Test find_expiring_soon with custom threshold."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        # Create provider for connection
        provider_id, unique_slug = await provider_factory("thresh")
        connection = create_test_connection(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=unique_slug,
            status=ConnectionStatus.ACTIVE,
            credentials=create_test_credentials(
                expires_at=datetime.now(UTC) + timedelta(minutes=45),
            ),
        )

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(connection)

        # Act - 30 min threshold (should NOT find our connection)
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            all_30min = await repo.find_expiring_soon(minutes=30)
            our_30min = [c for c in all_30min if c.provider_slug == unique_slug]

        # Act - 60 min threshold (should find our connection)
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            all_60min = await repo.find_expiring_soon(minutes=60)
            our_60min = [c for c in all_60min if c.provider_slug == unique_slug]

        # Assert - our specific connection behavior
        assert our_30min == []  # 45 min expiry not in 30 min threshold
        assert len(our_60min) == 1  # 45 min expiry IS in 60 min threshold
        assert our_60min[0].provider_slug == unique_slug


@pytest.mark.integration
class TestProviderConnectionRepositoryDelete:
    """Test ProviderConnectionRepository delete operations."""

    @pytest.mark.asyncio
    async def test_delete_removes_connection(self, test_database, schwab_provider):
        """Test delete removes connection from database."""
        # Arrange
        provider_id, provider_slug = schwab_provider
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        connection = create_test_connection(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
        )

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(connection)

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.delete(connection.id)

        # Assert
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            found = await repo.find_by_id(connection.id)
            assert found is None

    @pytest.mark.asyncio
    async def test_delete_raises_when_not_found(self, test_database):
        """Test delete raises NoResultFound for non-existent connection."""
        from sqlalchemy.exc import NoResultFound

        # Act & Assert
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            with pytest.raises(NoResultFound):
                await repo.delete(uuid7())


@pytest.mark.integration
class TestProviderConnectionRepositoryCredentialMapping:
    """Test credential mapping between domain and model."""

    @pytest.mark.asyncio
    async def test_credentials_roundtrip(self, test_database, schwab_provider):
        """Test credentials survive save/load roundtrip."""
        # Arrange
        provider_id, provider_slug = schwab_provider
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        original_data = b"sensitive_oauth_tokens_here"
        original_expires = datetime.now(UTC) + timedelta(hours=1)
        credentials = ProviderCredentials(
            encrypted_data=original_data,
            credential_type=CredentialType.OAUTH2,
            expires_at=original_expires,
        )

        connection = create_test_connection(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            status=ConnectionStatus.ACTIVE,
            credentials=credentials,
        )

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(connection)

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            loaded = await repo.find_by_id(connection.id)

        # Assert
        assert loaded is not None
        assert loaded.credentials is not None
        assert loaded.credentials.encrypted_data == original_data
        assert loaded.credentials.credential_type == CredentialType.OAUTH2
        # Compare with microsecond precision (database may truncate)
        assert loaded.credentials.expires_at is not None
        assert loaded.credentials.expires_at.replace(
            microsecond=0
        ) == original_expires.replace(microsecond=0)

    @pytest.mark.asyncio
    async def test_null_credentials_handled(self, test_database, schwab_provider):
        """Test connection without credentials handled correctly."""
        # Arrange
        provider_id, provider_slug = schwab_provider
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        connection = create_test_connection(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            status=ConnectionStatus.PENDING,
            credentials=None,
        )

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(connection)

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            loaded = await repo.find_by_id(connection.id)

        # Assert
        assert loaded is not None
        assert loaded.credentials is None

    @pytest.mark.asyncio
    async def test_credentials_cleared_on_update(self, test_database, schwab_provider):
        """Test credentials can be cleared on update."""
        # Arrange
        provider_id, provider_slug = schwab_provider
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        connection = create_test_connection(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            status=ConnectionStatus.ACTIVE,
            credentials=create_test_credentials(),
        )

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(connection)

        # Act - Clear credentials
        connection.credentials = None
        connection.status = ConnectionStatus.DISCONNECTED
        connection.updated_at = datetime.now(UTC)

        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            await repo.save(connection)

        # Assert
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            loaded = await repo.find_by_id(connection.id)
            assert loaded is not None
            assert loaded.credentials is None
            assert loaded.status == ConnectionStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_all_credential_types_supported(
        self, test_database, provider_factory
    ):
        """Test all CredentialType enum values work correctly."""
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)

        for cred_type in CredentialType:
            # Create a unique provider for each credential type
            provider_id, provider_slug = await provider_factory(
                f"cred_{cred_type.value}"
            )
            connection = create_test_connection(
                user_id=user_id,
                provider_id=provider_id,
                provider_slug=provider_slug,
                status=ConnectionStatus.ACTIVE,
                credentials=ProviderCredentials(
                    encrypted_data=f"data_for_{cred_type.value}".encode(),
                    credential_type=cred_type,
                    expires_at=datetime.now(UTC) + timedelta(hours=1)
                    if cred_type in CredentialType.supports_refresh()
                    else None,
                ),
            )

            async with test_database.get_session() as session:
                repo = ProviderConnectionRepository(session=session)
                await repo.save(connection)

            async with test_database.get_session() as session:
                repo = ProviderConnectionRepository(session=session)
                loaded = await repo.find_by_id(connection.id)
                assert loaded is not None
                assert loaded.credentials is not None
                assert loaded.credentials.credential_type == cred_type
