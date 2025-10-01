# Dashtam Application Architecture Guide

## Overview

Dashtam uses a **dual-environment architecture** with complete isolation between development and testing. Both environments run in Docker but are configured differently and can coexist simultaneously.

---

## 1. Environment Architecture

### Development Environment
**Purpose**: Active development, debugging, and manual testing

**Containers**:
- `dashtam-app` (port 8000) - FastAPI application
- `dashtam-callback` (port 8182) - OAuth callback server
- `dashtam-postgres` - PostgreSQL database
- `dashtam-redis` - Redis cache

**Configuration**:
- Uses `.env` file
- Database: `dashtam` with user `dashtam_user`
- Auto-runs `init_db.py` on startup
- Hot reload enabled (code changes auto-restart)
- HTTPS with self-signed certs

**Startup Command**: `make up`

### Test Environment
**Purpose**: Automated testing with isolated data

**Containers** (overlays dev):
- Same container names but with test config overlay
- `dashtam-app` runs `sleep infinity` (no auto-start)
- `dashtam-postgres` with test database
- `dashtam-redis` (different database index)

**Configuration**:
- Uses `.env.test` (mounted as `.env`)
- Database: `dashtam_test` with user `dashtam_test_user`
- Runs `init_test_db.py` on demand
- No SSL/auto-reload
- Clean database state for each test run

**Startup Command**: `make test-setup`

---

## 2. Environment Coexistence

### How Environments Interact

**Key Point**: The environments **share the same Docker containers** but with different configurations!

When you run tests:
```bash
make test-setup  # or make test-unit
```

**What happens**:
1. Docker Compose uses file overlays:
   ```bash
   docker-compose --env-file .env.test \
     -f docker-compose.yml \
     -f docker-compose.test.yml \
     up -d postgres redis app
   ```

2. **PostgreSQL container**:
   - Still running the same instance
   - Now has BOTH databases: `dashtam` AND `dashtam_test`
   - Has BOTH users: `dashtam_user` AND `dashtam_test_user`
   - Dev data remains untouched in `dashtam` database
   - Test data is isolated in `dashtam_test` database

3. **App container**:
   - Gets restarted with test configuration
   - `.env.test` mounted as `.env`
   - Environment variables overridden (DATABASE_URL, ENVIRONMENT)
   - Command changed to `sleep infinity` (doesn't auto-start the app)

4. **Dev environment**:
   - Dev containers stop when test containers start
   - Dev database data persists in volumes
   - Can be restarted with `make up` after testing

---

## 3. Database Initialization Flows

### Development Database Initialization

**File**: `src/core/init_db.py`

**When it runs**: Automatically on app container startup

**Process**:
```
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

**Key Points**:
- Idempotent (safe to run multiple times)
- Only creates tables, no seed data
- Runs in DEBUG mode (from .env)
- Logs all SQL queries if DB_ECHO=true

### Test Database Initialization

**File**: `src/core/init_test_db.py`

**When it runs**: On-demand via `make test-setup`

**Process**:
```
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

**Key Points**:
- **Always drops tables first** (clean state)
- Has safety checks to prevent running on prod database
- Optimized for speed (no fsync, no synchronous commits)
- Only runs when explicitly called
- Container stays running for tests

---

## 4. Model Import System

Both initialization scripts must import all models BEFORE calling `SQLModel.metadata.create_all()`. This is because SQLModel uses a metadata registry.

**Why this matters**:
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

**Model Registration**:
- Each model class that inherits from `SQLModel` auto-registers with `SQLModel.metadata`
- The `table=True` parameter marks it as a database table
- Relationships are established via foreign keys

---

## 5. Configuration Management

### Settings Hierarchy

**Development**:
```
Environment Variables (docker-compose.yml)
    ↓
.env file
    ↓
Settings class defaults (src/core/config.py)
    ↓
Final Settings object
```

**Testing**:
```
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

---

## 6. Typical Workflows

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

---

## 7. Database State Management

### Development Database State

**Location**: Docker volume `dashtam_postgres_data`

**Persistence**:
- Survives container restarts
- Survives `make down`
- Lost with `make clean`

**Tables**:
- users
- providers
- provider_connections
- provider_tokens
- provider_audit_logs

**When to reset**:
```bash
make clean          # Remove all data and containers
make build          # Rebuild
make up             # Fresh start
```

### Test Database State

**Location**: Same PostgreSQL instance, different database

**Persistence**:
- **Intentionally destroyed** on each `make test-setup`
- `init_test_db.py` drops all tables
- Always starts with clean slate

**Why this matters**:
- Tests are isolated from each other
- No test data pollution
- Predictable test environment

---

## 8. Common Issues and Solutions

### Issue: Tests fail with "database does not exist"
**Solution**: Run `make test-setup` first to initialize test database

### Issue: Dev database lost after testing
**Solution**: Dev database is in a different database (`dashtam` vs `dashtam_test`). Use `make up` to restart dev environment.

### Issue: Environment variables not loading in tests
**Solution**: Ensure `docker-compose.test.yml` properly overrides and `.env.test` is mounted as `.env`

### Issue: Tables not created in test database
**Solution**: Verify all models are imported in `init_test_db.py` before `create_all()`

### Issue: Can't run dev and tests simultaneously
**Solution**: By design. Use `make test-clean` then `make up` to switch back to dev.

---

## 9. File Reference

### Core Application Files
- `src/core/config.py` - Settings management
- `src/core/database.py` - Database connection and session management
- `src/core/init_db.py` - Development database initialization
- `src/core/init_test_db.py` - Test database initialization
- `src/main.py` - FastAPI application entry point

### Configuration Files
- `.env` - Development environment variables
- `.env.test` - Test environment variables
- `docker-compose.yml` - Base Docker configuration
- `docker-compose.test.yml` - Test environment overrides
- `Makefile` - Command shortcuts

### Database Models
- `src/models/user.py` - User model
- `src/models/provider.py` - Provider, Connection, Token, AuditLog models

### Test Files
- `tests/test_config.py` - Test configuration
- `tests/conftest.py` - Pytest fixtures
- `tests/unit/` - Unit tests
- `tests/integration/` - Integration tests

---

## Summary

The Dashtam application uses a sophisticated **dual-environment architecture** where:

1. **Development and testing are completely isolated** (different databases, users, configs)
2. **Both run in Docker** with different compose file overlays
3. **Database initialization is automatic for dev**, on-demand for tests
4. **Test environment always starts clean** (drops tables on each run)
5. **Dev data persists** even when running tests
6. **Switching between environments** is seamless with Make commands

This architecture ensures:
- ✅ No test data pollution
- ✅ Safe, repeatable testing
- ✅ Dev environment stability
- ✅ Complete isolation
- ✅ Easy workflow switching
