"""Database connection and session management.

This module handles all database connectivity for the Dashtam application,
including async session management, connection pooling, and database lifecycle
operations. It uses SQLModel with async SQLAlchemy for optimal performance.

The module provides dependency injection functions for FastAPI routes to get
database sessions, ensuring proper session lifecycle management and cleanup.

Example:
    >>> from src.core.database import get_session
    >>> from fastapi import Depends
    >>>
    >>> @app.get("/items")
    >>> async def get_items(session: AsyncSession = Depends(get_session)):
    >>>     result = await session.exec(select(Item))
    >>>     return result.all()
"""

from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)
from sqlmodel import SQLModel

from src.core.config import settings


# Global engine instance (created once at startup)
_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker | None = None


def get_engine() -> AsyncEngine:
    """Get or create the global async database engine.

    This function returns the global database engine instance, creating it
    if it doesn't exist. The engine is configured with connection pooling
    and other optimizations based on application settings.

    Returns:
        The global AsyncEngine instance for database connections.

    Raises:
        RuntimeError: If database URL is not configured.

    Note:
        The engine is thread-safe and handles connection pooling automatically.
    """
    global _engine

    if _engine is None:
        if not settings.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured")

        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DB_ECHO,
            future=True,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )

    return _engine


def get_session_maker() -> async_sessionmaker:
    """Get or create the global async session maker.

    This function returns a session maker factory that can be used to create
    new database sessions with consistent configuration.

    Returns:
        An async_sessionmaker instance for creating database sessions.
    """
    global _async_session_maker

    if _async_session_maker is None:
        engine = get_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    return _async_session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection function for database sessions.

    This async generator function is designed to be used with FastAPI's
    dependency injection system. It provides a database session that is
    automatically closed after the request completes.

    Yields:
        An AsyncSession instance for database operations.

    Example:
        >>> from fastapi import Depends
        >>>
        >>> @app.get("/users")
        >>> async def get_users(session: AsyncSession = Depends(get_session)):
        >>>     result = await session.exec(select(User))
        >>>     return result.all()
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize the database by creating all tables.

    This function creates all database tables defined by SQLModel models.
    It should be called once during application startup in development
    or testing environments.

    Warning:
        This is for development only. Use Alembic migrations for production
        to preserve data and handle schema changes properly.

    Raises:
        Exception: If database initialization fails.
    """
    engine = get_engine()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    print("✅ Database tables created successfully")


async def close_db() -> None:
    """Close the database connection and cleanup resources.

    This function properly disposes of the database engine and its
    connection pool. Should be called during application shutdown.
    """
    global _engine, _async_session_maker

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
        print("✅ Database connections closed")


async def check_db_connection() -> bool:
    """Check if the database is accessible and responsive.

    This function attempts to execute a simple query to verify that
    the database is reachable and functioning properly.

    Returns:
        True if the database is accessible, False otherwise.

    Example:
        >>> if await check_db_connection():
        >>>     print("Database is healthy")
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            _ = result.scalar()
        return True
    except Exception as e:
        print(f"❌ Database connection check failed: {e}")
        return False


@asynccontextmanager
async def get_db_context():
    """Context manager for database operations outside of FastAPI requests.

    This context manager provides a convenient way to work with database
    sessions in scripts, background tasks, or other contexts outside of
    FastAPI's dependency injection system.

    Yields:
        An AsyncSession instance that is automatically closed on exit.

    Example:
        >>> async with get_db_context() as session:
        >>>     user = User(name="John", email="john@example.com")
        >>>     session.add(user)
        >>>     await session.commit()
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
