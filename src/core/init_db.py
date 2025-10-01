#!/usr/bin/env python3
"""
Database initialization script.

This script handles database setup including:
- Creating all tables from SQLModel models
- Running any pending Alembic migrations (if configured)
- Seeding initial data if needed

This follows the best practice of being idempotent - safe to run multiple times.
"""

import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# Add project root to path for src imports  
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import from src after path setup
from src.core.config import settings  # noqa: E402

# Import all models to register them with SQLModel.metadata
# These imports MUST happen before create_tables() is called
from src.models.user import User  # noqa: E402, F401
from src.models.provider import Provider, ProviderConnection, ProviderToken, ProviderAuditLog  # noqa: E402, F401

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_database_connection(engine: AsyncEngine) -> bool:
    """Test database connectivity.

    Args:
        engine: SQLAlchemy async engine.

    Returns:
        True if connection successful, False otherwise.
    """
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()  # Don't await the row object
            logger.info("✅ Database connection successful")
            return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False


async def create_tables(engine: AsyncEngine) -> None:
    """Create all database tables from SQLModel models.

    This uses SQLModel's metadata.create_all which only creates
    tables that don't already exist, making it safe to run multiple times.

    Args:
        engine: SQLAlchemy async engine.
    """
    logger.info("📋 Creating database tables...")

    async with engine.begin() as conn:
        # This only creates tables that don't exist
        # Safe to run multiple times (idempotent)
        await conn.run_sync(SQLModel.metadata.create_all)

    logger.info("✅ Database tables ready")


async def verify_tables(engine: AsyncEngine) -> None:
    """Verify that all expected tables exist.

    Args:
        engine: SQLAlchemy async engine.
    """
    expected_tables = [
        "users",
        "providers",
        "provider_connections",
        "provider_tokens",
        "provider_audit_logs",
    ]

    async with engine.connect() as conn:
        # Check which tables exist
        result = await conn.execute(
            text("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public'
            """)
        )
        existing_tables = {row[0] for row in result}

        # Report status
        for table in expected_tables:
            if table in existing_tables:
                logger.info(f"  ✅ Table '{table}' exists")
            else:
                logger.warning(f"  ⚠️  Table '{table}' missing")

        # Check for unexpected tables
        unexpected = existing_tables - set(expected_tables)
        if unexpected:
            logger.info(f"  ℹ️  Additional tables found: {', '.join(unexpected)}")


async def seed_initial_data(engine: AsyncEngine) -> None:
    """Seed any initial data needed for the application.

    Currently, we don't need any seed data as users will register
    and add their own provider connections. This function is here
    for future use if needed.

    Args:
        engine: SQLAlchemy async engine.
    """
    # Example: Create a test user in development
    if settings.DEBUG:
        async with AsyncSession(engine) as session:
            # Check if we already have users (only after tables are created)
            try:
                result = await session.execute(text("SELECT COUNT(*) FROM users"))
                user_count = result.scalar()

                if user_count == 0:
                    logger.info("🌱 No users found, skipping seed data")
                    # Uncomment to create a test user:
                    # test_user = User(
                    #     email="test@example.com",
                    #     name="Test User",
                    #     is_verified=True
                    # )
                    # session.add(test_user)
                    # await session.commit()
                    # logger.info("✅ Created test user")
                else:
                    logger.info(f"ℹ️  Found {user_count} existing users")
            except Exception as e:
                logger.info(f"ℹ️  Skipping seed data (tables may not exist yet): {e}")


async def init_db() -> None:
    """Initialize the database.

    This is the main entry point that orchestrates all initialization steps.
    It's designed to be idempotent - safe to run multiple times.
    """
    logger.info("🚀 Starting database initialization...")

    # Create engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,  # Log SQL in development
        pool_pre_ping=True,  # Verify connections before using
    )

    try:
        # Check connection
        if not await check_database_connection(engine):
            logger.error("Failed to connect to database. Exiting.")
            sys.exit(1)

        # Create tables
        await create_tables(engine)

        # Verify tables
        await verify_tables(engine)

        # Seed initial data if needed
        await seed_initial_data(engine)

        logger.info("🎉 Database initialization completed successfully!")

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

    finally:
        # Clean up
        await engine.dispose()


def run_init() -> None:
    """Synchronous wrapper for async init_db.

    This allows the script to be run directly or imported and called.
    """
    try:
        asyncio.run(init_db())
    except KeyboardInterrupt:
        logger.info("Database initialization interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_init()
