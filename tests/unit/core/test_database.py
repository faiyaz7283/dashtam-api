"""Unit tests for database connection and session management.

This module tests the core database functionality including:
- Engine creation and lifecycle
- Session maker configuration
- Dependency injection
- Connection health checks
- Context managers
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.core import database
from src.core.config import settings


class TestGetEngine:
    """Tests for get_engine() function.

    Tests singleton pattern for AsyncEngine creation and configuration.
    """

    def setup_method(self):
        """Reset global engine before each test."""
        database._engine = None
        database._async_session_maker = None

    def test_get_engine_creates_new_engine(self):
        """Test get_engine creates new AsyncEngine on first call.

        Verifies that:
        - New AsyncEngine instance created
        - Engine stored in module-level singleton
        - Engine is AsyncEngine type
        """
        engine = database.get_engine()

        assert engine is not None
        assert isinstance(engine, AsyncEngine)
        assert database._engine is engine

    def test_get_engine_returns_existing_engine(self):
        """Test get_engine returns same engine instance (singleton pattern).

        Verifies that:
        - Second call returns same instance
        - No duplicate engines created
        - Singleton pattern working correctly
        """
        engine1 = database.get_engine()
        engine2 = database.get_engine()

        assert engine1 is engine2

    def test_get_engine_raises_if_no_database_url(self):
        """Test get_engine raises RuntimeError for missing DATABASE_URL.

        Verifies that:
        - RuntimeError raised if DATABASE_URL not configured
        - Error message mentions "DATABASE_URL is not configured"
        - Prevents engine creation without database URL

        Raises:
            RuntimeError: Expected error for missing config
        """
        database._engine = None

        with patch.object(settings, "DATABASE_URL", None):
            with pytest.raises(RuntimeError, match="DATABASE_URL is not configured"):
                database.get_engine()

    def test_get_engine_configuration(self):
        """Test engine created with proper PostgreSQL configuration.

        Verifies that:
        - Engine has connection pool configured
        - Engine URL is set
        - Engine attributes exist and configured
        """
        database._engine = None
        engine = database.get_engine()

        # Check that engine is configured (these attributes exist)
        assert engine.pool is not None
        assert engine.url is not None

    def teardown_method(self):
        """Clean up after each test."""
        database._engine = None
        database._async_session_maker = None


class TestGetSessionMaker:
    """Tests for get_session_maker() function.

    Tests singleton pattern for async_sessionmaker creation.
    """

    def setup_method(self):
        """Reset global session maker before each test."""
        database._engine = None
        database._async_session_maker = None

    def test_get_session_maker_creates_new_maker(self):
        """Test get_session_maker creates new async_sessionmaker on first call.

        Verifies that:
        - New async_sessionmaker instance created
        - Session maker stored in module-level singleton
        - Session maker is not None
        """
        session_maker = database.get_session_maker()

        assert session_maker is not None
        assert database._async_session_maker is session_maker

    def test_get_session_maker_returns_existing_maker(self):
        """Test get_session_maker returns same instance (singleton pattern).

        Verifies that:
        - Second call returns same instance
        - No duplicate session makers created
        - Singleton pattern working correctly
        """
        maker1 = database.get_session_maker()
        maker2 = database.get_session_maker()

        assert maker1 is maker2

    def test_get_session_maker_uses_existing_engine(self):
        """Test session maker uses existing engine instance.

        Verifies that:
        - Session maker uses already-created engine
        - Engine singleton shared across session maker
        - No duplicate engine creation
        """
        engine = database.get_engine()
        session_maker = database.get_session_maker()

        assert database._engine is engine
        assert session_maker is not None

    def teardown_method(self):
        """Clean up after each test."""
        database._engine = None
        database._async_session_maker = None


@pytest.mark.asyncio
class TestGetSession:
    """Tests for get_session() dependency injection function.

    Tests FastAPI dependency for database session management.
    Validates async generator pattern with proper cleanup.
    """

    def setup_method(self):
        """Reset global state before each test."""
        database._engine = None
        database._async_session_maker = None

    async def test_get_session_yields_session(self):
        """Test get_session yields valid AsyncSession for FastAPI endpoints.

        Verifies that:
        - Async generator yields AsyncSession
        - Session is valid AsyncSession instance
        - Can be used for database operations

        Note:
            Used as FastAPI Depends() dependency.
        """
        session_gen = database.get_session()
        session = await session_gen.__anext__()

        assert session is not None
        assert isinstance(session, AsyncSession)

        # Clean up
        try:
            await session_gen.__anext__()
        except StopAsyncIteration:
            pass

    async def test_get_session_closes_session_on_exit(self):
        """Test get_session closes session after request completes.

        Verifies that:
        - Session close() method called on exit
        - Cleanup happens automatically
        - No connection leaks
        - Close called at least once (may be twice due to context manager)

        Note:
            Critical for connection pool management.
        """
        session_gen = database.get_session()
        session = await session_gen.__anext__()

        # Mock the close method to verify it's called
        original_close = session.close
        session.close = AsyncMock(wraps=original_close)

        # Exit the generator
        try:
            await session_gen.__anext__()
        except StopAsyncIteration:
            pass

        # Verify close was called (may be called twice due to context manager)
        assert session.close.called
        assert session.close.call_count >= 1

    def teardown_method(self):
        """Clean up after each test."""
        database._engine = None
        database._async_session_maker = None


@pytest.mark.asyncio
class TestInitDb:
    """Tests for init_db() function.

    Tests database table creation during application startup.
    """

    async def test_init_db_creates_tables(self, capsys):
        """Test init_db creates database tables and prints success message.

        Verifies that:
        - Database tables created successfully
        - Success message printed to stdout
        - No errors during table creation

        Args:
            capsys: Pytest fixture to capture stdout/stderr

        Note:
            Called during application startup (main.py).
        """
        # Reset engine to ensure clean state
        database._engine = None

        await database.init_db()

        captured = capsys.readouterr()
        assert "✅ Database tables created successfully" in captured.out


@pytest.mark.asyncio
class TestCloseDb:
    """Tests for close_db() function.

    Tests database connection cleanup during application shutdown.
    """

    async def test_close_db_disposes_engine(self, capsys):
        """Test close_db disposes engine and clears singletons.

        Verifies that:
        - Engine disposed properly
        - Module-level _engine set to None
        - Module-level _async_session_maker set to None
        - Success message printed to stdout

        Args:
            capsys: Pytest fixture to capture stdout/stderr

        Note:
            Called during application shutdown (lifespan event).
        """
        # Create an engine first
        database.get_engine()
        assert database._engine is not None

        await database.close_db()

        assert database._engine is None
        assert database._async_session_maker is None

        captured = capsys.readouterr()
        assert "✅ Database connections closed" in captured.out

    async def test_close_db_handles_no_engine(self, capsys):
        """Test close_db handles case when no engine exists (idempotent).

        Verifies that:
        - No errors if engine is None
        - Graceful handling of already-closed state
        - No success message printed (nothing to close)

        Args:
            capsys: Pytest fixture to capture stdout/stderr

        Note:
            Idempotent operation - safe to call multiple times.
        """
        database._engine = None
        database._async_session_maker = None

        await database.close_db()

        # Should not print anything if engine is None
        captured = capsys.readouterr()
        assert "✅ Database connections closed" not in captured.out


@pytest.mark.asyncio
class TestCheckDbConnection:
    """Tests for check_db_connection() function.

    Tests database connection health check for monitoring and startup validation.
    """

    async def test_check_db_connection_success(self):
        """Test successful database connection health check.

        Verifies that:
        - Returns True for working connection
        - Can connect to test database
        - No errors during health check

        Note:
            Used for /health endpoint and startup validation.
        """
        result = await database.check_db_connection()

        # Should return True for a working test database
        assert result is True

    async def test_check_db_connection_failure(self, capsys):
        """Test database connection check failure handling.

        Verifies that:
        - Returns False on connection failure
        - Error message printed to stdout
        - Exception caught and handled gracefully
        - No uncaught exceptions raised

        Args:
            capsys: Pytest fixture to capture stdout/stderr

        Note:
            Allows graceful degradation when database unavailable.
        """
        # Mock the engine to simulate connection failure
        with patch.object(database, "get_engine") as mock_get_engine:
            mock_engine = Mock()
            mock_engine.connect = Mock(side_effect=Exception("Connection failed"))
            mock_get_engine.return_value = mock_engine

            result = await database.check_db_connection()

            assert result is False
            captured = capsys.readouterr()
            assert "❌ Database connection check failed" in captured.out


@pytest.mark.asyncio
class TestGetDbContext:
    """Tests for get_db_context() context manager.

    Tests async context manager for database session lifecycle.
    Alternative to FastAPI dependency injection for non-endpoint code.
    """

    async def test_get_db_context_yields_session(self):
        """Test get_db_context yields valid session in async with block.

        Verifies that:
        - Context manager yields AsyncSession
        - Session is valid for database operations
        - Can be used in service layer

        Note:
            Used for background tasks and service methods.
        """
        async with database.get_db_context() as session:
            assert session is not None
            assert isinstance(session, AsyncSession)

    async def test_get_db_context_closes_session(self):
        """Test get_db_context closes session on normal exit.

        Verifies that:
        - Session close() called on context exit
        - Cleanup happens automatically
        - No connection leaks
        - Close called at least once

        Note:
            Ensures proper resource cleanup.
        """
        session_ref = None

        async with database.get_db_context() as session:
            session_ref = session
            # Mock close to verify it's called
            original_close = session.close
            session.close = AsyncMock(wraps=original_close)

        # Verify close was called (may be called twice due to context manager)
        assert session_ref.close.called
        assert session_ref.close.call_count >= 1

    async def test_get_db_context_closes_session_on_exception(self):
        """Test get_db_context closes session even on exception.

        Verifies that:
        - Session close() called even if exception raised
        - Cleanup happens in finally block
        - No connection leaks on errors
        - Exception still propagates to caller

        Raises:
            ValueError: Test exception (expected)

        Note:
            Critical: ensures cleanup even on errors.
        """
        session_ref = None

        with pytest.raises(ValueError, match="Test exception"):
            async with database.get_db_context() as session:
                session_ref = session
                # Mock close to verify it's called
                original_close = session.close
                session.close = AsyncMock(wraps=original_close)
                raise ValueError("Test exception")

        # Verify close was called even with exception
        assert session_ref.close.called
        assert session_ref.close.call_count >= 1
