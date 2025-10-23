# Dashtam Application Architecture Guide

Comprehensive guide to Dashtam's dual-environment architecture, explaining how development and testing environments coexist with complete isolation while sharing Docker containers efficiently.

## Overview

Dashtam uses a **dual-environment architecture** with complete isolation between development and testing. Both environments run in Docker containers with different configurations, enabling safe concurrent development and testing workflows.

### Key Architecture Principles

1. **Complete Environment Isolation** - Development and testing use separate databases, users, and configurations
2. **Docker-First Approach** - All environments run in containers for consistency and reproducibility
3. **Configuration Overlay Pattern** - Base configuration with environment-specific overrides
4. **Idempotent Initialization** - Database setup scripts safe to run multiple times
5. **Clean Test State** - Test environment always starts with fresh data

## Context

Dashtam's application architecture operates within a containerized development ecosystem, balancing developer productivity with testing reliability.

**Operating Environment:**

- **Platform**: Docker containers on local development machines
- **Database**: PostgreSQL 17.6 with async drivers (asyncpg)
- **Cache**: Redis 8.2.1 for session and temporary data
- **Web Framework**: FastAPI with async/await patterns
- **Package Management**: UV 0.8.22 for deterministic dependency resolution

**System Constraints:**

- **Local Development**: All services must run on developer machines without external dependencies
- **Resource Efficiency**: Minimize Docker overhead for fast iteration cycles
- **Test Isolation**: Tests must not interfere with development data
- **Reproducibility**: Same environment behavior across all developer machines
- **SSL Everywhere**: HTTPS required even in development for production parity

**Key Requirements:**

1. **Environment Isolation**: Development and testing must not share state
2. **Data Persistence**: Development data must survive container restarts
3. **Clean Test State**: Each test run starts with fresh database
4. **Easy Switching**: Seamless transitions between development and testing
5. **Minimal Complexity**: Simple commands for common workflows

## Architecture Goals

1. **Complete Isolation** - Separate databases, users, and configurations prevent cross-contamination between environments
2. **Developer Productivity** - Hot reload, persistent data, and simple commands minimize friction
3. **Test Reliability** - Clean state for each test run ensures predictable, repeatable results
4. **Production Parity** - Docker containers match production environment closely
5. **Operational Simplicity** - Make-based commands abstract Docker complexity
6. **Resource Efficiency** - Share containers where safe, minimize duplication
7. **Debugging Support** - Easy access to logs, databases, and running processes
8. **Flexibility** - Support both isolated and overlapping environment workflows

## Design Decisions

### Decision 1: Dual-Environment Architecture with Shared Containers

**Rationale**: Instead of completely separate container sets, use Docker Compose overlay pattern to share infrastructure while isolating data.

**Trade-offs**:

- ✅ **Pro**: Reduced resource usage (one PostgreSQL instance, not two)
- ✅ **Pro**: Faster startup times (reuse running containers when possible)
- ✅ **Pro**: Simpler Docker network configuration
- ❌ **Con**: Cannot run dev and test truly simultaneously (container name conflicts)
- ❌ **Con**: More complex configuration management

**Alternatives Considered**:

- Completely separate containers with different names → Rejected due to resource overhead
- Single shared environment → Rejected due to data pollution concerns

### Decision 2: Idempotent Database Initialization

**Rationale**: Development database initialization runs automatically on startup, test initialization runs on-demand with clean slate.

**Trade-offs**:

- ✅ **Pro**: Development "just works" without manual setup
- ✅ **Pro**: Tests always start clean (predictable state)
- ✅ **Pro**: Safe to re-run initialization scripts
- ❌ **Con**: Slight startup delay for development environment
- ❌ **Con**: Test data lost on each test run (by design)

**Implementation**: `init_db.py` for dev (creates if missing), `init_test_db.py` for tests (drops and recreates).

### Decision 3: Configuration Overlay Pattern

**Rationale**: Use `docker-compose.yml` as base with `docker-compose.test.yml` overlay for test-specific overrides.

**Trade-offs**:

- ✅ **Pro**: DRY principle - shared config in base file
- ✅ **Pro**: Easy to understand differences (test overlay shows only changes)
- ✅ **Pro**: Prevents configuration drift
- ❌ **Con**: Requires understanding Docker Compose override mechanics

**Key Overrides**: App command (`sleep infinity`), environment variables (`.env.test`), database credentials.

## Components

### Development Environment

**Purpose:** Active development, debugging, and manual testing

**Containers:**

- `dashtam-app` (port 8000) - FastAPI application
- `dashtam-callback` (port 8182) - OAuth callback server
- `dashtam-postgres` - PostgreSQL database
- `dashtam-redis` - Redis cache

**Configuration:**

- Uses `.env` file
- Database: `dashtam` with user `dashtam_user`
- Auto-runs `init_db.py` on startup
- Hot reload enabled (code changes auto-restart)
- HTTPS with self-signed certs

**Startup Command:** `make up`

### Test Environment

**Purpose:** Automated testing with isolated data

**Containers** (overlays dev):

- Same container names but with test config overlay
- `dashtam-app` runs `sleep infinity` (no auto-start)
- `dashtam-postgres` with test database
- `dashtam-redis` (different database index)

**Configuration:**

- Uses `.env.test` (mounted as `.env`)
- Database: `dashtam_test` with user `dashtam_test_user`
- Runs `init_test_db.py` on demand
- No SSL/auto-reload
- Clean database state for each test run

**Startup Command:** `make test-setup`

## Implementation Details

### Environment Coexistence

#### How Environments Interact

**Key Point:** The environments **share the same Docker containers** but with different configurations!

When you run tests:

```bash
make test-setup  # or make test-unit
```

**What happens:**

1. Docker Compose uses file overlays:

   ```bash
   docker-compose --env-file .env.test \
     -f docker-compose.yml \
     -f docker-compose.test.yml \
     up -d postgres redis app
   ```

2. **PostgreSQL container:**
   - Still running the same instance
   - Now has BOTH databases: `dashtam` AND `dashtam_test`
   - Has BOTH users: `dashtam_user` AND `dashtam_test_user`
   - Dev data remains untouched in `dashtam` database
   - Test data is isolated in `dashtam_test` database

3. **App container:**
   - Gets restarted with test configuration
   - `.env.test` mounted as `.env`
   - Environment variables overridden (DATABASE_URL, ENVIRONMENT)
   - Command changed to `sleep infinity` (doesn't auto-start the app)

4. **Dev environment:**
   - Dev containers stop when test containers start
   - Dev database data persists in volumes
   - Can be restarted with `make up` after testing

### Database Initialization Flows

#### Development Database Initialization

**File:** `src/core/init_db.py`

**When it runs:** Automatically on app container startup

**Process:**

```text
1. Container starts
2. Command: "uv run python src/core/init_db.py && uv run uvicorn..."
3. init_db.py executes:
   ├── Load settings from .env
   ├── Create AsyncEngine (DATABASE_URL)
   ├── Connect to database
   ├── Import all models (User, Provider, etc.)
   ├── Run SQLModel.metadata.create_all()
   │   ├── Creates table: users
   │   ├── Creates table: providers
   │   ├── Creates table: provider_connections
   │   ├── Creates table: provider_tokens
   │   └── Creates table: provider_audit_logs
   ├── Enable UUID extension
   └── Log success
4. App starts (uvicorn)
```

**Key Points:**

- Idempotent (safe to run multiple times)
- Only creates tables, no seed data
- Runs in DEBUG mode (from .env)
- Logs all SQL queries if DB_ECHO=true

#### Test Database Initialization

**File:** `src/core/init_test_db.py`

**When it runs:** On-demand via `make test-setup`

**Process:**

```text
1. make test-setup called
2. Start postgres/redis containers with test config
3. PostgreSQL init script runs (docker/init-test-db.sh):
   ├── Check if POSTGRES_DB == dashtam_test (test mode)
   ├── Create user: dashtam_test_user
   ├── Grant permissions
   └── Enable UUID extension
4. Start app container with sleep infinity
5. Execute: docker-compose exec app uv run python src/core/init_test_db.py
6. init_test_db.py executes:
   ├── Load TestSettings from .env (actually .env.test)
   ├── SAFETY CHECK: Verify test environment
   │   └── Must have: ENVIRONMENT=testing + DATABASE_URL with "test"
   ├── Create AsyncEngine (test_database_url)
   ├── Connect and verify database name contains "test"
   ├── Apply test optimizations (synchronous_commit=OFF, etc.)
   ├── Import all models
   ├── DROP all existing tables (clean slate)
   ├── CREATE all tables fresh
   ├── Verify all 5 expected tables exist
   └── Log success
```

**Key Points:**

- **Always drops tables first** (clean state)
- Has safety checks to prevent running on prod database
- Optimized for speed (no fsync, no synchronous commits)
- Only runs when explicitly called
- Container stays running for tests

### Model Import System

Both initialization scripts must import all models BEFORE calling `SQLModel.metadata.create_all()`. This is because SQLModel uses a metadata registry.

**Why this matters:**

```python
# ❌ WRONG - Tables won't be created
from sqlmodel import SQLModel
SQLModel.metadata.create_all()  # Empty! No models registered

# ✅ CORRECT - Models register themselves with metadata
from src.models.user import User
from src.models.provider import Provider, ProviderConnection, ProviderToken
from sqlmodel import SQLModel
SQLModel.metadata.create_all()  # Now creates all tables!
```

**Model Registration:**

- Each model class that inherits from `SQLModel` auto-registers with `SQLModel.metadata`
- The `table=True` parameter marks it as a database table
- Relationships are established via foreign keys

### Configuration Management

### Settings Hierarchy

**Development:**

```text
Environment Variables (docker-compose.yml)
    ↓
.env file
    ↓
Settings class defaults (src/core/config.py)
    ↓
Final Settings object
```

**Testing:**

```text
Environment Variables (docker-compose.test.yml override)
    ↓
.env.test file (mounted as .env)
    ↓
TestSettings class defaults (tests/test_config.py)
    ↓
Final TestSettings object
```

### Key Configuration Files

**`.env`** (Development):

- DATABASE_URL: `postgresql+asyncpg://dashtam_user:...@postgres:5432/dashtam`
- ENVIRONMENT: `development`
- DEBUG: `true`
- Schwab API credentials

**`.env.test`** (Testing):

- DATABASE_URL: `postgresql+asyncpg://dashtam_test_user:...@postgres:5432/dashtam_test`
- ENVIRONMENT: `testing`
- TESTING: `true`
- Mock provider credentials

**`docker-compose.yml`** (Base):

- Defines all services
- Uses variables from `.env`
- Sets up networks and volumes

**`docker-compose.test.yml`** (Override):

- Overrides app command to `sleep infinity`
- Overrides database credentials
- Mounts .env.test as .env
- No persistent volumes for postgres

### Typical Workflows

### Development Workflow

```bash
# Initial setup
make setup          # Generate certs and keys
make build          # Build Docker images

# Start development
make up             # Start all containers
                    # → init_db.py runs automatically
                    # → App available at https://localhost:8000

# Development
# ... edit code ...
                    # → Auto-reload detects changes
                    # → App restarts automatically

make logs           # View logs
make status         # Check containers

# Stop development
make down           # Stop containers (data persists)
```

### Testing Workflow

```bash
# From clean state OR with dev running

# Run all tests
make test-setup     # Initialize test environment
                    # → Stops dev containers
                    # → Starts test containers
                    # → Creates test database
                    # → Runs init_test_db.py

make test-unit      # Run unit tests
                    # → Executes pytest inside container
                    # → Uses test database

# Clean up tests
make test-clean     # Remove test containers and data

# Resume development
make up             # Restart dev containers
                    # → Dev data still intact
```

### Simultaneous Dev and Test (Advanced)

You **cannot** run dev and test simultaneously with current setup because they share container names. However, you can:

1. Run tests in one terminal
2. Switch back to dev without losing data:

```bash
# Terminal 1
make test           # Tests running...

# Terminal 2 (after tests complete)
make test-clean     # Clean test environment
make up             # Resume development
```

### Database State Management

#### Development Database State

**Location:** Docker volume `dashtam_postgres_data`

**Persistence:**

- Survives container restarts
- Survives `make down`
- Lost with `make clean`

**Tables:**

- users
- providers
- provider_connections
- provider_tokens
- provider_audit_logs

**When to reset:**

```bash
make clean          # Remove all data and containers
make build          # Rebuild
make up             # Fresh start
```

#### Test Database State

**Location:** Same PostgreSQL instance, different database

**Persistence:**

- **Intentionally destroyed** on each `make test-setup`
- `init_test_db.py` drops all tables
- Always starts with clean slate

**Why this matters:**

- Tests are isolated from each other
- No test data pollution
- Predictable test environment

### Troubleshooting

#### Issue: Tests fail with "database does not exist"

**Solution:** Run `make test-setup` first to initialize test database

#### Issue: Dev database lost after testing

**Solution:** Dev database is in a different database (`dashtam` vs `dashtam_test`). Use `make up` to restart dev environment.

#### Issue: Environment variables not loading in tests

**Solution:** Ensure `docker-compose.test.yml` properly overrides and `.env.test` is mounted as `.env`

#### Issue: Tables not created in test database

**Solution:** Verify all models are imported in `init_test_db.py` before `create_all()`

#### Issue: Can't run dev and tests simultaneously

**Solution:** By design. Use `make test-clean` then `make up` to switch back to dev.

## Security Considerations

### Environment Isolation

- **Separate Credentials**: Development and test environments use different database users and passwords
- **No Shared State**: Complete isolation prevents test data leaking into development
- **SSL in Development**: HTTPS enforced even in local dev for production parity

### Configuration Security

- **Environment Variables**: Sensitive credentials stored in `.env` files (gitignored)
- **No Hardcoded Secrets**: All secrets loaded from environment, never committed to code
- **Test Credentials**: Test environment uses mock/test credentials, not real API keys

### Database Security

- **Principle of Least Privilege**: Each environment user has only necessary permissions
- **Test Safety Checks**: `init_test_db.py` verifies test environment before dropping tables
- **Volume Isolation**: Test database uses non-persistent volumes, dev uses persistent volumes

## Performance Considerations

### Docker Overhead

- **Shared Containers**: Development and test share same PostgreSQL instance to reduce resource usage
- **Hot Reload**: Development container uses volume mounts for instant code reload without rebuild
- **Layer Caching**: Docker builds leverage layer caching for fast image rebuilds

### Database Performance

- **Development**: Full ACID compliance with fsync enabled for data safety
- **Testing**: Optimized for speed with `synchronous_commit=OFF` and reduced durability
- **Connection Pooling**: SQLAlchemy async engine with connection pooling for efficiency

### Optimization Strategies

- **Selective Container Startup**: Only start containers needed for current task
- **Volume Reuse**: Development data persists in volumes, avoiding re-initialization
- **Parallel Execution**: Test database optimizations enable faster test suite execution

## Testing Strategy

### How This Architecture Enables Testing

- **Clean State**: Test database drops all tables before each run, ensuring predictable starting state
- **Isolated Data**: Test database (`dashtam_test`) completely separate from development database (`dashtam`)
- **Fast Iteration**: Optimized test database settings (no fsync, no synchronous commits) for speed
- **Safety Checks**: `init_test_db.py` verifies test environment before destructive operations

### Test Environment Features

- **On-Demand Initialization**: Tests only run when explicitly called via `make test-setup`
- **No Auto-Start**: App container runs `sleep infinity` allowing manual test execution
- **Fixture Support**: pytest fixtures provide database sessions, test clients, and mock data
- **Coverage Tracking**: Tests run with coverage reporting to ensure comprehensive validation

### Test Types Supported

- **Unit Tests**: Isolated component testing with mocked dependencies
- **Integration Tests**: Database and service integration validation
- **API Tests**: End-to-end endpoint testing with FastAPI TestClient

## Future Enhancements

### Planned Improvements

- **Parallel Environment Support**: Allow simultaneous dev and test with unique container names
- **CI/CD Integration**: Dedicated CI environment configuration for GitHub Actions
- **Production Parity**: Production-like docker-compose setup for staging validation
- **Database Migrations**: Alembic integration for schema version management
- **Monitoring**: Prometheus/Grafana integration for local performance monitoring

### Known Limitations

- **No Simultaneous Environments**: Cannot run dev and test concurrently due to shared container names
- **Manual Test Cleanup**: Requires explicit `make test-clean` to remove test environment
- **Single Database Instance**: PostgreSQL instance shared between environments (resource efficiency trade-off)
- **Self-Signed Certificates**: Development SSL uses self-signed certs (browser warnings expected)

## References

### Related Dashtam Documentation

- [Database Migrations](../infrastructure/database-migrations.md) - Schema migration guide
- [Docker Setup](../infrastructure/docker-setup.md) - Detailed Docker configuration
- [Testing Guide](../guides/testing-guide.md) - Comprehensive testing documentation

### Project Files

**Core Application Files:**

- `src/core/config.py` - Settings management
- `src/core/database.py` - Database connection and session management
- `src/core/init_db.py` - Development database initialization
- `src/core/init_test_db.py` - Test database initialization
- `src/main.py` - FastAPI application entry point

**Configuration Files:**

- `.env` - Development environment variables (not in repo)
- `.env.test` - Test environment variables (not in repo)
- `docker-compose.yml` - Base Docker configuration
- `docker-compose.test.yml` - Test environment overrides
- `Makefile` - Command shortcuts

**Database Models:**

- `src/models/user.py` - User model
- `src/models/provider.py` - Provider, Connection, Token, AuditLog models

**Test Files:**

- `tests/test_config.py` - Test configuration
- `tests/conftest.py` - Pytest fixtures
- `tests/unit/` - Unit tests
- `tests/integration/` - Integration tests

---

## Document Information

**Template:** [architecture-template.md](../../templates/architecture-template.md)
**Created:** 2025-10-04
**Last Updated:** 2025-10-17
