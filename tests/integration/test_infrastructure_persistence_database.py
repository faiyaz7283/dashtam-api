"""Integration tests for database infrastructure.

Tests database connectivity and session management with real PostgreSQL:
    - Database connection
    - Session lifecycle management
    - Transaction commit/rollback behavior
    - Alembic migration verification
"""

import pytest
import pytest_asyncio
from sqlalchemy import text

from src.core.config import settings
from src.infrastructure.persistence.database import Database


@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests for database infrastructure."""

    @pytest_asyncio.fixture
    async def test_database(self):
        """Create a test database connection.

        Uses settings from environment variables (loaded from .env.test
        when running in test environment via Docker Compose).
        No hardcoded values - follows our configuration management architecture.
        """
        # Use database URL from settings - automatically uses correct environment
        db = Database(database_url=settings.database_url, echo=settings.db_echo)
        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_database_connection_works(self, test_database):
        """Test that we can connect to the real database."""
        result = await test_database.check_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_get_session_executes_query(self, test_database):
        """Test that get_session can execute a simple query."""
        async with test_database.get_session() as session:
            result = await session.execute(text("SELECT 1"))
            value = result.scalar()
            assert value == 1

    @pytest.mark.asyncio
    async def test_transaction_commits_data(self, test_database):
        """Test that transaction commits data properly."""
        # Create a test table
        async with test_database.get_session() as session:
            await session.execute(
                text("""
                CREATE TABLE IF NOT EXISTS f04_test (
                    id SERIAL PRIMARY KEY,
                    value TEXT
                )
            """)
            )

        # Insert data in transaction
        async with test_database.transaction() as session:
            await session.execute(
                text("INSERT INTO f04_test (value) VALUES (:value)"),
                {"value": "test_data"},
            )

        # Verify data was committed
        async with test_database.get_session() as session:
            result = await session.execute(
                text("SELECT value FROM f04_test WHERE value = :value"),
                {"value": "test_data"},
            )
            assert result.scalar() == "test_data"

        # Cleanup
        async with test_database.get_session() as session:
            await session.execute(text("DROP TABLE f04_test"))

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, test_database):
        """Test that transaction rolls back on error."""
        # Create a test table
        async with test_database.get_session() as session:
            await session.execute(
                text("""
                CREATE TABLE IF NOT EXISTS f04_rollback_test (
                    id SERIAL PRIMARY KEY,
                    value TEXT UNIQUE
                )
            """)
            )

        # Try to insert with error
        with pytest.raises(Exception):
            async with test_database.get_session() as session:
                await session.execute(
                    text("INSERT INTO f04_rollback_test (value) VALUES (:value)"),
                    {"value": "rollback_test"},
                )
                # Force an error
                raise Exception("Test error")

        # Verify data was NOT committed
        async with test_database.get_session() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM f04_rollback_test WHERE value = :value"),
                {"value": "rollback_test"},
            )
            assert result.scalar() == 0

        # Cleanup
        async with test_database.get_session() as session:
            await session.execute(text("DROP TABLE f04_rollback_test"))

    @pytest.mark.asyncio
    async def test_alembic_version_table_exists(self, test_database):
        """Test that Alembic migration has been applied."""
        async with test_database.get_session() as session:
            result = await session.execute(
                text("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_name = 'alembic_version'
            """)
            )
            assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_initial_migration_recorded(self, test_database):
        """Test that the initial migration is recorded."""
        async with test_database.get_session() as session:
            result = await session.execute(
                text("SELECT version_num FROM alembic_version")
            )
            version = result.scalar()
            assert version is not None
            # Verify we have a migration recorded (initial setup)
            assert version == "bb433187db3b"
