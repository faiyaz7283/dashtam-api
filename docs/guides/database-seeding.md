# Database Seeding Guide

## Overview

Database seeding provides initial data required for the application to function. Dashtam uses idempotent seeders that run automatically after Alembic migrations.

**Philosophy**: Seeders bootstrap essential data. All subsequent changes are managed through admin APIs (properly audited).

---

## Architecture

### Directory Structure

```text
alembic/
├── env.py                # Post-migration hook calls seeders
├── versions/             # Migration files
└── seeds/
    ├── __init__.py       # Exports run_all_seeders()
    ├── rbac_seeder.py    # RBAC policies (F1.1b)
    └── ...               # Future seeders
```

**Why `alembic/seeds/` instead of `src/`?**

- Seeds only run via Alembic (post-migration hook)
- Seeds use raw SQLAlchemy, not application adapters
- Keeps Alembic concerns co-located
- Clean separation from application code

### Flow

```text
┌─────────────────────────────────────────────────────────────┐
│                    Seeding Flow                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   1. alembic upgrade head                                   │
│      └── Runs migrations                                    │
│                          │                                  │
│                          ↓                                  │
│   2. Post-migration hook                                    │
│      └── Calls run_all_seeders()                            │
│                          │                                  │
│                          ↓                                  │
│   3. Each seeder runs                                       │
│      └── INSERT ... ON CONFLICT DO NOTHING                  │
│                          │                                  │
│                          ↓                                  │
│   4. First run: Data inserted                               │
│      Subsequent runs: No-op (data exists)                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation

### Seeder Pattern

Each seeder follows this pattern:

```python
# alembic/seeds/example_seeder.py
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_example_data(session: AsyncSession) -> None:
    """Seed example data. Idempotent via ON CONFLICT DO NOTHING.

    Note:
        After initial seeding, all changes should be managed via
        admin APIs (properly audited, authorized).
    """
    data = [
        {"name": "value1", "config": "setting1"},
        {"name": "value2", "config": "setting2"},
    ]

    for item in data:
        await session.execute(
            text("""
                INSERT INTO example_table (name, config)
                VALUES (:name, :config)
                ON CONFLICT DO NOTHING
            """),
            item,
        )
```

**Key Points**:

- `ON CONFLICT DO NOTHING` makes it idempotent
- No version tracking needed - seeders are no-ops if data exists
- Document that changes after seeding go through admin APIs

### Seeder Runner

```python
# alembic/seeds/__init__.py
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from seeds.provider_seeder import seed_providers
from seeds.rbac_seeder import seed_rbac_policies

logger = structlog.get_logger(__name__)


async def run_all_seeders(session: AsyncSession) -> None:
    """Run all database seeders. Called after Alembic migrations.

    All seeders are idempotent - safe to run on every migration.
    Uses existence checks or ON CONFLICT DO NOTHING for insert operations.

    Args:
        session: Async database session.
    """
    logger.info("seeding_started")

    # Run RBAC seeder (F1.1b - User Authorization)
    await seed_rbac_policies(session)

    # Run Provider seeder (F4.1 - Provider Integration)
    await seed_providers(session)

    # Add future seeders here:
    # await seed_feature_flags(session)

    logger.info("seeding_completed")
```

### Alembic Integration

```python
# alembic/env.py
async def run_async_migrations() -> None:
    """Run migrations in async mode."""
    connectable = async_engine_from_config(...)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    # Run seeders after migrations complete
    await _run_seeders(connectable)

    await connectable.dispose()


async def _run_seeders(engine: AsyncEngine) -> None:
    """Execute idempotent seeders after migrations."""
    import os
    import sys

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    # Add alembic directory to path for local seeds import
    alembic_dir = os.path.dirname(__file__)
    if alembic_dir not in sys.path:
        sys.path.insert(0, alembic_dir)

    from seeds import run_all_seeders

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await run_all_seeders(session)
        await session.commit()
```

---

## When to Use Seeders

### ✅ Use Seeders For

- **System roles/permissions** - App won't function without them
- **Default configuration** - Required settings with sensible defaults
- **Lookup/reference data** - Status codes, types that code depends on
- **Required system records** - Single-row config tables

### ❌ Don't Use Seeders For

- **User data** - Created through normal app flow
- **Test data** - Use fixtures in tests
- **Optional configuration** - Let admins set via UI/API
- **Frequently changing data** - Use admin APIs instead

---

## Adding a New Seeder

1. **Create seeder file**:

   ```python
   # alembic/seeds/new_seeder.py
   async def seed_new_data(session: AsyncSession) -> None:
       ...
   ```

2. **Register in runner**:

   ```python
   # alembic/seeds/__init__.py
   from seeds.new_seeder import seed_new_data

   async def run_all_seeders(session: AsyncSession) -> None:
       await seed_rbac_policies(session)
       await seed_new_data(session)  # Add here
   ```

3. **Test locally**:

   ```bash
   make db-migrate  # Seeders run automatically
   ```

---

## Design Decisions

### Why Idempotent Seeders?

- **Simple** - No version tracking, no seed history table
- **Safe** - Can run on every migration without side effects
- **Predictable** - `ON CONFLICT DO NOTHING` = clear behavior

### Why Not Version-Tracked Seeders?

- **Overkill** - Seeders only provide bootstrap data
- **Admin APIs** - All ongoing changes go through audited admin APIs
- **Complexity** - Version tracking adds unnecessary machinery

### When Would You Update a Seeder?

**Rarely.** Only for:

- New system role that code depends on
- New required configuration key
- New lookup value that code references

Most "updates" should go through admin APIs instead.

---

## Current Seeders

- **`rbac_seeder.py`** (F1.1b) - Default roles (readonly, user, admin), permissions, and role hierarchy for Casbin RBAC
- **`provider_seeder.py`** (F4.1) - Built-in providers (Charles Schwab, Alpaca, Chase Bank file import)

---

**Created**: 2025-11-27 | **Last Updated**: 2026-01-10
