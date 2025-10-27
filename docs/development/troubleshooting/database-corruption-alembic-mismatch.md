# Database State Corruption - Alembic Version Mismatch

This document details a critical database state corruption issue where the Alembic migration tracking table (`alembic_version`) existed but all application tables were missing. This mismatch prevented autogenerate from working and required manual intervention to restore database integrity.

The root cause was Docker volume state corruption during a daemon crash, combined with the destructive nature of `make clean` command which deletes persistent volumes without warning. The solution involved resetting Alembic state to match the actual database schema and implementing safety prompts to prevent future data loss.

---

## Initial Problem

### Symptoms

**Environment:** Development (Docker Compose dev environment)

```bash
# Attempting to autogenerate migration for new table
docker compose exec app uv run alembic revision --autogenerate -m "add_rate_limit_audit_logs_table"

# Output showed ALL tables being detected as "new" (not just the one new table)
INFO  [alembic.autogenerate.compare] Detected added table 'users'
INFO  [alembic.autogenerate.compare] Detected added table 'providers'
INFO  [alembic.autogenerate.compare] Detected added table 'rate_limit_audit_logs'
# ... all tables listed as new
```

**Working Environments:** Test environment (fresh migrations ran on startup)

### Expected Behavior

Alembic autogenerate should detect only the new `rate_limit_audit_logs` table since all other tables already exist from previous migrations.

### Actual Behavior

Alembic autogenerate detected ALL tables as new, attempting to create the entire schema from scratch. This indicated Alembic's metadata was completely out of sync with the actual database state.

### Impact

- **Severity:** High
- **Affected Components:** Database migrations, rate limiting Phase 4 implementation, development workflow
- **User Impact:** Development completely blocked - unable to create new migrations or proceed with Phase 4 work

## Investigation Steps

### Step 1: Check Alembic Current State

**Hypothesis:** Alembic might not be tracking the database properly

**Investigation:**

```bash
docker compose -f compose/docker-compose.dev.yml exec app uv run alembic current -v
```

**Findings:**

```text
Current revision(s) for postgresql+asyncpg://...
Rev: e18e20278eaa (head)
Parent: bce8c437167b
Path: /app/alembic/versions/20251004_1825-e18e20278eaa_add_jwt_authentication_support.py
```

Alembic reported being at the latest migration (`e18e20278eaa`).

**Result:** 🔍 Partial insight - Alembic thinks migrations are applied

### Step 2: Check Actual Database Tables

**Hypothesis:** Database might be missing tables despite Alembic's belief

**Investigation:**

```bash
docker compose -f compose/docker-compose.dev.yml exec postgres \
  psql -U dashtam_user -d dashtam -c "\dt"
```

**Findings:**

```text
                List of relations
 Schema |      Name       | Type  |    Owner     
--------+-----------------+-------+--------------
 public | alembic_version | table | dashtam_user
(1 row)
```

Only `alembic_version` table existed - ALL application tables missing!

**Result:** ✅ Issue found - Database is empty but Alembic thinks it's migrated

### Step 3: Check alembic_version Table Content

**Hypothesis:** Version table might contain stale data

**Investigation:**

```bash
docker compose -f compose/docker-compose.dev.yml exec postgres \
  psql -U dashtam_user -d dashtam -c "SELECT * FROM alembic_version;"
```

**Findings:**

```text
 version_num  
--------------
 e18e20278eaa
(1 row)
```

The `alembic_version` table claimed migrations were applied to version `e18e20278eaa`, but no actual tables existed.

**Result:** ✅ Issue confirmed - Complete state mismatch

### Step 4: Check Docker Volumes

**Hypothesis:** Docker volume might be corrupted or incorrectly mounted

**Investigation:**

```bash
docker volume ls --filter name=dashtam
```

**Findings:**

```text
DRIVER    VOLUME NAME
local     dashtam-dev_postgres_dev_data
local     dashtam-dev_redis_dev_data
local     dashtam_postgres_data          # Old volume
local     dashtam_postgres_dev_data      # Old volume
local     dashtam_redis_data             # Old volume
local     dashtam_redis_dev_data         # Old volume
```

Multiple volumes existed, suggesting previous cleanup didn't fully remove old volumes or volume corruption occurred.

**Result:** ✅ Root cause identified - Volume state corruption

## Root Cause Analysis

### Primary Cause

**Problem:**

Docker volume state corruption occurred during a previous Docker daemon crash. When `docker kill` commands were used to forcibly terminate the daemon, the PostgreSQL volume was left in an inconsistent state where:

1. The `alembic_version` table existed (from initial Alembic setup)
2. All application tables were missing (partial volume wipe or remount to different database instance)

This created a "zombie state" where Alembic tracking indicated migrations were applied, but the actual schema didn't exist.

**Why This Happens:**

```bash
# When Docker daemon crashes or is forcibly killed:
# 1. Volume metadata may persist
# 2. Volume data may be partially lost
# 3. Containers may remount to different volume instances
# 4. Result: alembic_version survives but application tables don't
```

Docker volumes should be atomic (all-or-nothing), but daemon crashes can violate this guarantee. The `alembic_version` table is created very early by Alembic's initialization, so it may survive while later migrations' tables are lost.

**Impact:**

- Alembic autogenerate compared models against database and thought ALL tables were new
- Unable to create migrations for individual table additions
- Development workflow completely blocked
- Manual intervention required to restore consistency

### Contributing Factors

#### Factor 1: No Safety Prompts on Destructive Commands

The `make clean` command in Makefile line 293 used the `-v` flag to delete all volumes:

```makefile
clean:
    docker compose down -v --remove-orphans
```

This destructive operation had no warning prompt, making accidental data deletion easy.

#### Factor 2: Docker Daemon Instability

Previous session had Docker daemon issues requiring forceful termination (`docker kill` commands), which can cause volume corruption and inconsistent states.

#### Factor 3: Multiple Stale Volumes

Old volume naming schemes (`dashtam_postgres_data`) coexisted with new naming schemes (`dashtam-dev_postgres_dev_data`), suggesting incomplete cleanup from previous setups.

## Solution Implementation

### Approach

The solution involved two main components:

1. **Immediate Fix:** Reset Alembic state to match actual database (empty), then re-run all migrations
2. **Preventive Measure:** Add prominent safety warning to `make clean` command to prevent future accidental data loss

### Changes Made

#### Change 1: Reset Alembic State

**Before:**

```text
# Alembic thought database was at e18e20278eaa
# Database actually only had alembic_version table
```

**After:**

```bash
# Told Alembic database is actually empty
docker compose exec app uv run alembic stamp base

# Re-ran all migrations from scratch
docker compose exec app uv run alembic upgrade head
```

**Rationale:**

The `stamp base` command resets Alembic's tracking to "no migrations applied" without attempting to run downgrade migrations (which would fail on non-existent tables). This brought Alembic's metadata into sync with reality, allowing migrations to be applied cleanly.

#### Change 2: Add Destructive Warning to `make clean`

**Before:**

```makefile
clean:
    @echo "🧹 Cleaning up ALL environments..."
    @docker compose down -v --remove-orphans
    # ... immediate deletion
```

**After:**

```makefile
clean:
    @echo "⚠️  ⚠️  ⚠️  DESTRUCTIVE OPERATION WARNING ⚠️  ⚠️  ⚠️"
    @echo ""
    @echo "This will PERMANENTLY DELETE all database data and volumes!"
    @echo ""
    @echo "📦 Affected Docker Volumes:"
    @echo "   • dashtam-dev_postgres_dev_data (development database)"
    @echo "   • dashtam-dev_redis_dev_data (development cache)"
    # ... detailed warning
    @read -p "⚠️  Type 'DELETE ALL DATA' to confirm (case-sensitive): " confirm; \
    if [ "$$confirm" != "DELETE ALL DATA" ]; then \
        echo "❌ Cleanup cancelled - No data deleted"; \
        exit 1; \
    fi
    # ... then proceed with deletion
```

**Rationale:**

Explicit confirmation requirement with case-sensitive phrase prevents accidental data deletion while still allowing intentional cleanup when needed. Detailed warning lists all affected volumes and recovery steps.

### Implementation Steps

1. **Step 1**: Reset Alembic to base state

   ```bash
   docker compose -f compose/docker-compose.dev.yml exec app \
     uv run alembic stamp base
   ```

   **Output:**

   ```text
   INFO  [alembic.runtime.migration] Running stamp_revision e18e20278eaa -> 
   ```

2. **Step 2**: Verify Alembic now shows no current version

   ```bash
   docker compose -f compose/docker-compose.dev.yml exec app \
     uv run alembic current
   ```

   **Output:** (Empty - no current version)

3. **Step 3**: Run all migrations from beginning

   ```bash
   docker compose -f compose/docker-compose.dev.yml exec app \
     uv run alembic upgrade head
   ```

   **Output:**

   ```text
   INFO  [alembic.runtime.migration] Running upgrade  -> bce8c437167b, Initial database schema
   INFO  [alembic.runtime.migration] Running upgrade bce8c437167b -> e18e20278eaa, add_jwt_authentication_support
   ```

4. **Step 4**: Verify all tables now exist

   ```bash
   docker compose -f compose/docker-compose.dev.yml exec postgres \
     psql -U dashtam_user -d dashtam -c "\dt"
   ```

   **Output:**

   ```text
   # All 9 tables now present:
   users, providers, provider_connections, provider_tokens, provider_audit_logs,
   refresh_tokens, email_verification_tokens, password_reset_tokens, alembic_version
   ```

5. **Step 5**: Test autogenerate with new table

   ```bash
   docker compose -f compose/docker-compose.dev.yml exec app \
     uv run alembic revision --autogenerate -m "add_rate_limit_audit_logs_table"
   ```

   **Output:**

   ```text
   INFO  [alembic.autogenerate.compare] Detected added table 'rate_limit_audit_logs'
   INFO  [alembic.autogenerate.compare] Detected added index 'ix_rate_limit_audit_logs_endpoint'
   # ... only the new table detected (SUCCESS!)
   ```

6. **Step 6**: Update Makefile with safety prompt

   Modified lines 289-342 of Makefile to add comprehensive warning before destructive cleanup.

## Verification

### Test Results

**Before Fix:**

```bash
# Autogenerate detected ALL tables as new (incorrect)
docker compose exec app uv run alembic revision --autogenerate -m "test"

# Output:
INFO  Detected added table 'users'
INFO  Detected added table 'providers'
INFO  Detected added table 'rate_limit_audit_logs'
# ... all tables (WRONG)
```

**After Fix:**

```bash
# Autogenerate detected ONLY new table (correct)
docker compose exec app uv run alembic revision --autogenerate -m "add_rate_limit_audit_logs_table"

# Output:
INFO  Detected added table 'rate_limit_audit_logs'
INFO  Detected added index 'ix_rate_limit_audit_logs_endpoint'
# ... only new table (CORRECT)
```

### Verification Steps

1. **Test in original failing environment**

   ```bash
   # Applied migration successfully
   docker compose exec app uv run alembic upgrade head
   
   # Verified table exists
   docker compose exec postgres psql -U dashtam_user -d dashtam -c "\dt rate_limit_audit_logs"
   ```

   **Result:** ✅ Passing - Table created with all indexes

2. **Test make clean safety prompt**

   ```bash
   make clean
   
   # Attempted cancellation
   # Prompt: Type 'DELETE ALL DATA' to confirm: [typed "no"]
   # Output: ❌ Cleanup cancelled - No data deleted
   ```

   **Result:** ✅ Passing - Data deletion prevented

3. **Test make clean confirmation**

   ```bash
   make clean
   
   # Confirmed deletion
   # Prompt: Type 'DELETE ALL DATA' to confirm: DELETE ALL DATA
   # Output: ✅ Cleanup complete! All data and volumes deleted.
   ```

   **Result:** ✅ Passing - Volumes deleted only after explicit confirmation

### Regression Testing

Verified that test environment still auto-runs migrations on startup:

```bash
make test-clean
make test-up

# Container logs showed:
# "Initializing test database with Alembic migrations..."
# "Running upgrade  -> bce8c437167b"
# "Running upgrade bce8c437167b -> e18e20278eaa"
# "Test environment ready."
```

No regression - test environment remains self-healing.

## Lessons Learned

### Technical Insights

1. **Alembic Version Table is Created Early**

   The `alembic_version` table is created during Alembic's first initialization, separate from actual migration operations. This means it can survive volume corruption while application tables are lost, creating dangerous state mismatches.

2. **Docker Volume Corruption is Real**

   Docker volumes are not immune to corruption during daemon crashes or forceful terminations. The assumption that "volumes persist everything" is only true for graceful shutdowns.

3. **`alembic stamp` is the Correct Recovery Tool**

   When Alembic metadata is out of sync with database reality, `alembic stamp` safely updates tracking without attempting to run migrations. This is preferable to `alembic downgrade` which would fail on non-existent tables.

### Process Improvements

1. **Always Add Safety Prompts to Destructive Commands**

   Any command that deletes persistent data (especially using `-v` flag) must have:
   - Clear warning about data loss
   - List of affected volumes
   - Explicit confirmation requirement (not just y/N)
   - Recovery steps in output

2. **Distinguish Between Ephemeral and Persistent Environments**

   Test environments should use ephemeral storage (tmpfs) and auto-rebuild, while development environments should use persistent volumes with protection. The distinction should be obvious in command naming (`test-clean` vs `clean`).

3. **Document Volume Architecture**

   Project documentation should clearly explain:
   - Which volumes are persistent vs ephemeral
   - Which commands affect volumes
   - How to recover from volume corruption

### Best Practices

- Never use `docker compose down -v` without explicit confirmation prompt
- After Docker daemon crashes, verify database state before continuing work
- Use `alembic current -v` to check migration state before autogenerate
- Test autogenerate output before assuming it's correct
- Keep development and test volume naming schemes distinct
- Regularly audit for stale Docker volumes

## Future Improvements

### Short-Term Actions

1. **Add Volume Health Check Command**

   **Timeline:** Next sprint

   **Owner:** Development team

   Create `make check-volumes` command to verify:
   - Correct volumes mounted
   - Database state matches Alembic version
   - No stale volumes present

2. **Document Recovery Procedures**

   **Timeline:** Immediate (this document)

   **Owner:** Development team

   Add recovery steps to troubleshooting guide for common corruption scenarios.

### Long-Term Improvements

1. **Automated Database State Validation**

   Add startup health check that compares Alembic state with actual database schema and fails fast with recovery instructions if mismatch detected.

2. **Volume Backup Strategy**

   Implement automated volume backups before destructive operations:

   ```bash
   # Proposed workflow:
   make backup-dev-db  # Creates timestamped backup
   make clean          # Safe to run after backup
   make restore-dev-db BACKUP=timestamp  # Restore if needed
   ```

### Monitoring & Prevention

Add pre-flight check before autogenerate:

```bash
# Example monitoring command (add to Makefile)
check-migration-state:
    @echo "🔍 Checking Alembic and database state..."
    @docker compose exec app uv run alembic current -v
    @docker compose exec postgres psql -U dashtam_user -d dashtam -c "\dt" | wc -l
    # If table count doesn't match expected, warn user
```

## References

**Related Documentation:**

- [Database Migrations Guide](../infrastructure/database-migrations.md)
- [Docker Setup Guide](../infrastructure/docker-setup.md)
- [Testing Guide](../../testing/testing-guide.md)

**External Resources:**

- [Alembic Documentation - Stamp Command](https://alembic.sqlalchemy.org/en/latest/tutorial.html#stamp) - Official docs on stamp usage
- [Docker Volumes](https://docs.docker.com/storage/volumes/) - Understanding Docker volume persistence

**Related Issues:**

- GitHub Issue - Rate Limiting Phase 4 implementation (blocked by this issue)

---

## Document Information

**Template:** [troubleshooting-template.md](../../templates/troubleshooting-template.md)
**Created:** 2025-10-26
**Last Updated:** 2025-10-26
