"""Alembic environment configuration for async SQLAlchemy.

This module configures Alembic to work with async database operations.
"""

import asyncio
import sys
from logging.config import fileConfig
from typing import TYPE_CHECKING

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import context
from src.core.config import settings
from src.infrastructure.persistence import BaseModel

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get database URL from Settings (not from alembic.ini)
config.set_main_option("sqlalchemy.url", settings.database_url)

# Import all models here for autogenerate support
# This ensures Alembic can detect schema changes
# Note: E402 suppressed because imports must come after config setup
from src.infrastructure.persistence.models.audit_log import AuditLog  # noqa: E402, F401
from src.infrastructure.persistence.models.email_verification_token import (  # noqa: E402, F401
    EmailVerificationToken,
)
from src.infrastructure.persistence.models.password_reset_token import (  # noqa: E402, F401
    PasswordResetToken,
)
from src.infrastructure.persistence.models.refresh_token import RefreshToken  # noqa: E402, F401
from src.infrastructure.persistence.models.security_config import SecurityConfig  # noqa: E402, F401
from src.infrastructure.persistence.models.session import Session  # noqa: E402, F401
from src.infrastructure.persistence.models.casbin_rule import CasbinRule  # noqa: E402, F401
from src.infrastructure.persistence.models.user import User  # noqa: E402, F401
from src.infrastructure.persistence.models.provider_connection import (  # noqa: E402, F401
    ProviderConnection,
)
from src.infrastructure.persistence.models.provider import Provider  # noqa: E402, F401
from src.infrastructure.persistence.models.account import Account  # noqa: E402, F401
from src.infrastructure.persistence.models.transaction import Transaction  # noqa: E402, F401

# Add model's MetaData for autogenerate
target_metadata = BaseModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection.

    Args:
        connection: SQLAlchemy connection to use for migrations.
    """
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


def _should_run_seeders() -> bool:
    """Run seeders during `alembic upgrade` (online) or when forced via -x.

    Robust across different invocation styles (alembic CLI, python -m alembic,
    wrappers) and avoids running during `revision --autogenerate`.
    """
    # 1) Manual override via -x
    try:
        xargs = context.get_x_argument(as_dictionary=True)  # type: ignore[arg-type]
    except Exception:
        xargs = {}
    flag = (xargs.get("run_seeders") or xargs.get("seed") or "").strip().lower()
    forced = flag in {"1", "true", "yes", "y"}

    # 2) Skip in offline SQL generation unless explicitly forced
    if "--sql" in sys.argv:
        return forced

    # 3) Detect upgrade via config.cmd_opts if available
    cmd_opts = getattr(config, "cmd_opts", None)
    is_upgrade = getattr(cmd_opts, "cmd", None) == "upgrade"
    not_sql = not getattr(cmd_opts, "sql", False) if cmd_opts else True

    # 4) Fallback: inspect argv to detect upgrade
    if not is_upgrade:
        argv_lower = " ".join(sys.argv).lower()
        is_upgrade = " upgrade" in argv_lower or argv_lower.endswith("upgrade")

    return (is_upgrade and not_sql) or forced


async def run_async_migrations() -> None:
    """Run migrations in async mode.

    Creates an async engine and runs migrations asynchronously.
    After migrations, optionally runs idempotent database seeders.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    # Run seeders only during `alembic upgrade`
    if _should_run_seeders():
        await _run_seeders(connectable)

    await connectable.dispose()


async def _run_seeders(engine: "AsyncEngine") -> None:
    """Execute idempotent seeders after migrations.

    Seeders populate required bootstrap data (roles, permissions, config).
    All seeders are idempotent - safe to run on every migration.

    Args:
        engine: Async database engine.
    """
    import os
    import sys

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    # Add alembic directory to path for local seeds import
    alembic_dir = os.path.dirname(__file__)
    if alembic_dir not in sys.path:
        sys.path.insert(0, alembic_dir)

    from seeds import run_all_seeders  # noqa: E402

    # Create async session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await run_all_seeders(session)
        await session.commit()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using async engine."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
