# Database Migrations with Alembic

## Overview

Dashtam uses **Alembic** for database schema migrations, providing version-controlled, automated database schema evolution. All environments (development, test, and CI/CD) automatically run migrations on startup, ensuring database schemas are always synchronized with the codebase.

**Migration Philosophy:**

- ✅ **Automated:** Migrations run automatically on container startup
- ✅ **Version-controlled:** All schema changes tracked in Git
- ✅ **Timezone-aware:** All datetime columns use `TIMESTAMPTZ` for UTC compliance
- ✅ **Async-compatible:** Full support for SQLAlchemy AsyncSession
- ✅ **Docker-integrated:** All migration operations occur in containers

---

## Quick Reference

### Common Commands

```bash
# Generate new migration (autogenerate from models)
make migrate-create MESSAGE="description of changes"

# Apply migrations (upgrade to latest)
make migrate-up

# Rollback last migration
make migrate-down

# View migration history
make migrate-history

# Check current migration version
make migrate-current

# Generate migration with empty script (manual)
make migrate-create-manual MESSAGE="custom migration"
```

### Emergency Commands

```bash
# Reset database and apply all migrations from scratch
make dev-down
docker volume rm dashtam_dev_postgres_data
make dev-up  # Migrations run automatically

# View migration status
make migrate-status
```

---

## Architecture

### Directory Structure

```bash
Dashtam/
├── alembic/                          # Alembic migration directory
│   ├── versions/                     # Migration scripts
│   │   └── 20251003_2149-bce8c437167b_initial_database_schema_with_timezone_.py
│   ├── env.py                        # Alembic environment config
│   ├── script.py.mako                # Migration template
│   └── README                        # Alembic default README
├── alembic.ini                       # Alembic configuration
├── src/models/                       # SQLModel database models (source of truth)
│   ├── base.py
│   ├── user.py
│   └── provider.py
└── docker/
    └── Dockerfile                    # Migration execution in entrypoint
```

### Migration Workflow

```mermaid
graph LR
    A[Modify SQLModel] --> B[Generate Migration]
    B --> C[Review Migration]
    C --> D[Test Migration]
    D --> E[Commit to Git]
    E --> F[Deploy - Auto Run]
```

---

## Configuration

### alembic.ini

Key configuration settings:

```ini
[alembic]
# Timestamped filenames with timezone
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(rev)s_%%(slug)s
timezone = UTC

# Database URL (overridden by env.py from environment variable)
sqlalchemy.url = driver://user:pass@localhost/dbname

# Migration location
script_location = alembic

# Version table name
version_table = alembic_version
version_table_schema = public

# Migration hooks (with ruff linting)
[post_write_hooks]
hooks = ruff_format ruff_lint
ruff_format.type = console_scripts
ruff_format.entrypoint = ruff
ruff_format.options = format REVISION_SCRIPT_FILENAME
ruff_lint.type = console_scripts
ruff_lint.entrypoint = ruff
ruff_lint.options = check --fix REVISION_SCRIPT_FILENAME
```

### env.py (Migration Environment)

Critical settings in `alembic/env.py`:

```python
# Async database support
from sqlalchemy.ext.asyncio import create_async_engine

# Import all models for autogeneration
from src.models.base import SQLModel
from src.models.user import User
from src.models.provider import (
    Provider,
    ProviderConnection,
    ProviderToken,
    ProviderAuditLog,
)

# Use SQLModel metadata
target_metadata = SQLModel.metadata

# Async migration execution
def run_migrations_online() -> None:
    connectable = create_async_engine(
        url=config.get_main_option("sqlalchemy.url"),
        echo=True,
    )
    # ... async execution logic
```

---

## Automatic Migration Execution

### Development Environment

**When:** Every time containers start with `make dev-up`

**Dockerfile Entrypoint** (`docker/Dockerfile`):

```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000"]
```

**What Happens:**

1. Container starts
2. `alembic upgrade head` runs automatically
3. All pending migrations apply
4. FastAPI application starts
5. Database ready with latest schema

**Logs:**

```bash
dashtam-dev-app | Running Alembic migrations...
dashtam-dev-app | INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
dashtam-dev-app | INFO  [alembic.runtime.migration] Will assume transactional DDL.
dashtam-dev-app | INFO  [alembic.runtime.migration] Running upgrade  -> bce8c437167b, Initial database schema
dashtam-dev-app | Alembic migrations completed successfully
```

### Test Environment

**When:** Every time test containers start with `make test-up`

**Automatic Migration:** Same as development, migrations run before tests

**Benefits:**

- ✅ Test database always matches production schema
- ✅ No manual database initialization needed
- ✅ Clean slate for every test run

### CI/CD Environment

**When:** During CI pipeline execution

**docker-compose.ci.yml:**

```yaml
services:
  app:
    command: >
      sh -c "
        alembic upgrade head &&
        uv run pytest tests/ --verbose --tb=short --cov=src --cov-report=xml
      "
```

**What Happens:**

1. CI container starts
2. Migrations run automatically
3. Tests execute against migrated schema
4. CI validates migration correctness

---

## Creating Migrations

### Method 1: Autogeneration (Recommended)

**Use when:** You've modified SQLModel models and want Alembic to detect changes automatically.

**Steps:**

**Modify your SQLModel:**

```python
# src/models/user.py
class User(BaseModel, table=True):
    __tablename__ = "users"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    # NEW FIELD:
    phone_number: str | None = Field(default=None, max_length=20)
```

**Generate migration** (inside Docker container):

```bash
# Use Make target (recommended)
make migrate-create MESSAGE="add user phone number field"

# Or manually
docker compose -f docker-compose.dev.yml exec app \
  alembic revision --autogenerate -m "add user phone number field"
```

**Review generated migration:**

```python
# alembic/versions/20251003_2315-abc123def456_add_user_phone_number_field.py

def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('phone_number', sa.String(length=20), nullable=True))
    # ### end Alembic commands ###

def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'phone_number')
    # ### end Alembic commands ###
```

**Test migration:**

```bash
# Apply migration
make migrate-up

# Verify schema
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U dashtam_dev_user -d dashtam_dev -c "\d users"

# Check data integrity
docker compose -f docker-compose.dev.yml exec app uv run pytest tests/
```

**Rollback test** (optional but recommended):

```bash
# Rollback one step
make migrate-down

# Verify rollback
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U dashtam_dev_user -d dashtam_dev -c "\d users"

# Reapply
make migrate-up
```

**Commit migration:**

```bash
git add alembic/versions/20251003_2315-abc123def456_add_user_phone_number_field.py
git commit -m "feat(database): add phone_number field to users table"
```

### Method 2: Empty Migration (Manual)

**Use when:** You need to write custom SQL or perform data migrations.

**Steps:**

**Create empty migration:**

```bash
make migrate-create-manual MESSAGE="migrate user email format"
```

**Edit migration script manually:**

```python
# alembic/versions/20251003_2320-xyz789_migrate_user_email_format.py

def upgrade() -> None:
    # Custom SQL migration
    op.execute("""
        UPDATE users 
        SET email = LOWER(TRIM(email))
        WHERE email != LOWER(TRIM(email))
    """)
    
    # Add constraint after data migration
    op.create_check_constraint(
        "email_lowercase_check",
        "users",
        "email = LOWER(email)"
    )

def downgrade() -> None:
    op.drop_constraint("email_lowercase_check", "users", type_="check")
```

**Test thoroughly** (custom migrations require extra care):

```bash
make migrate-up
# Verify data transformation
# Run integration tests
make migrate-down  # Test rollback
make migrate-up    # Reapply
```

---

## Migration Best Practices

### ✅ DO's

1. **Always Review Autogenerated Migrations**
   - Alembic may miss relationships or constraints
   - Verify column types are correct (especially `TIMESTAMPTZ`)
   - Check for unintended changes

2. **Use Timezone-Aware Datetimes**

   ```python
   # ✅ CORRECT
   op.add_column('table', sa.Column('created_at', sa.TIMESTAMP(timezone=True)))
   
   # ❌ WRONG
   op.add_column('table', sa.Column('created_at', sa.DateTime()))
   ```

3. **Test Both Upgrade and Downgrade**
   - Always ensure migrations can roll back
   - Test data integrity after rollback
   - Document any irreversible migrations

4. **Use Descriptive Messages**

   ```bash
   # ✅ Good
   make migrate-create MESSAGE="add user phone verification fields"
   
   # ❌ Bad
   make migrate-create MESSAGE="update users"
   ```

5. **One Logical Change Per Migration**
   - Don't combine unrelated schema changes
   - Makes rollback easier and safer
   - Improves git history clarity

6. **Document Complex Migrations**

   ```python
   def upgrade() -> None:
       """
       Adds phone_number field to users table.
       
       This migration is part of implementing two-factor authentication.
       Related issue: #123
       """
       op.add_column('users', sa.Column('phone_number', sa.String(20)))
   ```

### ❌ DON'Ts

1. **Never Edit Existing Migrations**
   - Once committed and deployed, migrations are immutable
   - Create a new migration to fix issues
   - Exception: Pre-production migrations not yet deployed

2. **Avoid Direct SQL When Possible**

   ```python
   # ❌ Avoid
   op.execute("ALTER TABLE users ADD COLUMN email VARCHAR(255)")
   
   # ✅ Prefer
   op.add_column('users', sa.Column('email', sa.String(255)))
   ```

3. **Don't Assume Database State**
   - Always check if objects exist before dropping
   - Use `if_exists=True` where supported
   - Handle edge cases in data migrations

4. **Never Commit Untested Migrations**
   - Always test upgrade path
   - Test downgrade path
   - Run full test suite after migration

5. **Don't Skip Version Control**
   - All migration files must be committed
   - Keep migrations in chronological order
   - Never delete migration files from git history

---

## Timezone-Aware Datetime Implementation

### Why TIMESTAMPTZ?

Financial applications like Dashtam **must** use timezone-aware datetimes for:

- ✅ **Regulatory compliance:** Accurate audit trails across timezones
- ✅ **Data integrity:** Unambiguous temporal ordering
- ✅ **OAuth token management:** Proper expiration handling
- ✅ **Financial transaction accuracy:** Correct time-based operations

### Implementation

**SQLModel Definition:**

```python
from datetime import datetime, timezone
from sqlmodel import Field
import sqlalchemy as sa

class BaseModel(SQLModel):
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=sa.Column(
            sa.TIMESTAMP(timezone=True),  # TIMESTAMPTZ in PostgreSQL
            nullable=False,
        ),
    )
```

**Alembic Migration:**

```python
def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
```

**Verification:**

```sql
-- Check column types in PostgreSQL
\d+ users

-- Should show:
-- created_at | timestamp with time zone | not null
```

### Converting Existing Columns

If you need to migrate existing `TIMESTAMP` columns to `TIMESTAMPTZ`:

```python
def upgrade() -> None:
    # Modify column type
    op.alter_column(
        'users',
        'created_at',
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(timezone=False),
        existing_nullable=False,
    )

def downgrade() -> None:
    op.alter_column(
        'users',
        'created_at',
        type_=sa.TIMESTAMP(timezone=False),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )
```

---

## Troubleshooting

### Issue 1: Migration Fails on Startup

**Symptom:**

```bash
alembic.util.exc.CommandError: Can't locate revision identified by 'abc123'
```

**Cause:** Migration file missing or corrupted

**Solution:**

```bash
# Check migration history
make migrate-history

# Verify all migration files exist
ls -la alembic/versions/

# Reset to known good state
make dev-down
docker volume rm dashtam_dev_postgres_data
make dev-up
```

### Issue 2: Autogeneration Misses Changes

**Symptom:** Modified model but autogeneration creates empty migration

**Cause:** Model not imported in `alembic/env.py`

**Solution:**

```python
# alembic/env.py - Add missing import
from src.models.your_new_model import YourNewModel
```

### Issue 3: Migration Works Locally, Fails in CI

**Symptom:** Migration passes in dev, fails in CI/CD

**Cause:** Different database states or missing migrations

**Solution:**

```bash
# Ensure clean CI database
# In docker-compose.ci.yml:
postgres:
  tmpfs:
    - /var/lib/postgresql/data  # Always starts clean

# Verify all migrations committed
git status
git add alembic/versions/
```

### Issue 4: Downgrade Fails

**Symptom:**

```bash
sqlalchemy.exc.IntegrityError: (psycopg.errors.NotNullViolation)
```

**Cause:** Downgrade doesn't handle data properly

**Solution:**

```python
def downgrade() -> None:
    # Handle data before schema change
    op.execute("UPDATE table SET old_column = new_column")
    op.drop_column('table', 'new_column')
```

### Issue 5: Timezone Comparison Errors

**Symptom:**

```bash
TypeError: can't compare offset-naive and offset-aware datetimes
```

**Cause:** Mixing timezone-naive and timezone-aware datetimes

**Solution:**

```python
# ❌ WRONG
from datetime import datetime
now = datetime.now()  # Timezone-naive

# ✅ CORRECT
from datetime import datetime, timezone
now = datetime.now(timezone.utc)  # Timezone-aware
```

---

## Advanced Topics

### Branching and Merge Migrations

When multiple developers create migrations simultaneously:

**Problem:** Two migrations have same parent revision

**Detection:**

```bash
alembic heads
# Shows: abc123 (head), def456 (head)  # Multiple heads!
```

**Solution:** Create merge migration

```bash
docker compose -f docker-compose.dev.yml exec app \
  alembic merge -m "merge feature branches" abc123 def456
```

### Data Migrations

**Pattern:** Separate schema and data changes

```python
def upgrade() -> None:
    # 1. Add nullable column first
    op.add_column('users', sa.Column('full_name', sa.String(255), nullable=True))
    
    # 2. Migrate data
    connection = op.get_bind()
    connection.execute(
        text("UPDATE users SET full_name = first_name || ' ' || last_name")
    )
    
    # 3. Make column non-nullable after data migration
    op.alter_column('users', 'full_name', nullable=False)
```

### Testing Migrations in Isolation

```bash
# Create test database
docker compose -f docker-compose.dev.yml exec postgres \
  createdb -U dashtam_dev_user dashtam_test_migration

# Run migrations on test database
DATABASE_URL="postgresql+asyncpg://dashtam_dev_user:dashtam_dev_pass@postgres:5432/dashtam_test_migration" \
  docker compose -f docker-compose.dev.yml exec app alembic upgrade head

# Test queries on migrated database
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U dashtam_dev_user -d dashtam_test_migration

# Clean up
docker compose -f docker-compose.dev.yml exec postgres \
  dropdb -U dashtam_dev_user dashtam_test_migration
```

---

## Integration with CI/CD

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
- name: Run Database Migrations
  run: |
    docker-compose -f docker-compose.ci.yml up -d postgres redis
    docker-compose -f docker-compose.ci.yml run --rm app alembic upgrade head

- name: Run Tests
  run: |
    docker-compose -f docker-compose.ci.yml run --rm app \
      uv run pytest tests/ --cov=src --cov-report=xml
```

**Automatic Checks:**

- ✅ Migration syntax validation
- ✅ Upgrade path verification
- ✅ Test suite execution with migrated schema
- ✅ Downgrade path verification (optional)

---

## Migration Checklist

Before committing a migration:

- [ ] Reviewed autogenerated SQL
- [ ] Tested upgrade path locally
- [ ] Tested downgrade path
- [ ] Verified timezone-aware datetimes where applicable
- [ ] Run full test suite passes
- [ ] Descriptive migration message
- [ ] Documentation updated if needed
- [ ] Added to git with proper commit message

---

## Related Documentation

- [Docker Setup](docker-setup.md) - Container configuration
- [CI/CD Pipeline](ci-cd.md) - Automated testing
- [Database Models](../../api/models.md) - SQLModel reference
- [Testing Strategy](../testing/strategy.md) - Test infrastructure

---

## References

- **Alembic Official Docs:** https://alembic.sqlalchemy.org/
- **SQLAlchemy Async:** https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **PostgreSQL TIMESTAMPTZ:** https://www.postgresql.org/docs/current/datatype-datetime.html
- **UV Package Manager:** https://docs.astral.sh/uv/

---

**Last Updated:** October 3, 2025  
**Migration Version:** `bce8c437167b` (Initial schema with timezone-aware datetimes)
