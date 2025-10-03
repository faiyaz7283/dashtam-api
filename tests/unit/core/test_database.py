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
    """Tests for get_engine() function."""

    def setup_method(self):
        """Reset global engine before each test."""
        database._engine = None
        database._async_session_maker = None

    def test_get_engine_creates_new_engine(self):
        """Test that get_engine creates a new engine if none exists."""
        engine = database.get_engine()

        assert engine is not None
        assert isinstance(engine, AsyncEngine)
        assert database._engine is engine

    def test_get_engine_returns_existing_engine(self):
        """Test that get_engine returns the same engine on subsequent calls."""
        engine1 = database.get_engine()
        engine2 = database.get_engine()

        assert engine1 is engine2

    def test_get_engine_raises_if_no_database_url(self):
        """Test that get_engine raises RuntimeError if DATABASE_URL is not set."""
        database._engine = None

        with patch.object(settings, "DATABASE_URL", None):
            with pytest.raises(RuntimeError, match="DATABASE_URL is not configured"):
                database.get_engine()

    def test_get_engine_configuration(self):
        """Test that engine is created with correct configuration."""
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
    """Tests for get_session_maker() function."""

    def setup_method(self):
        """Reset global session maker before each test."""
        database._engine = None
        database._async_session_maker = None

    def test_get_session_maker_creates_new_maker(self):
        """Test that get_session_maker creates a new session maker if none exists."""
        session_maker = database.get_session_maker()

        assert session_maker is not None
        assert database._async_session_maker is session_maker

    def test_get_session_maker_returns_existing_maker(self):
        """Test that get_session_maker returns the same maker on subsequent calls."""
        maker1 = database.get_session_maker()
        maker2 = database.get_session_maker()

        assert maker1 is maker2

    def test_get_session_maker_uses_existing_engine(self):
        """Test that session maker uses the existing engine."""
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
    """Tests for get_session() dependency injection function."""

    def setup_method(self):
        """Reset global state before each test."""
        database._engine = None
        database._async_session_maker = None

    async def test_get_session_yields_session(self):
        """Test that get_session yields a valid AsyncSession."""
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
        """Test that get_session properly closes the session."""
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
    """Tests for init_db() function."""

    async def test_init_db_creates_tables(self, capsys):
        """Test that init_db creates tables and prints success message."""
        # Reset engine to ensure clean state
        database._engine = None

        await database.init_db()

        captured = capsys.readouterr()
        assert "✅ Database tables created successfully" in captured.out


@pytest.mark.asyncio
class TestCloseDb:
    """Tests for close_db() function."""

    async def test_close_db_disposes_engine(self, capsys):
        """Test that close_db properly disposes of the engine."""
        # Create an engine first
        database.get_engine()
        assert database._engine is not None

        await database.close_db()

        assert database._engine is None
        assert database._async_session_maker is None

        captured = capsys.readouterr()
        assert "✅ Database connections closed" in captured.out

    async def test_close_db_handles_no_engine(self, capsys):
        """Test that close_db handles the case when no engine exists."""
        database._engine = None
        database._async_session_maker = None

        await database.close_db()

        # Should not print anything if engine is None
        captured = capsys.readouterr()
        assert "✅ Database connections closed" not in captured.out


@pytest.mark.asyncio
class TestCheckDbConnection:
    """Tests for check_db_connection() function."""

    async def test_check_db_connection_success(self):
        """Test successful database connection check."""
        result = await database.check_db_connection()

        # Should return True for a working test database
        assert result is True

    async def test_check_db_connection_failure(self, capsys):
        """Test database connection check failure handling."""
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
    """Tests for get_db_context() context manager."""

    async def test_get_db_context_yields_session(self):
        """Test that get_db_context yields a valid session."""
        async with database.get_db_context() as session:
            assert session is not None
            assert isinstance(session, AsyncSession)

    async def test_get_db_context_closes_session(self):
        """Test that get_db_context closes session on exit."""
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
        """Test that get_db_context closes session even when exception occurs."""
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
