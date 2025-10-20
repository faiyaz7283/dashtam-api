# Dashtam Environment Flow Diagrams

Documentation of development, test, and CI/CD environment workflows with detailed state transitions and configuration hierarchies.

---

## Table of Contents

- [Overview](#overview)
  - [Key Features](#key-features)
- [Purpose](#purpose)
- [Components](#components)
  - [Component 1: Development Environment](#component-1-development-environment)
  - [Component 2: Test Environment](#component-2-test-environment)
  - [Component 3: PostgreSQL Database Container](#component-3-postgresql-database-container)
  - [Component 4: Configuration Management](#component-4-configuration-management)
  - [Component 5: Docker Compose Orchestration](#component-5-docker-compose-orchestration)
- [Configuration](#configuration)
  - [Environment Files](#environment-files)
  - [Docker Compose Files](#docker-compose-files)
  - [Configuration Loading Hierarchy](#configuration-loading-hierarchy)
  - [Ports and Services](#ports-and-services)
- [Setup Instructions](#setup-instructions)
  - [Prerequisites](#prerequisites)
  - [Starting Development Environment](#starting-development-environment)
  - [Starting Test Environment](#starting-test-environment)
  - [Switching Between Environments](#switching-between-environments)
- [Operation](#operation)
  - [Development Workflow](#development-workflow)
  - [Test Environment Flow](#test-environment-flow)
  - [Environment Switching](#environment-switching)
  - [Database State Management](#database-state-management)
- [Monitoring](#monitoring)
  - [Container Status](#container-status)
  - [Database Status](#database-status)
  - [Logs](#logs)
- [Troubleshooting](#troubleshooting)
  - [Issue 1: Container Name Conflicts](#issue-1-container-name-conflicts)
  - [Issue 2: Database Connection Errors](#issue-2-database-connection-errors)
  - [Issue 3: Test Data Not Clean](#issue-3-test-data-not-clean)
- [Maintenance](#maintenance)
  - [Best Practices](#best-practices)
  - [Safety Features](#safety-features)
- [Security](#security)
  - [Test Database Safety Checks](#test-database-safety-checks)
  - [Data Isolation](#data-isolation)
- [Performance Optimization](#performance-optimization)
  - [Test Database Optimizations](#test-database-optimizations)
- [References](#references)
  - [Key Takeaways](#key-takeaways)
  - [Related Documentation](#related-documentation)

---

## Overview

Dashtam uses Docker Compose to orchestrate separate development and test environments. Both environments share the same container infrastructure but use different configurations, ensuring complete data isolation while allowing rapid environment switching.

### Key Features

- **Isolated Environments:** Development and test use separate databases within same PostgreSQL container
- **Persistent Dev Data:** Development database survives test runs and environment switches
- **Clean Test State:** Test database dropped and recreated on every test setup
- **Configuration Hierarchy:** Layered configuration with environment-specific overrides
- **Safety Checks:** Multiple validation layers prevent accidental data loss
- **Docker-Native:** All operations run in containers for consistency

## Purpose

The multi-environment workflow exists to solve critical development and testing challenges:

- **Data Isolation:** Keep development data (OAuth tokens, provider configs) completely separate from test data
- **Clean Testing:** Ensure every test run starts with fresh, empty database tables
- **Developer Productivity:** Switch between development and testing without losing work
- **CI/CD Compatibility:** Use same Docker setup locally and in GitHub Actions
- **Safety:** Prevent accidental modification of development data during testing
- **Debugging:** Allow inspection of development state without test interference

---

## Components

### Component 1: Development Environment

**Purpose:** Primary development workflow with persistent database and hot-reload

**Technology:** Docker Compose (docker-compose.yml)

**Services:**

- `dashtam-app` (port 8000) - FastAPI application with hot reload
- `dashtam-callback` (port 8182) - OAuth callback server
- `dashtam-postgres` (port 5432) - PostgreSQL with `dashtam` database
- `dashtam-redis` (port 6379) - Redis cache (index 0)

**Key Characteristics:**

- Database persists across restarts (Docker volume)
- Code changes trigger automatic reload
- Real OAuth tokens and provider connections
- Always uses `.env` file for configuration

### Component 2: Test Environment

**Purpose:** Isolated testing environment with clean database state

**Technology:** Docker Compose (docker-compose.yml + docker-compose.test.yml overlay)

**Services (Overridden):**

- `dashtam-app` - Runs in "sleep" mode, controlled by pytest
- `dashtam-postgres` - Uses `dashtam_test` database (separate from dev)
- `dashtam-redis` - Uses cache index 1 (separate from dev)

**Key Characteristics:**

- Database dropped and recreated on every `make test-setup`
- No persistent data between test runs
- Uses `.env.test` file (mounted as `.env` in container)
- Safety checks prevent running on production databases

### Component 3: PostgreSQL Database Container

**Purpose:** Single PostgreSQL instance hosting both dev and test databases

**Technology:** PostgreSQL 17.6

**Databases:**

1. **`dashtam` (Development)**
   - Owner: `dashtam_user`
   - Persistent data (Docker volume)
   - Real OAuth tokens and configurations

2. **`dashtam_test` (Testing)**
   - Owner: `dashtam_test_user`
   - Ephemeral data (recreated each test run)
   - Mock data only

**Isolation:** Both databases exist simultaneously but are completely isolated - no data sharing.

### Component 4: Configuration Management

**Purpose:** Layered configuration system with environment-specific overrides

**Layers:**

1. **Docker Compose** - Container orchestration and environment variables
2. **Environment Files** - `.env` (dev) or `.env.test` (testing)
3. **Pydantic Settings** - Type-safe config loading in Python
4. **Application Layer** - Final configuration consumed by FastAPI

**Key Files:**

- `docker-compose.yml` - Base configuration
- `docker-compose.test.yml` - Test overrides
- `.env` - Development variables
- `.env.test` - Test variables
- `src/core/config.py` - Settings class
- `tests/test_config.py` - Test settings class

### Component 5: Docker Compose Orchestration

**Purpose:** Manage service lifecycle and configuration overlays

**Commands:**

- `make up` - Start development environment
- `make test-setup` - Stop dev, start test environment, initialize test DB
- `make test-clean` - Stop test environment, restore dev

**Overlay Pattern:**

```yaml
# docker-compose.yml (base)
# + docker-compose.test.yml (overrides)
# = Test configuration
```

---

## Configuration

### Environment Files

**Development: `.env`**

```bash
# Database configuration
POSTGRES_DB=dashtam
POSTGRES_USER=dashtam_user
POSTGRES_PASSWORD=secure_password_change_me

# Application configuration
ENVIRONMENT=development
DEBUG=true
DATABASE_URL=postgresql+asyncpg://dashtam_user:secure_password@postgres:5432/dashtam
```

**Testing: `.env.test`**

```bash
# Test database configuration
TEST_POSTGRES_DB=dashtam_test
TEST_POSTGRES_USER=dashtam_test_user
TEST_POSTGRES_PASSWORD=test_password

# Test environment markers
ENVIRONMENT=testing
TESTING=true
DEBUG=true
DATABASE_URL=postgresql+asyncpg://dashtam_test_user:test_password@postgres:5432/dashtam_test
```

### Docker Compose Files

**Base Configuration: `docker-compose.yml`**

- Defines all services (app, callback, postgres, redis)
- Uses environment variables from `.env`
- Default: Development configuration

**Test Overlay: `docker-compose.test.yml`**

- Extends base configuration
- Overrides environment variables
- Changes app command to "sleep infinity"
- Uses different Redis cache index
- Mounts `.env.test` as `.env` in containers

### Ports and Services

| Service | Dev Port | Test Port | Protocol | Purpose |
|---------|----------|-----------|----------|---------|
| FastAPI App | 8000 | 8001 | HTTPS | Main application (dev/test) |
| OAuth Callback | 8182 | 8183 | HTTPS | OAuth redirect handler |
| PostgreSQL | 5432 | 5433 | TCP | Dev and test databases |
| Redis | 6379 | 6380 | TCP | Cache (dev: index 0, test: index 1) |

**Note:** Test environment reuses same ports but with different internal configuration.

---

## Setup Instructions

### Prerequisites

- [ ] Docker and Docker Compose installed
- [ ] `.env` file exists (development configuration)
- [ ] `.env.test` file exists (test configuration)
- [ ] SSL certificates generated (`make certs` if needed)
- [ ] All source code in `src/` directory

### Starting Development Environment

#### Step 1: Start All Services

```bash
# Start development containers
make up

# Or manually:
docker compose up -d
```

#### Step 2: Verify Services

```bash
# Check all containers running
docker compose ps

# Expected: 4 containers (app, callback, postgres, redis)
```

#### Step 3: Access Application

```bash
# API documentation
open https://localhost:8000/docs

# Health check
curl -k https://localhost:8000/health
```

**Verification:**

```bash
# View logs to confirm successful startup
make dev-logs

# Expected output:
# - "Running Alembic migrations..."
# - "Migrations completed successfully"
# - "Uvicorn running on https://0.0.0.0:8000"
```

### Starting Test Environment

#### Step 1: Setup Test Environment

```bash
# Stop dev, start test, initialize test database
make test-setup
```

**What Happens:**

1. Development containers stop (if running)
2. Test containers start with `.env.test` configuration
3. `init_test_db.py` drops and recreates all test tables
4. Test database is clean and ready

#### Step 2: Run Tests

```bash
# Run all tests
make test

# Or specific test suites:
make test-unit
make test-integration
```

#### Step 3: Clean Up

```bash
# Stop test environment
make test-clean

# Optionally restart development
make up
```

### Switching Between Environments

**From Development to Testing:**

```bash
# Currently in development
make up  # (already running)

# Switch to testing
make test-setup  # Stops dev, starts test
```

**From Testing to Development:**

```bash
# Currently in testing
make test  # (tests running)

# Switch back to development
make test-clean  # Stops test
make up          # Starts dev (data intact!)
```

**Important:** Cannot run both simultaneously - container name conflicts.

---

## Operation

### Development Workflow

## Development Environment Flow

```mermaid
flowchart TD
    Start([make dev-up]) --> Compose
    Compose["Docker Compose reads<br/>compose/docker-compose.dev.yml<br/>env/.env.dev"]
    
    Compose --> ContainerStart[Containers start]
    ContainerStart --> Services
    
    subgraph Services [" "]
        direction TB
        
        subgraph DB [" "]
            DB_Title["dashtam-dev-postgres"]
            DB_Details["DB: dashtam<br/>User: dashtam_user<br/>Port: 5432"]
        end
        
        subgraph Cache [" "]
            Cache_Title["dashtam-dev-redis"]
            Cache_Details["Index: 0<br/>Port: 6379"]
        end
        
        subgraph App [" "]
            App_Title["dashtam-dev-app"]
            App_Port["Port 8000"]
            App_Migrate["Run Alembic migrations"]
            App_Start["Start FastAPI with reload"]
            App_Migrate --> App_Start
        end
        
        subgraph Callback [" "]
            Cb_Title["dashtam-dev-callback"]
            Cb_Port["Port 8182"]
        end
    end
    
    Services --> Ready["Ready at https://localhost:8000"]
    Ready --> End([Development Active])
    
    style DB_Title fill:#e1f5ff
    style Cache_Title fill:#fff4e1
    style App_Title fill:#e8f5e9
    style Cb_Title fill:#f3e5f5
```

---

## Test Environment Flow

```mermaid
flowchart TD
    Start([make test-up]) --> Compose
    Compose["Docker Compose reads<br/>compose/docker-compose.test.yml<br/>env/.env.test"]
    
    Compose --> ContainerStart[Containers start]
    ContainerStart --> Services
    
    subgraph Services [" "]
        direction TB
        
        subgraph DB [" "]
            DB_Title["dashtam-test-postgres"]
            DB_Details["DB: dashtam_test<br/>Port: 5433 to 5432<br/>Storage: tmpfs"]
        end
        
        subgraph Cache [" "]
            Cache_Title["dashtam-test-redis"]
            Cache_Details["Index: 1<br/>Port: 6380 to 6379"]
        end
        
        subgraph App [" "]
            App_Title["dashtam-test-app"]
            App_Port["Port 8001 to 8000"]
            App_Migrate["Run Alembic migrations"]
            App_Wait["Keep container alive"]
            App_Migrate --> App_Wait
        end
        
        subgraph Callback [" "]
            Cb_Title["dashtam-test-callback"]
            Cb_Port["Port 8183 to 8182"]
        end
    end
    
    Services --> Ready["Ready - Clean database"]
    Ready --> RunTests["Run tests"]
    RunTests --> End([Testing Complete])
    
    style DB_Title fill:#e1f5ff
    style Cache_Title fill:#fff4e1
    style App_Title fill:#e8f5e9
    style Cb_Title fill:#f3e5f5
```

---

### Database State Management

## Database State Comparison

```mermaid
graph TB
    subgraph Container ["PostgreSQL Container"]
        direction LR
        
        subgraph DevDB ["Development Database"]
            Dev_Name["dashtam"]
            Dev_Owner["Owner: dashtam_user"]
            Dev_Storage["Volume: postgres_dev_data"]
            Dev_Tables["Tables: users, providers, etc"]
            Dev_Data["Persistent data"]
            Dev_Name --> Dev_Owner
            Dev_Owner --> Dev_Storage
            Dev_Owner --> Dev_Tables
            Dev_Tables --> Dev_Data
        end
        
        subgraph TestDB ["Test Database"]
            Test_Name["dashtam_test"]
            Test_Owner["Owner: dashtam_test_user"]
            Test_Storage["Storage: tmpfs ephemeral"]
            Test_Tables["Tables: users, providers, etc"]
            Test_Data["Clean mock data"]
            Test_Name --> Test_Owner
            Test_Owner --> Test_Storage
            Test_Owner --> Test_Tables
            Test_Tables --> Test_Data
        end
        
        Isolation["ISOLATED - No data sharing"]
        DevDB -.-> Isolation
        Isolation -.-> TestDB
    end
    
    style Dev_Name fill:#e8f5e9
    style Test_Name fill:#fff3e0
    style Isolation fill:#ffebee
```

---

### Environment Switching

## Environment Switching Flow

```mermaid
flowchart TD
    DevUp([make dev-up]) --> DevActive[Development Active]
    TestUp([make test-up]) --> TestActive[Testing Active]
    
    DevActive -.-> Parallel[Both can run in parallel]
    Parallel -.-> TestActive
    
    DevDown([make dev-down]) --> DevStopped[Development Stopped]
    TestDown([make test-down]) --> TestStopped[Testing Stopped]
    
    ParallelNote["Parallel support:<br/>- Distinct names<br/>- Isolated networks<br/>- Different ports"]
    Parallel --> ParallelNote
```

### Configuration Loading Hierarchy

```mermaid
flowchart TD
    subgraph Dev ["Development"]
        Dev_Compose["docker-compose.dev.yml"]
        Dev_Env["env/.env.dev"]
        Dev_Settings["Pydantic Settings"]
        Dev_App["Application"]
        
        Dev_Compose -->|env_file| Dev_Env
        Dev_Env --> Dev_Settings
        Dev_Settings --> Dev_App
    end
    
    subgraph Test ["Testing"]
        Test_Compose["docker-compose.test.yml"]
        Test_Env["env/.env.test"]
        Test_Settings["Pydantic Settings"]
        Test_App["Application"]
        
        Test_Compose -->|env_file| Test_Env
        Test_Env --> Test_Settings
        Test_Settings --> Test_App
    end
    
    Note["No .env volume mounts<br/>Docker Compose loads env files"]
    Dev --> Note
```

---

## Monitoring

### Container Status

**Check All Containers:**

```bash
# Development environment
docker compose ps

# Test environment
docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.test ps
```

**Expected Output (Development):**

```text
NAME                  STATUS    PORTS
dashtam-app           Up        0.0.0.0:8000->8000/tcp
dashtam-callback      Up        0.0.0.0:8182->8182/tcp
dashtam-postgres      Up        0.0.0.0:5432->5432/tcp
dashtam-redis         Up        0.0.0.0:6379->6379/tcp
```

### Database Status

**Check Databases Exist:**

```bash
# List all databases in PostgreSQL container
docker compose exec postgres psql -U dashtam_user -l

# Expected: Both dashtam and dashtam_test listed
```

**Check Active Connections:**

```bash
# View active database connections
docker compose exec postgres psql -U dashtam_user -d dashtam -c "
  SELECT datname, count(*) 
  FROM pg_stat_activity 
  WHERE datname IN ('dashtam', 'dashtam_test') 
  GROUP BY datname;
"
```

### Logs

**Development Logs:**

```bash
# All services
make dev-logs

# Specific service
docker compose logs -f app
docker compose logs -f postgres
```

**Test Logs:**

```bash
# During test execution
docker compose -f docker-compose.yml -f docker-compose.test.yml logs -f app
```

**Key Log Indicators:**

- **Success:** "Migrations completed successfully", "Uvicorn running on..."
- **Database Ready:** "database system is ready to accept connections"
- **Test DB Initialized:** "Test database initialized successfully"

---

## Troubleshooting

### Issue 1: Container Name Conflicts

**Symptoms:**

- Error: "Container name 'dashtam-app' already in use"
- Cannot start second environment while first is running

**Diagnosis:**

```bash
# Check running containers
docker ps -a --filter name=dashtam
```

**Solution:**

```bash
# Stop conflicting environment first
make dev-down  # or make test-clean

# Then start desired environment
make up  # or make test-setup
```

**Prevention:** Always stop one environment before starting the other.

### Issue 2: Database Connection Errors

**Symptoms:**

- "Connection refused" errors
- "Database 'dashtam_test' does not exist"
- Tests fail with database errors

**Diagnosis:**

```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check database exists
docker compose exec postgres psql -U dashtam_user -l | grep dashtam
```

**Solution:**

```bash
# For test environment, reinitialize
make test-setup  # Recreates test database

# For development, check .env file
cat .env | grep DATABASE_URL

# Restart if needed
make dev-down && make dev-up
```

### Issue 3: Test Data Not Clean

**Symptoms:**

- Tests fail due to existing data
- "Unique constraint violation" errors
- Inconsistent test results

**Diagnosis:**

```bash
# Check if test tables have data
docker compose exec postgres psql -U dashtam_test_user -d dashtam_test -c "
  SELECT schemaname, tablename, n_tup_ins 
  FROM pg_stat_user_tables;
"
```

**Solution:**

```bash
# Reinitialize test database (drops all data)
make test-setup

# Or manually:
docker compose exec app uv run python src/core/init_test_db.py
```

**Cause:** Test setup not run before tests, or `init_test_db.py` failed silently.

---

## Maintenance

### Best Practices

1. **Always run `make test-setup` before testing**
   - Ensures clean database state
   - Prevents test interference
   - Validates safety checks

2. **Use `make test-clean` when done testing**
   - Frees up resources
   - Allows quick return to development
   - Prevents accidental test database usage

3. **Don't manually connect to test database**
   - Let scripts handle initialization
   - Maintains safety checks
   - Prevents accidental data corruption

4. **Dev database persists**
   - OAuth tokens survive test runs
   - Provider configurations intact
   - No need to re-authenticate after testing

### Safety Features

**Critical Safety Checks in `init_test_db.py`:**

1. **Environment Validation:**
   - Checks `ENVIRONMENT == "testing"`
   - Prevents running on production
   - Triple validation (environment, database URL, TESTING flag)

2. **Database Name Validation:**
   - Database URL must contain "test"
   - Prevents accidental dev database wipe
   - Logged and verified before operations

3. **Table Drop Protection:**
   - Only runs after all checks pass
   - Requires explicit TESTING=true flag
   - Logs all operations for audit trail

---

## Security

### Test Database Safety Checks

**Multi-Layer Validation:**

```python
# src/core/init_test_db.py

# Layer 1: Environment variable check
if settings.ENVIRONMENT != "testing":
    raise ValueError("This script must only run in testing environment")

# Layer 2: Database URL validation
if "test" not in settings.DATABASE_URL:
    raise ValueError("Database URL must contain 'test'")

# Layer 3: Explicit testing flag
if not settings.TESTING:
    raise ValueError("TESTING flag must be True")
```

**Why Three Layers?**

- **Defense in Depth:** Multiple checks prevent accidental production use
- **Explicit Intent:** Requires deliberate configuration to enable
- **Fail-Safe:** Any check failing stops execution immediately

### Data Isolation

**Complete Database Separation:**

- Development: `dashtam` database, `dashtam_user` owner
- Testing: `dashtam_test` database, `dashtam_test_user` owner
- No shared tables, no shared users, no shared data
- PostgreSQL enforces isolation at database level

**Redis Cache Separation:**

- Development: Redis index 0
- Testing: Redis index 1
- Different namespaces prevent cache collisions

**Configuration Isolation:**

- Development: `.env` file
- Testing: `.env.test` file (mounted as `.env` in container)
- Pydantic Settings classes enforce type safety

---

## Performance Optimization

### Test Database Optimizations

**Applied Automatically by `init_test_db.py`:**

```sql
-- Disable synchronous commits (faster writes, acceptable for tests)
SET synchronous_commit = OFF;

-- Disable fsync (bypass disk writes, ephemeral data)
SET fsync = OFF;

-- Disable full page writes (not needed for test data)
SET full_page_writes = OFF;
```

**Impact:**

- **3-5x faster test execution** for database-heavy tests
- **No durability impact** (test data is ephemeral)
- **Safe for testing** (data discarded after each run)

**Not Applied to Development:**

- Development database uses standard PostgreSQL settings
- Full durability for real OAuth tokens and provider configs
- Matches production behavior

---

## References

### Key Takeaways

**✅ What You Need to Remember:**

1. **Dev and test use the SAME containers** but with different configurations
2. **Dev data is NEVER lost** when running tests (different database)
3. **Test data is ALWAYS fresh** (dropped and recreated each time)
4. **You cannot run dev and test simultaneously** (container name conflicts)
5. **Switching is easy:** `make test-clean` → `make up`

**⚠️ Critical Safety Features:**

1. **init_test_db.py has safety checks** - won't run on production
2. **Test database name must contain "test"** - verified before operations
3. **ENVIRONMENT must be "testing"** - double-checked
4. **Tables are dropped first** - ensures clean state every time

**🎯 Best Practices:**

1. **Always run `make test-setup` first** before running tests
2. **Use `make test-clean`** when done testing
3. **Don't manually connect to test database** - let scripts handle it
4. **Dev database persists** - your OAuth tokens and test data are safe

### Related Documentation

- [Docker Setup](docker-setup.md) - Container configuration details
- [Database Migrations](database-migrations.md) - Alembic migration system
- [CI/CD Pipeline](ci-cd.md) - GitHub Actions integration
- [Testing Strategy](../testing/strategy.md) - Test infrastructure overview

---

## Document Information

**Template:** [infrastructure-template.md](../../templates/infrastructure-template.md)
**Created:** YYYY-MM-DD
**Last Updated:** 2025-10-17
