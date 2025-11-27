"""Integration tests for SecurityConfigRepository.

Tests cover:
- get_or_create_default: creates singleton config on first call
- get_or_create_default: returns existing config on subsequent calls
- update_global_version: increments version and stores reason
- update_grace_period: updates grace period setting
- Singleton enforcement (only one row with id=1)

Architecture:
- Integration tests with REAL PostgreSQL database
- Uses test_database fixture (fresh instance per test)
- Tests actual database operations, not mocked behavior
- Async tests for database operations
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text

from src.infrastructure.persistence.repositories import SecurityConfigRepository


@pytest_asyncio.fixture(autouse=True)
async def clean_security_config(test_database):
    """Clean security_config table before each test in this module.

    Ensures each test starts with an empty table for consistent behavior.
    Uses autouse=True so it runs automatically for every test.
    """
    async with test_database.get_session() as session:
        await session.execute(text("DELETE FROM security_config"))
        await session.commit()


@pytest.mark.integration
class TestSecurityConfigRepositoryGet:
    """Test get operations.

    Note: These tests run FIRST to test behavior when config doesn't exist.
    """

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_exists(self, test_database):
        """Test get returns None when config doesn't exist.

        This test MUST run before any test that creates the config.
        """
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)

            config = await repo.get()

            assert config is None


@pytest.mark.integration
class TestSecurityConfigRepositoryGetOrCreateDefault:
    """Test get_or_create_default operations."""

    @pytest.mark.asyncio
    async def test_get_or_create_default_creates_config_on_first_call(
        self, test_database
    ):
        """Test creates singleton config with default values on first call."""
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)

            config = await repo.get_or_create_default()
            await session.commit()

            assert config is not None
            assert config.id == 1
            assert config.global_min_token_version == 1
            assert config.grace_period_seconds == 300
            assert config.last_rotation_at is None
            assert config.last_rotation_reason is None

    @pytest.mark.asyncio
    async def test_get_or_create_default_returns_existing_config(self, test_database):
        """Test returns existing config on subsequent calls."""
        # First call - creates config
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            first_config = await repo.get_or_create_default()
            await session.commit()

        # Second call - returns existing
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            second_config = await repo.get_or_create_default()

            assert second_config.id == first_config.id
            assert (
                second_config.global_min_token_version
                == first_config.global_min_token_version
            )

    @pytest.mark.asyncio
    async def test_get_or_create_default_is_idempotent(self, test_database):
        """Test multiple calls don't create duplicate rows."""
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)

            # Call multiple times
            config1 = await repo.get_or_create_default()
            await session.commit()

        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            config2 = await repo.get_or_create_default()
            await session.commit()

        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            config3 = await repo.get_or_create_default()

            # All should return same config (id=1)
            assert config1.id == config2.id == config3.id == 1


@pytest.mark.integration
class TestSecurityConfigRepositoryUpdateGlobalVersion:
    """Test update_global_version operations."""

    @pytest.mark.asyncio
    async def test_update_global_version_increments_version(self, test_database):
        """Test updating global version increments the value."""
        # Setup - create default config (starts at version 1)
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            await repo.get_or_create_default()
            await session.commit()

        # Act - update version to 2
        rotation_time = datetime.now(UTC)
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            updated = await repo.update_global_version(
                new_version=2,
                reason="Security breach detected",
                rotation_time=rotation_time,
            )
            await session.commit()

            assert updated.global_min_token_version == 2
            assert updated.last_rotation_reason == "Security breach detected"
            assert updated.last_rotation_at is not None

    @pytest.mark.asyncio
    async def test_update_global_version_persists_reason(self, test_database):
        """Test rotation reason is persisted correctly."""
        # Setup - create default config
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            await repo.get_or_create_default()
            await session.commit()

        # Update to version 5 with reason
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            await repo.update_global_version(
                new_version=5,
                reason="Database compromise",
                rotation_time=datetime.now(UTC),
            )
            await session.commit()

        # Verify in new session
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            config = await repo.get_or_create_default()

            assert config.global_min_token_version == 5
            assert config.last_rotation_reason == "Database compromise"

    @pytest.mark.asyncio
    async def test_update_global_version_updates_timestamp(self, test_database):
        """Test rotation timestamp is updated."""
        # Setup - create default config
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            initial = await repo.get_or_create_default()
            initial_updated_at = initial.updated_at
            await session.commit()

        # Update to version 2
        rotation_time = datetime.now(UTC)
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            updated = await repo.update_global_version(
                new_version=2,
                reason="Test",
                rotation_time=rotation_time,
            )
            await session.commit()

            assert updated.last_rotation_at is not None
            assert updated.updated_at >= initial_updated_at


@pytest.mark.integration
class TestSecurityConfigRepositoryUpdateGracePeriod:
    """Test update_grace_period operations."""

    @pytest.mark.asyncio
    async def test_update_grace_period_changes_value(self, test_database):
        """Test updating grace period changes the value."""
        # Setup
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            await repo.get_or_create_default()
            await session.commit()

        # Update
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            updated = await repo.update_grace_period(grace_period_seconds=600)
            await session.commit()

            assert updated.grace_period_seconds == 600

    @pytest.mark.asyncio
    async def test_update_grace_period_persists(self, test_database):
        """Test grace period change persists across sessions."""
        # Setup
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            await repo.get_or_create_default()
            await session.commit()

        # Update
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            await repo.update_grace_period(grace_period_seconds=1800)
            await session.commit()

        # Verify
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            config = await repo.get_or_create_default()

            assert config.grace_period_seconds == 1800


@pytest.mark.integration
class TestSecurityConfigRepositoryGetAfterCreate:
    """Test get operations after config is created."""

    @pytest.mark.asyncio
    async def test_get_returns_config_when_exists(self, test_database):
        """Test get returns config when it exists."""
        # Setup - ensure config exists
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            await repo.get_or_create_default()
            await session.commit()

        # Get
        async with test_database.get_session() as session:
            repo = SecurityConfigRepository(session=session)
            config = await repo.get()

            assert config is not None
            assert config.id == 1
