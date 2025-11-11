"""Database connection and session management.

This module provides database connection management using SQLAlchemy's
async engine and session handling. It follows dependency injection patterns
to provide database sessions to repositories and services.

Following hexagonal architecture:
- This is an infrastructure concern
- Provides database sessions to repository implementations
- Handles transaction boundaries and connection pooling
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    """Database connection and session management.

    This class manages the database engine and provides async sessions
    for database operations. It handles:
    - Connection pooling
    - Session lifecycle
    - Transaction management

    Usage:
        db = Database("postgresql+asyncpg://user:pass@host/dbname")
        async with db.get_session() as session:
            # Use session for database operations
            # Automatically commits on success, rolls back on error
    """

    def __init__(
        self,
        database_url: str,
        echo: bool = False,
        pool_size: int = 20,
        max_overflow: int = 0,
    ) -> None:
        """Initialize database with connection parameters.

        Args:
            database_url: Database connection URL (e.g., postgresql+asyncpg://...)
            echo: If True, log all SQL statements (useful for debugging)
            pool_size: Number of connections to maintain in pool
            max_overflow: Maximum overflow connections above pool_size
        """
        self.engine: AsyncEngine = create_async_engine(
            database_url,
            echo=echo,
            pool_pre_ping=True,  # Verify connections before use
            pool_size=pool_size,
            max_overflow=max_overflow,
            # PostgreSQL-specific optimizations (but still works with other DBs)
            connect_args={
                "server_settings": {
                    "jit": "off"
                },  # Disable JIT for consistent performance
                "command_timeout": 60,
                "timeout": 30,
            }
            if "postgresql" in database_url
            else {},
        )

        # Create session factory
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit
        )

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide a transactional database session.

        This is a context manager that:
        - Creates a new session
        - Commits on successful exit
        - Rolls back on exception
        - Always closes the session

        Yields:
            AsyncSession: Database session for operations

        Example:
            async with db.get_session() as session:
                user = User(email="test@example.com")
                session.add(user)
                # Automatically commits when context exits
        """
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide an explicit transaction context.

        Use this when you need explicit transaction control,
        especially for operations that span multiple repositories.

        Yields:
            AsyncSession: Database session within a transaction

        Example:
            async with db.transaction() as session:
                user_repo = UserRepository(session)
                account_repo = AccountRepository(session)

                await user_repo.save(user)
                await account_repo.save(account)
                # Both operations commit together
        """
        async with self.get_session() as session:
            async with session.begin():
                yield session

    async def create_all(self) -> None:
        """Create all tables defined in the models.

        Warning: This should only be used for development/testing.
        Production should use Alembic migrations.
        """
        from src.infrastructure.persistence.base import BaseModel

        async with self.engine.begin() as conn:
            await conn.run_sync(BaseModel.metadata.create_all)

    async def drop_all(self) -> None:
        """Drop all tables defined in the models.

        Warning: This will delete all data! Only use for testing.
        """
        from src.infrastructure.persistence.base import BaseModel

        async with self.engine.begin() as conn:
            await conn.run_sync(BaseModel.metadata.drop_all)

    async def close(self) -> None:
        """Close all database connections.

        Should be called when shutting down the application.
        """
        await self.engine.dispose()

    async def check_connection(self) -> bool:
        """Check if database connection is working.

        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception:
            return False
