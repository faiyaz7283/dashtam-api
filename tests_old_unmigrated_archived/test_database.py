"""Unit tests for core database functionality.

This module tests database connection management, engine creation,
session handling, and dependency injection following the Phase 1 test plan.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.core.database import (
    get_engine,
    get_session_maker,
    get_session,
    init_db,
    close_db,
)
from src.core.config import settings
from tests.test_config import test_settings


class TestEngineCreation:
    """Test database engine creation and configuration."""

    def test_get_engine_creates_async_engine(self):
        """Test that get_engine creates proper AsyncEngine."""
        engine = get_engine()

        assert engine is not None
        assert isinstance(engine, AsyncEngine)

        # Verify engine configuration
        assert "postgresql+asyncpg://" in str(engine.url)
        assert engine.url.database is not None

    def test_get_engine_uses_settings_database_url(self):
        """Test that engine uses DATABASE_URL from settings."""
        engine = get_engine()

        # Should use the database URL from settings
        assert str(engine.url).startswith("postgresql+asyncpg://")

        # In test environment, should contain test database
        if "test" in settings.DATABASE_URL:
            assert "test" in str(engine.url)

    def test_get_engine_configuration_parameters(self):
        """Test engine configuration parameters."""
        engine = get_engine()

        # Verify engine pool settings
        assert engine.pool_size > 0
        assert engine.pool_recycle == 3600  # 1 hour
        assert engine.pool_pre_ping is True

        # Echo should match DEBUG setting
        assert engine.echo == settings.DEBUG

    def test_get_engine_singleton_behavior(self):
        """Test that get_engine returns the same instance."""
        engine1 = get_engine()
        engine2 = get_engine()

        # Should return same instance (singleton pattern)
        assert engine1 is engine2

    @patch("src.core.database.create_async_engine")
    def test_get_engine_with_custom_settings(self, mock_create_engine):
        """Test engine creation with custom settings."""
        mock_engine = MagicMock(spec=AsyncEngine)
        mock_create_engine.return_value = mock_engine

        # Clear singleton to force recreation
        from src.core import database

        database._engine = None

        result = get_engine()

        # Verify create_async_engine was called with correct parameters
        mock_create_engine.assert_called_once()
        call_args = mock_create_engine.call_args

        assert call_args[0][0] == settings.DATABASE_URL  # First positional arg
        assert call_args[1]["echo"] == settings.DEBUG
        assert call_args[1]["pool_pre_ping"] is True
        assert call_args[1]["pool_recycle"] == 3600
        assert result is mock_engine


class TestSessionMakerCreation:
    """Test session maker creation and configuration."""

    def test_get_session_maker_creates_async_session_maker(self):
        """Test that get_session_maker creates proper async_sessionmaker."""
        session_maker = get_session_maker()

        assert session_maker is not None
        assert callable(session_maker)
        # Should be async_sessionmaker instance
        assert hasattr(session_maker, "class_")

    def test_get_session_maker_configuration(self):
        """Test session maker configuration."""
        session_maker = get_session_maker()

        # Test configuration by inspecting the bound engine
        assert session_maker.bind is not None
        assert isinstance(session_maker.bind, AsyncEngine)

        # Verify session class
        assert session_maker.class_ == AsyncSession

        # Verify session configuration
        assert session_maker.expire_on_commit is False
        assert session_maker.autoflush is True
        assert session_maker.autocommit is False

    def test_get_session_maker_singleton_behavior(self):
        """Test that get_session_maker returns the same instance."""
        maker1 = get_session_maker()
        maker2 = get_session_maker()

        # Should return same instance
        assert maker1 is maker2

    def test_get_session_maker_uses_same_engine(self):
        """Test that session maker uses the same engine instance."""
        engine = get_engine()
        session_maker = get_session_maker()

        assert session_maker.bind is engine


class TestSessionDependency:
    """Test session dependency injection."""

    @pytest.mark.asyncio
    async def test_get_session_yields_async_session(self):
        """Test that get_session yields AsyncSession."""
        async with get_session() as session:
            assert isinstance(session, AsyncSession)
            assert session is not None

    @pytest.mark.asyncio
    async def test_get_session_context_manager(self):
        """Test get_session as async context manager."""
        session_instances = []

        async with get_session() as session1:
            session_instances.append(session1)
            assert isinstance(session1, AsyncSession)

        async with get_session() as session2:
            session_instances.append(session2)
            assert isinstance(session2, AsyncSession)

        # Should be different session instances
        assert session_instances[0] is not session_instances[1]

    @pytest.mark.asyncio
    async def test_get_session_proper_cleanup(self):
        """Test that get_session properly cleans up sessions."""

        # Mock session to track close calls
        get_session_maker()
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_maker = AsyncMock()
        mock_session_maker.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.core.database.get_session_maker", return_value=mock_session_maker
        ):
            async with get_session() as session:
                assert session is mock_session

        # Verify session was properly closed
        mock_session_maker.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_error_handling(self):
        """Test get_session error handling and cleanup."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_maker = AsyncMock()
        mock_session_maker.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.core.database.get_session_maker", return_value=mock_session_maker
        ):
            try:
                async with get_session():
                    # Simulate error within session context
                    raise ValueError("Test error")
            except ValueError:
                pass  # Expected error

        # Verify cleanup still occurred
        mock_session_maker.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_multiple_concurrent(self):
        """Test multiple concurrent get_session calls."""
        import asyncio

        sessions = []

        async def get_test_session():
            async with get_session() as session:
                sessions.append(session)
                # Small delay to ensure concurrency
                await asyncio.sleep(0.01)
                return session

        # Run multiple concurrent sessions
        results = await asyncio.gather(*[get_test_session() for _ in range(3)])

        # All should be valid sessions but different instances
        assert len(results) == 3
        for session in results:
            assert isinstance(session, AsyncSession)

        # Should be different instances
        assert len(set(id(s) for s in results)) == 3


class TestDatabaseInitialization:
    """Test database initialization functionality."""

    @pytest.mark.asyncio
    async def test_init_database_basic_functionality(self):
        """Test basic database initialization."""
        with patch("src.core.database.SQLModel") as mock_sqlmodel:
            mock_metadata = MagicMock()
            mock_sqlmodel.metadata = mock_metadata

            with patch("src.core.database.get_engine") as mock_get_engine:
                mock_engine = AsyncMock(spec=AsyncEngine)
                mock_conn = AsyncMock()
                mock_engine.begin.return_value.__aenter__.return_value = mock_conn
                mock_get_engine.return_value = mock_engine

                await init_db()

                # Verify engine.begin was called
                mock_engine.begin.assert_called_once()

                # Verify metadata.create_all was called
                mock_conn.run_sync.assert_called_once_with(mock_metadata.create_all)

    @pytest.mark.asyncio
    async def test_init_database_error_handling(self):
        """Test init_database error handling."""
        with patch("src.core.database.get_engine") as mock_get_engine:
            mock_engine = AsyncMock(spec=AsyncEngine)
            mock_engine.begin.side_effect = Exception("Database connection failed")
            mock_get_engine.return_value = mock_engine

            # Should raise the exception
            with pytest.raises(Exception, match="Database connection failed"):
                await init_db()

    @pytest.mark.asyncio
    async def test_init_database_idempotent(self):
        """Test that init_database is idempotent (safe to run multiple times)."""
        with patch("src.core.database.SQLModel") as mock_sqlmodel:
            mock_metadata = MagicMock()
            mock_sqlmodel.metadata = mock_metadata

            with patch("src.core.database.get_engine") as mock_get_engine:
                mock_engine = AsyncMock(spec=AsyncEngine)
                mock_conn = AsyncMock()
                mock_engine.begin.return_value.__aenter__.return_value = mock_conn
                mock_get_engine.return_value = mock_engine

                # Run init_database multiple times
                await init_db()
                await init_db()
                await init_db()

                # Should not fail and metadata.create_all should be called each time
                assert mock_conn.run_sync.call_count == 3


class TestDatabaseCleanup:
    """Test database cleanup functionality."""

    @pytest.mark.asyncio
    async def test_close_database_disposes_engine(self):
        """Test that close_database properly disposes engine."""
        mock_engine = AsyncMock(spec=AsyncEngine)

        with patch("src.core.database.get_engine", return_value=mock_engine):
            await close_db()

            # Verify engine was disposed
            mock_engine.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_database_resets_singletons(self):
        """Test that close_database resets singleton instances."""
        # Get initial instances
        engine1 = get_engine()
        session_maker1 = get_session_maker()

        # Close database
        await close_db()

        # Get new instances after close
        engine2 = get_engine()
        session_maker2 = get_session_maker()

        # Should be different instances (singletons reset)
        assert engine1 is not engine2
        assert session_maker1 is not session_maker2

    @pytest.mark.asyncio
    async def test_close_database_error_handling(self):
        """Test close_database error handling."""
        mock_engine = AsyncMock(spec=AsyncEngine)
        mock_engine.dispose.side_effect = Exception("Disposal failed")

        with patch("src.core.database.get_engine", return_value=mock_engine):
            # Should not raise exception, just log it
            await close_db()

            # Verify dispose was attempted
            mock_engine.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_database_when_no_engine(self):
        """Test close_database when no engine exists."""
        # Clear any existing engine
        from src.core import database

        database._engine = None

        # Should not raise exception
        await close_db()


class TestDatabaseConnectionValidation:
    """Test database connection validation and health checks."""

    @pytest.mark.asyncio
    async def test_database_connection_check(self):
        """Test database connection health check."""
        from sqlalchemy import text

        # This is an integration-like test but using unit test patterns
        with patch("src.core.database.get_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_result.scalar.return_value = 1
            mock_session.execute.return_value = mock_result
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Test connection check
            async with get_session() as session:
                result = await session.execute(text("SELECT 1"))
                value = result.scalar()

            assert value == 1
            mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_connection_failure(self):
        """Test database connection failure handling."""
        from sqlalchemy import text

        with patch("src.core.database.get_session") as mock_get_session:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session.execute.side_effect = Exception("Connection failed")
            mock_get_session.return_value.__aenter__.return_value = mock_session

            with pytest.raises(Exception, match="Connection failed"):
                async with get_session() as session:
                    await session.execute(text("SELECT 1"))


class TestDatabaseConfigurationIntegration:
    """Test database configuration integration with settings."""

    def test_database_uses_settings_configuration(self):
        """Test that database components use settings configuration."""
        # Test that engine uses settings
        engine = get_engine()

        # Should use DATABASE_URL from settings
        assert settings.DATABASE_URL in str(engine.url)

        # Debug setting should match echo
        assert engine.echo == settings.DEBUG

    def test_database_test_environment_detection(self):
        """Test database configuration in test environment."""
        # In test environment
        if (
            hasattr(test_settings, "is_test_environment")
            and test_settings.is_test_environment
        ):
            engine = get_engine()

            # Should use test database
            assert "test" in str(engine.url)

    @patch.dict(
        "os.environ",
        {"DATABASE_URL": "postgresql+asyncpg://test:pass@localhost:5432/test_db"},
    )
    def test_database_with_environment_override(self):
        """Test database configuration with environment variable override."""
        # Clear singleton to pick up environment change
        from src.core import database

        database._engine = None

        engine = get_engine()

        # Should use environment variable
        assert "test_db" in str(engine.url)


class TestDatabasePerformanceConsiderations:
    """Test database performance-related configurations."""

    def test_connection_pool_configuration(self):
        """Test connection pool settings for performance."""
        engine = get_engine()

        # Should have reasonable pool settings
        assert engine.pool_size >= 5  # Minimum pool size
        assert engine.pool_size <= 20  # Maximum reasonable pool size
        assert engine.pool_recycle == 3600  # Connection recycling
        assert engine.pool_pre_ping is True  # Connection validation

    def test_session_configuration_for_performance(self):
        """Test session configuration for optimal performance."""
        session_maker = get_session_maker()

        # Should not expire on commit for better performance
        assert session_maker.expire_on_commit is False

        # Should use autoflush for consistency
        assert session_maker.autoflush is True


class TestDatabaseErrorScenarios:
    """Test various database error scenarios."""

    @pytest.mark.asyncio
    async def test_session_rollback_on_error(self):
        """Test that sessions properly rollback on errors."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_maker = AsyncMock()
        mock_session_maker.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.__aexit__ = AsyncMock()

        with patch(
            "src.core.database.get_session_maker", return_value=mock_session_maker
        ):
            try:
                async with get_session():
                    # Simulate database operation that fails
                    raise Exception("Database operation failed")
            except Exception:
                pass  # Expected

        # Verify session cleanup was called
        mock_session_maker.__aexit__.assert_called_once()

    def test_engine_creation_with_invalid_url(self):
        """Test engine creation with invalid database URL."""
        with patch("src.core.config.settings") as mock_settings:
            mock_settings.DATABASE_URL = "invalid://url"
            mock_settings.DEBUG = False

            # Clear singleton
            from src.core import database

            database._engine = None

            # Should raise appropriate error
            with pytest.raises(Exception):
                get_engine()

    @pytest.mark.asyncio
    async def test_concurrent_database_operations_isolation(self):
        """Test that concurrent database operations are properly isolated."""
        import asyncio

        async def database_operation(operation_id):
            async with get_session() as session:
                # Each operation should get its own session
                return id(session)

        # Run concurrent operations
        session_ids = await asyncio.gather(*[database_operation(i) for i in range(3)])

        # All should be different session instances
        assert len(set(session_ids)) == 3
