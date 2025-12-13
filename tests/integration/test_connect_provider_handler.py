"""Integration tests for ConnectProviderHandler.

Tests cover:
- Successful connection persists to database
- Connection entity has correct FK to provider (via provider_id)
- Credentials are correctly stored
- Connection status is ACTIVE
- Error cases return Failure without database writes

Architecture:
- Integration tests with REAL PostgreSQL database
- Uses test_database fixture (fresh instance per test)
- Tests actual database operations, not mocked behavior
- Async tests for database operations
"""

from datetime import UTC, datetime, timedelta

import pytest
from uuid_extensions import uuid7

from src.application.commands.handlers.connect_provider_handler import (
    ConnectProviderHandler,
    ConnectProviderError,
)
from src.application.commands.provider_commands import ConnectProvider
from src.core.result import Failure, Success
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.enums.credential_type import CredentialType
from src.domain.value_objects.provider_credentials import ProviderCredentials
from src.infrastructure.persistence.repositories.provider_connection_repository import (
    ProviderConnectionRepository,
)


# =============================================================================
# Test Helpers
# =============================================================================


def create_test_credentials(
    encrypted_data: bytes = b"encrypted_oauth_tokens",
    credential_type: CredentialType = CredentialType.OAUTH2,
    expires_at: datetime | None = None,
) -> ProviderCredentials:
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


async def create_provider_in_db(session, provider_id=None, slug=None):
    """Create a provider in the database for FK constraint.

    Args:
        session: Database session.
        provider_id: Optional provider UUID.
        slug: Optional slug (defaults to unique test slug).

    Returns:
        tuple[UUID, str]: Provider ID and slug.
    """
    from src.infrastructure.persistence.models.provider import Provider as ProviderModel
    import uuid

    provider_id = provider_id or uuid7()
    # Use fully random UUID suffix to ensure uniqueness across tests
    slug = slug or f"test_{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC)

    provider = ProviderModel(
        id=provider_id,
        slug=slug,
        name=f"Test Provider {slug}",
        credential_type=CredentialType.OAUTH2.value,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(provider)
    await session.commit()
    return provider_id, slug


class StubEventBus:
    """Stub event bus that records published events for verification."""

    def __init__(self):
        self.events = []

    async def publish(self, event):
        self.events.append(event)


# =============================================================================
# Test Classes
# =============================================================================


@pytest.mark.integration
class TestConnectProviderHandlerSuccess:
    """Test ConnectProviderHandler successful connection scenarios."""

    @pytest.mark.asyncio
    async def test_handle_creates_connection_in_database(self, test_database):
        """Test that successful handle() persists connection to database."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            provider_id, provider_slug = await create_provider_in_db(session)

        credentials = create_test_credentials()
        event_bus = StubEventBus()

        cmd = ConnectProvider(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            credentials=credentials,
            alias="My Test Account",
        )

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            handler = ConnectProviderHandler(
                connection_repo=repo,
                event_bus=event_bus,
            )
            result = await handler.handle(cmd)

        # Assert - result is success
        assert isinstance(result, Success)
        connection_id = result.value

        # Assert - connection exists in database
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            found = await repo.find_by_id(connection_id)

            assert found is not None
            assert found.id == connection_id
            assert found.user_id == user_id
            assert found.provider_id == provider_id
            assert found.provider_slug == provider_slug
            assert found.alias == "My Test Account"
            assert found.status == ConnectionStatus.ACTIVE
            assert found.connected_at is not None

    @pytest.mark.asyncio
    async def test_handle_stores_credentials(self, test_database):
        """Test that credentials are correctly stored in database."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            provider_id, provider_slug = await create_provider_in_db(session)

        encrypted_data = b"AES256_encrypted_oauth_tokens_here"
        expires_at = datetime.now(UTC) + timedelta(minutes=30)
        credentials = ProviderCredentials(
            encrypted_data=encrypted_data,
            credential_type=CredentialType.OAUTH2,
            expires_at=expires_at,
        )
        event_bus = StubEventBus()

        cmd = ConnectProvider(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            credentials=credentials,
        )

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            handler = ConnectProviderHandler(connection_repo=repo, event_bus=event_bus)
            result = await handler.handle(cmd)

        # Assert
        assert isinstance(result, Success)
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            found = await repo.find_by_id(result.value)

            assert found.credentials is not None
            assert found.credentials.encrypted_data == encrypted_data
            assert found.credentials.credential_type == CredentialType.OAUTH2
            # Compare without microseconds (DB may truncate)
            assert found.credentials.expires_at.replace(
                microsecond=0
            ) == expires_at.replace(microsecond=0)

    @pytest.mark.asyncio
    async def test_handle_emits_events(self, test_database):
        """Test that handler emits correct domain events."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            provider_id, provider_slug = await create_provider_in_db(session)

        credentials = create_test_credentials()
        event_bus = StubEventBus()

        cmd = ConnectProvider(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            credentials=credentials,
        )

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            handler = ConnectProviderHandler(connection_repo=repo, event_bus=event_bus)
            await handler.handle(cmd)

        # Assert - check events
        assert len(event_bus.events) == 2

        # First event: Attempted
        from src.domain.events.provider_events import (
            ProviderConnectionAttempted,
            ProviderConnectionSucceeded,
        )

        assert isinstance(event_bus.events[0], ProviderConnectionAttempted)
        assert event_bus.events[0].user_id == user_id
        assert event_bus.events[0].provider_slug == provider_slug

        # Second event: Succeeded
        assert isinstance(event_bus.events[1], ProviderConnectionSucceeded)
        assert event_bus.events[1].user_id == user_id


@pytest.mark.integration
class TestConnectProviderHandlerValidation:
    """Test ConnectProviderHandler validation and error scenarios."""

    @pytest.mark.asyncio
    async def test_handle_missing_credentials_returns_failure(self, test_database):
        """Test that missing credentials returns Failure without DB write."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            provider_id, provider_slug = await create_provider_in_db(session)

        event_bus = StubEventBus()

        cmd = ConnectProvider(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            credentials=None,  # Missing credentials
        )

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            handler = ConnectProviderHandler(connection_repo=repo, event_bus=event_bus)
            result = await handler.handle(cmd)

        # Assert - returns Failure
        assert isinstance(result, Failure)
        assert result.error == ConnectProviderError.INVALID_CREDENTIALS

        # Assert - no connection created
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            connections = await repo.find_by_user_id(user_id)
            assert len(connections) == 0

        # Assert - emits ATTEMPTED and FAILED events
        from src.domain.events.provider_events import (
            ProviderConnectionAttempted,
            ProviderConnectionFailed,
        )

        assert len(event_bus.events) == 2
        assert isinstance(event_bus.events[0], ProviderConnectionAttempted)
        assert isinstance(event_bus.events[1], ProviderConnectionFailed)

    @pytest.mark.asyncio
    async def test_handle_invalid_provider_slug_returns_failure(self, test_database):
        """Test that invalid provider_slug returns Failure."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            provider_id, _ = await create_provider_in_db(session)

        credentials = create_test_credentials()
        event_bus = StubEventBus()

        cmd = ConnectProvider(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug="",  # Empty slug
            credentials=credentials,
        )

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            handler = ConnectProviderHandler(connection_repo=repo, event_bus=event_bus)
            result = await handler.handle(cmd)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ConnectProviderError.INVALID_PROVIDER_SLUG

    @pytest.mark.asyncio
    async def test_handle_slug_too_long_returns_failure(self, test_database):
        """Test that provider_slug > 50 chars returns Failure."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            provider_id, _ = await create_provider_in_db(session)

        credentials = create_test_credentials()
        event_bus = StubEventBus()

        cmd = ConnectProvider(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug="x" * 51,  # Too long
            credentials=credentials,
        )

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            handler = ConnectProviderHandler(connection_repo=repo, event_bus=event_bus)
            result = await handler.handle(cmd)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ConnectProviderError.INVALID_PROVIDER_SLUG


@pytest.mark.integration
class TestConnectProviderHandlerForeignKeys:
    """Test FK constraints in ConnectProviderHandler."""

    @pytest.mark.asyncio
    async def test_handle_with_valid_provider_fk(self, test_database):
        """Test that connection correctly references provider via FK."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            provider_id, provider_slug = await create_provider_in_db(session)

        credentials = create_test_credentials()
        event_bus = StubEventBus()

        cmd = ConnectProvider(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug=provider_slug,
            credentials=credentials,
        )

        # Act
        async with test_database.get_session() as session:
            repo = ProviderConnectionRepository(session=session)
            handler = ConnectProviderHandler(connection_repo=repo, event_bus=event_bus)
            result = await handler.handle(cmd)

        # Assert
        assert isinstance(result, Success)

        # Verify FK relationship via raw SQL
        async with test_database.get_session() as session:
            from sqlalchemy import text

            query = text("""
                SELECT pc.provider_id, p.slug
                FROM provider_connections pc
                JOIN providers p ON pc.provider_id = p.id
                WHERE pc.id = :connection_id
            """)
            row = (
                await session.execute(query, {"connection_id": result.value})
            ).first()
            assert row is not None
            assert row.provider_id == provider_id
            assert row.slug == provider_slug

    @pytest.mark.asyncio
    async def test_handle_invalid_provider_id_raises_error(self, test_database):
        """Test that invalid provider_id causes database error."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            # Don't create provider - leave provider_id as non-existent FK

        credentials = create_test_credentials()
        event_bus = StubEventBus()
        fake_provider_id = uuid7()  # Non-existent provider

        cmd = ConnectProvider(
            user_id=user_id,
            provider_id=fake_provider_id,
            provider_slug="nonexistent",
            credentials=credentials,
        )

        # Act - Note: repo.save() does its own commit, which fails with FK violation.
        # The handler catches this and returns Failure. We create the session
        # but DON'T use the context manager's auto-commit since repo handles it.
        from src.infrastructure.persistence.database import Database
        from src.core.config import settings

        db = Database(database_url=settings.database_url, echo=settings.db_echo)
        try:
            session = db.async_session()
            try:
                repo = ProviderConnectionRepository(session=session)
                handler = ConnectProviderHandler(
                    connection_repo=repo, event_bus=event_bus
                )
                result = await handler.handle(cmd)
            finally:
                await session.close()
        finally:
            await db.close()

        # Assert - should fail with database error (FK violation)
        assert isinstance(result, Failure)
        assert "Database error" in result.error

        # Verify FAILED event emitted
        from src.domain.events.provider_events import ProviderConnectionFailed

        failed_events = [
            e for e in event_bus.events if isinstance(e, ProviderConnectionFailed)
        ]
        assert len(failed_events) == 1
