# Local CI Testing Guide

**Purpose**: Run CI/CD checks locally before pushing to GitHub, enabling faster feedback and debugging.

**Last Updated**: 2025-12-12

---

## Quick Start

```bash
# Full CI suite (recommended before pushing)
make ci-test-local

# Tests only (faster iteration)
make ci-test

# Linting only (code quality checks)
make ci-lint
```

---

## Available CI Commands

### `make ci-test-local` - Full CI Suite

Runs the complete CI pipeline locally:

1. **Tests** - All tests except smoke tests (with coverage)
2. **Linter** - Ruff code linting
3. **Format Check** - Code formatting validation
4. **Type Check** - mypy type checking

**When to use**: Before pushing commits, before creating PRs.

**Expected duration**: 2-3 minutes

```bash
make ci-test-local
```

**What it does**:

- Starts CI environment (`docker-compose.ci.yml`)
- Runs migrations
- Executes all quality checks
- Cleans up containers automatically
- Exits with error code if any check fails

### `make ci-test` - Tests Only

Matches GitHub Actions `test-main` job behavior exactly.

**When to use**: Quick test validation, debugging test failures.

**Expected duration**: 1-2 minutes

```bash
make ci-test
```

**What it does**:

- Starts CI environment
- Runs tests (excludes smoke tests)
- Generates coverage report
- Cleans up automatically

### `make ci-lint` - Linting Only

Matches GitHub Actions `lint` job behavior exactly.

**When to use**: Quick code quality checks, fixing lint issues.

**Expected duration**: 30-60 seconds

```bash
make ci-lint
```

**What it does**:

- Runs `ruff check` (linting)
- Runs `ruff format --check` (formatting)
- Runs `markdownlint-cli2` (markdown)
- Cleans up automatically

---

## CI Environment vs Local Test Environment

### CI Environment (`docker-compose.ci.yml`)

- **Purpose**: Match GitHub Actions exactly
- **Speed**: Optimized (tmpfs, aggressive health checks)
- **Isolation**: Fresh containers each run
- **Database**: Ephemeral, no persistence
- **Ports**: No external ports (internal only)

### Test Environment (`docker-compose.test.yml`)

- **Purpose**: Interactive local testing
- **Speed**: Standard
- **Isolation**: Persistent between runs
- **Database**: Persists data
- **Ports**: Exposed (5433, 6380)

**Key difference**: CI environment is disposable and optimized for speed. Test environment is stateful for development.

---

## Debugging CI Failures

### Strategy 1: Reproduce Locally

```bash
# Run full CI suite locally
make ci-test-local

# If it fails, you can debug:
# 1. Check the specific failing step in output
# 2. Run that check individually (see below)
```

### Strategy 2: Run Individual Checks

```bash
# Just tests
make ci-test

# Just linting
make ci-lint

# Just formatting check
docker compose -f compose/docker-compose.ci.yml exec app \
  uv run ruff format --check src/ tests/
```

### Strategy 3: Interactive Debugging

```bash
# Start CI environment manually
docker compose -f compose/docker-compose.ci.yml up -d --build

# Shell into container
docker compose -f compose/docker-compose.ci.yml exec app /bin/bash

# Run tests manually
uv run pytest tests/ -v --cov=src

# Cleanup when done
docker compose -f compose/docker-compose.ci.yml down -v
```

---

## Common CI Failures & Solutions

### Tests Pass Locally But Fail in CI

**Possible causes**:

1. **Test environment differences** - CI uses fresh database
2. **Test order dependencies** - CI may run tests in different order
3. **Timing issues** - CI may be slower/faster

**Solution**:

```bash
# Always test with fresh CI environment
make ci-test
```

### Lint Passes Locally But Fails in CI

**Possible causes**:

1. **Ruff version mismatch** - CI uses exact versions from `uv.lock`
2. **Markdown lint config differences**

**Solution**:

```bash
# Use CI lint target (uses exact CI versions)
make ci-lint
```

### Type Check Passes Locally But Fails in CI

**Possible causes**:

1. **mypy version mismatch**
2. **Different Python version** - CI uses Python 3.13

**Solution**:

```bash
# Run type check in CI container
docker compose -f compose/docker-compose.ci.yml up -d --build
docker compose -f compose/docker-compose.ci.yml exec app uv run mypy src
docker compose -f compose/docker-compose.ci.yml down -v
```

---

## CI Environment Configuration

### Environment File

CI uses `env/.env.ci` (copied from `env/.env.ci.example`):

```bash
# Copy example if missing
cp env/.env.ci.example env/.env.ci
```

**Key settings**:

- `ENVIRONMENT=ci` - CI-specific behavior
- `TESTING=true` - Test mode enabled
- Fixed test keys (not cryptographically secure)

### Database Optimizations

CI PostgreSQL is optimized for speed over durability:

```sql
synchronous_commit=off  -- No disk sync on commit
fsync=off               -- No fsync calls
full_page_writes=off    -- No full page writes
```

**Safe for CI because**:

- Each job is isolated
- Database is ephemeral (tmpfs)
- No data to lose

---

## GitHub Actions Workflow

### Test Pipeline

```text
[Push to GitHub]
    │
    ├─> test-main (Ubuntu)
    │   ├─ Start CI containers
    │   ├─ Run tests (exclude smoke)
    │   ├─ Upload coverage to Codecov
    │   └─ Cleanup
    │
    └─> test-smoke (Ubuntu, after test-main)
        ├─ Start fresh CI containers
        ├─ Run smoke tests only
        └─ Cleanup
```

### Lint Pipeline

```text
[Push to GitHub]
    │
    └─> lint (Ubuntu)
        ├─ Install uv + dependencies
        ├─ Run ruff linter
        ├─ Check code formatting
        └─ Run markdown linter
```

---

## Best Practices

### Before Every Commit

```bash
# 1. Format code
make format

# 2. Run tests locally
make test

# 3. Run CI checks
make ci-test-local
```

### Before Creating PR

```bash
# Full CI suite must pass
make ci-test-local

# If it passes, CI will pass in GitHub Actions
```

### When CI Fails in GitHub

```bash
# 1. Pull latest changes
git pull

# 2. Reproduce locally
make ci-test-local

# 3. Fix the issue

# 4. Verify fix
make ci-test-local

# 5. Push
git push
```

---

## Performance Tips

### Speed Up Local CI

```bash
# Skip tests if only linting
make ci-lint  # ~30-60 seconds

# Skip linting if only tests
make ci-test  # ~1-2 minutes
```

### Cache Optimization

Docker layer caching helps speed up subsequent runs:

```bash
# First run: ~2-3 minutes (builds images)
make ci-test-local

# Subsequent runs: ~1-2 minutes (uses cached images)
make ci-test-local
```

### Clean Docker Cache (if needed)

```bash
# If CI is slow or having issues
docker system prune -a --volumes
```

---

## Troubleshooting

### "service 'app' is not running"

**Cause**: CI containers didn't start properly.

**Solution**:

```bash
# Check logs
docker compose -f compose/docker-compose.ci.yml logs

# Cleanup and retry
docker compose -f compose/docker-compose.ci.yml down -v
make ci-test
```

### "Cannot connect to the Docker daemon"

**Cause**: Docker Desktop is not running.

**Solution**:

```bash
# Start Docker Desktop
open -a Docker
```

### "Port already in use"

**Cause**: CI uses internal networking only, no port conflicts.

**Solution**: This shouldn't happen with CI. If it does, check for other Docker containers using the same network name:

```bash
docker network ls | grep dashtam-ci
docker network rm dashtam-ci-network
```

---

## References

- **Makefile**: CI targets at lines 291-382
- **CI Docker Compose**: `compose/docker-compose.ci.yml`
- **GitHub Actions**: `.github/workflows/test.yml`
- **Environment Config**: `env/.env.ci.example`

---

**Created**: 2025-12-12 | **Last Updated**: 2025-12-12
