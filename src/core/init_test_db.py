#!/usr/bin/env python3
"""
Test database initialization script.

This script handles test database setup with optimizations for testing:
- Fast table creation and cleanup
- No seed data (tests provide their own fixtures)
- Test environment validation
- Idempotent operations safe for CI/CD

This follows the same patterns as init_db.py but optimized for testing workflows.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlmodel import SQLModel

# Add project root to path for test imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import from tests after path setup
from tests.test_config import get_test_settings, TestSettings  # noqa: E402

# Import all models so SQLModel.metadata knows about them
from src.models.user import User  # noqa: E402, F401
from src.models.provider import (
    Provider,
    ProviderConnection,
    ProviderToken,
    ProviderAuditLog,
)  # noqa: E402, F401

# Configure logging for test environment
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def check_test_database_connection(
    engine: AsyncEngine, settings: TestSettings
) -> bool:
    """Test database connectivity with additional safety checks.

    Args:
        engine: SQLAlchemy async engine configured for test database.
        settings: Test configuration settings.

    Returns:
        True if connection successful and safe for testing, False otherwise.

    Raises:
        RuntimeError: If not in test environment.
    """
    # Safety check - ensure we're in test environment
    if not settings.is_test_environment:
        raise RuntimeError(
            "SAFETY CHECK FAILED: init_test_db.py can only be run in test environment. "
            f"Current environment: {settings.ENVIRONMENT}, DATABASE_URL: {settings.DATABASE_URL}"
        )

    logger.info("🔍 Checking test database connection...")
    try:
        async with engine.connect() as conn:
            # Test basic connectivity
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()

            # Verify we're connected to test database
            db_name_result = await conn.execute(text("SELECT current_database()"))
            db_name = db_name_result.scalar()

            if "test" not in db_name.lower():
                raise RuntimeError(f"Connected to non-test database: {db_name}")

            logger.info(f"✅ Test database connection successful: {db_name}")
            return True

    except Exception as e:
        logger.error(f"❌ Test database connection failed: {e}")
        return False


async def create_test_tables(engine: AsyncEngine, settings: TestSettings) -> None:
    """Create all database tables optimized for testing.

    This uses SQLModel's metadata.create_all which is idempotent - safe to run
    multiple times. Tables are created with test-optimized settings.

    Args:
        engine: SQLAlchemy async engine configured for test database.
        settings: Test configuration settings.
    """
    logger.info("📋 Creating test database tables...")

    async with engine.begin() as conn:
        # Drop all tables first for clean test environment
        # This ensures we start with a completely fresh schema each time
        logger.info("🧹 Dropping existing tables for clean test environment...")
        await conn.run_sync(SQLModel.metadata.drop_all)

        # Create all tables fresh
        logger.info("🏗️  Creating fresh test tables...")
        await conn.run_sync(SQLModel.metadata.create_all)

    logger.info("✅ Test database tables ready")


async def verify_test_tables(engine: AsyncEngine) -> None:
    """Verify that all expected tables exist in test database.

    Args:
        engine: SQLAlchemy async engine configured for test database.
    """
    expected_tables = [
        "users",
        "providers",
        "provider_connections",
        "provider_tokens",
        "provider_audit_logs",
    ]

    logger.info("🔍 Verifying test table structure...")

    async with engine.connect() as conn:
        # Check which tables exist
        result = await conn.execute(
            text("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
        )
        existing_tables = {row[0] for row in result}

        # Report status
        all_tables_exist = True
        for table in expected_tables:
            if table in existing_tables:
                logger.info(f"  ✅ Table '{table}' exists")
            else:
                logger.error(f"  ❌ Table '{table}' MISSING")
                all_tables_exist = False

        # Check for unexpected tables (informational)
        unexpected = existing_tables - set(expected_tables) - {"alembic_version"}
        if unexpected:
            logger.info(
                f"  ℹ️  Additional tables found: {', '.join(sorted(unexpected))}"
            )

        if not all_tables_exist:
            raise RuntimeError(
                "Test database setup incomplete - missing required tables"
            )

        logger.info("✅ All test tables verified successfully")


async def prepare_test_database_constraints(engine: AsyncEngine) -> None:
    """Set up test-specific database constraints and optimizations.

    This configures the test database for optimal performance and isolation.

    Args:
        engine: SQLAlchemy async engine configured for test database.
    """
    logger.info("⚡ Optimizing test database settings...")

    async with engine.connect() as conn:
        # Set test-optimized PostgreSQL settings for better performance
        test_settings = [
            "SET synchronous_commit = OFF",  # Faster commits for tests
            "SET fsync = OFF",  # Disable disk sync for speed
            "SET full_page_writes = OFF",  # Reduce I/O for tests
        ]

        for setting in test_settings:
            try:
                await conn.execute(text(setting))
                logger.debug(f"Applied setting: {setting}")
            except Exception as e:
                logger.warning(f"Could not apply setting '{setting}': {e}")

    logger.info("✅ Test database optimization complete")


async def init_test_db(settings: Optional[TestSettings] = None) -> None:
    """Initialize the test database.

    This is the main entry point that orchestrates all test database setup.
    It's designed to be idempotent and optimized for testing workflows.

    Args:
        settings: Optional test settings. If None, will load from environment.

    Raises:
        RuntimeError: If not in test environment or setup fails.
    """
    if settings is None:
        settings = get_test_settings()

    logger.info("🚀 Starting test database initialization...")
    logger.info(f"🎯 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🗄️  Database: {settings.test_database_url}")

    # Create engine with test-specific configuration
    engine = create_async_engine(
        settings.test_database_url,
        echo=settings.DB_ECHO,  # Control SQL logging via test config
        pool_pre_ping=True,  # Verify connections before using
        # Test-optimized pool settings
        pool_size=2,  # Smaller pool for tests
        max_overflow=5,
        pool_recycle=300,  # Recycle connections every 5 minutes
    )

    try:
        # Safety and connectivity checks
        if not await check_test_database_connection(engine, settings):
            logger.error("Test database connection check failed. Exiting.")
            sys.exit(1)

        # Apply test database optimizations
        await prepare_test_database_constraints(engine)

        # Create tables with clean slate approach
        await create_test_tables(engine, settings)

        # Verify everything is set up correctly
        await verify_test_tables(engine)

        logger.info("🎉 Test database initialization completed successfully!")
        logger.info("🧪 Database is ready for testing workflows")

    except Exception as e:
        logger.error(f"❌ Test database initialization failed: {e}")
        logger.error("This may indicate a configuration or connectivity issue")
        raise

    finally:
        # Clean up engine
        await engine.dispose()


def run_test_init() -> None:
    """Synchronous wrapper for async init_test_db.

    This allows the script to be run directly from command line or Make targets.
    Includes proper error handling and exit codes for CI/CD integration.
    """
    try:
        logger.info("🎯 Dashtam Test Database Initialization")
        logger.info("=" * 50)

        asyncio.run(init_test_db())

        logger.info("=" * 50)
        logger.info("✅ SUCCESS: Test database is ready!")

    except KeyboardInterrupt:
        logger.info("🛑 Test database initialization interrupted by user")
        sys.exit(130)  # Standard exit code for SIGINT

    except Exception as e:
        logger.error("=" * 50)
        logger.error(f"❌ FAILED: Test database initialization error: {e}")
        logger.error("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    run_test_init()
