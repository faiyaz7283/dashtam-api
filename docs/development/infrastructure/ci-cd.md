# GitHub Actions CI/CD Pipeline

Complete CI/CD automation with GitHub Actions, Docker, and Codecov integration for the Dashtam platform.

## Overview

The Dashtam CI/CD pipeline automates testing, linting, and code quality checks using GitHub Actions. Every push triggers automated validation to ensure code quality and prevent regressions.

### Key Features

- **Automated Testing**: Full test suite (295 tests) runs on every push
- **Code Quality**: Automated linting with ruff
- **Coverage Tracking**: Integrated Codecov reporting (76% coverage)
- **Branch Protection**: Required status checks before merge
- **Docker-Based**: Isolated test environment matching production
- **Parallel Execution**: Test and lint jobs run simultaneously (~2-3 min total)

### Current Status

✅ **Fully Operational** - All systems green

- 295 tests passing
- 76% code coverage
- Branch protection active on `development`
- Zero failing workflows

## Purpose

The CI/CD pipeline serves critical functions:

**Quality Assurance**:

- Catch bugs before they reach main branch
- Enforce code quality standards
- Track test coverage trends
- Prevent regression failures

**Developer Productivity**:

- Instant feedback on code changes
- Automated repetitive tasks
- Consistent environment for all developers
- Reduced manual testing burden

**Compliance**:

- Required checks before merge
- Audit trail of all code changes
- Coverage requirements enforced
- Quality gates for production

## Components

### Component 1: GitHub Actions Workflow

**Purpose:** Orchestrates automated testing and quality checks

**Technology:** GitHub Actions (cloud-hosted runners)

**File:** `.github/workflows/test.yml`

**Jobs:**

1. **Test Suite** - Runs all tests in Docker environment
2. **Code Quality** - Lints code with ruff

**Dependencies:**

- Docker
- docker-compose v2
- PostgreSQL (test database)
- Redis (test cache)

### Component 2: CI Docker Environment

**Purpose:** Isolated test environment matching production configuration

**Technology:** Docker Compose

**File:** `compose/docker-compose.ci.yml`

**Services:**

- `app` - FastAPI application container
- `postgres` - PostgreSQL 17.6 test database
- `redis` - Redis 8.2.1 cache

**Dependencies:**

- `.env.ci` environment configuration
- Health checks for service readiness

### Component 3: Codecov Integration

**Purpose:** Track and visualize test coverage over time

**Technology:** Codecov (SaaS)

**File:** `codecov.yml`

**Features:**

- Coverage uploads on every CI run
- PR comments with coverage diff
- Coverage badge in README
- Historical trend tracking

**Dependencies:**

- `CODECOV_TOKEN` GitHub secret
- XML coverage reports from pytest

### Component 4: Branch Protection

**Purpose:** Enforce quality gates before merging code

**Technology:** GitHub branch protection rules

**Protected Branch:** `development`

**Required Checks:**

- ✅ `Test Suite / Run Tests` - All tests must pass
- ✅ `Code Quality / lint` - Linting must pass
- ✅ Branches must be up to date

**Restrictions:**

- No direct commits (PRs required)
- No force pushes
- No branch deletion
- At least 1 approval required

## Configuration

### Environment Variables

**CI Environment** (`.env.ci`):

```bash
# Database Configuration
POSTGRES_USER=dashtam_test      # Test database user
POSTGRES_PASSWORD=dashtam_test  # Test database password
POSTGRES_DB=dashtam_test        # Test database name
POSTGRES_HOST=postgres          # Docker service name
POSTGRES_PORT=5432              # Internal port

# Redis Configuration
REDIS_HOST=redis                # Docker service name
REDIS_PORT=6379                 # Internal port

# Application Configuration
DEBUG=true                      # Enable debug mode for tests
SECRET_KEY=test-secret-key-ci   # JWT signing key (test only)
ENCRYPTION_KEY=test-encryption  # Token encryption (test only)

# HTTP Timeouts
HTTP_TIMEOUT_TOTAL=30           # Overall request timeout (seconds)
HTTP_TIMEOUT_CONNECT=10         # Connection timeout (seconds)

# AWS Configuration (Mocked in CI)
AWS_REGION=us-east-1            # Not used (mocked)
# AWS credentials not needed (tests use mocks)
```

### Configuration Files

**File:** `.github/workflows/test.yml`

```yaml
name: Test Suite

on:
  push:
    branches: [ main, development, develop ]
  pull_request:
    branches: [ main, development, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Tests
        run: |
          docker compose -f compose/docker-compose.ci.yml up -d --build
          # ... test execution steps
```

**Purpose:** Defines workflow triggers and job execution

**File:** `codecov.yml`

```yaml
coverage:
  status:
    project:
      default:
        target: 85%          # Target overall coverage
        threshold: 2%        # Allow 2% drop without failing
    patch:
      default:
        target: 80%          # New code should be 80%+ tested
        threshold: 5%
```

**Purpose:** Configure coverage thresholds and reporting

### Ports and Services

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| app | 8000 | HTTP | FastAPI application (internal) |
| postgres | 5432 | TCP | PostgreSQL database (internal) |
| redis | 6379 | TCP | Redis cache (internal) |

**Note:** CI environment uses internal Docker networking only (no exposed ports)

## Setup Instructions

### Prerequisites

- [x] GitHub repository with Actions enabled
- [x] Codecov account connected to repository
- [x] Docker and docker-compose v2 installed locally (for testing)
- [x] `CODECOV_TOKEN` secret configured in GitHub

### Installation Steps

#### Step 1: Configure Workflow File

Already complete: `.github/workflows/test.yml`

**Verification:**

```bash
# Verify workflow file exists and is valid
cat .github/workflows/test.yml
```

#### Step 2: Configure CI Environment

Already complete: `compose/docker-compose.ci.yml` and `env/.env.ci.example`

**Verification:**

```bash
# Verify CI compose file
cat compose/docker-compose.ci.yml

# Verify environment template
cat env/.env.ci.example
```

#### Step 3: Enable Branch Protection

1. Go to GitHub repo **Settings** → **Branches**
2. Click **Add rule** or edit existing `development` rule
3. Configure protection settings (see Components section)
4. Save changes

**Verification:** Push to `development` - should require PR

#### Step 4: Configure Codecov

1. Visit [codecov.io](https://codecov.io)
2. Connect GitHub account and authorize repository
3. Copy `CODECOV_TOKEN` from Codecov settings
4. Add token to GitHub: **Settings** → **Secrets** → **Actions** → New secret

**Verification:**

```bash
# Check if token is configured (from GitHub UI)
# Settings → Secrets and variables → Actions → CODECOV_TOKEN
```

## Operation

### Starting the System

CI runs automatically on push/PR. To test locally:

```bash
# Run full CI pipeline locally
make ci-test

# Or manually with docker compose
docker compose -f compose/docker-compose.ci.yml up -d --build
docker compose -f compose/docker-compose.ci.yml exec -T app uv run pytest tests/
```

### Stopping the System

```bash
# Stop CI environment
make ci-down

# Or manually
docker compose -f compose/docker-compose.ci.yml down -v
```

### Checking Status

**GitHub Actions:**

```bash
# Via GitHub CLI
gh run list --limit 10

# Or visit GitHub Actions tab in browser
# https://github.com/YOUR_USERNAME/Dashtam/actions
```

**Expected Output:** ✅ All checks passed

**Codecov Status:**

Visit: `https://codecov.io/gh/faiyaz7283/Dashtam`

**Expected:** 76%+ coverage, green status

## Monitoring

### Health Checks

**Docker Services:**

```bash
# Check service health status
docker compose -f compose/docker-compose.ci.yml ps

# Expected: all services "healthy"
```

**GitHub Actions:**

- Navigate to **Actions** tab in GitHub
- All recent runs should show ✅ green checkmarks
- Any ❌ red X indicates failure requiring investigation

### Metrics to Monitor

- **Test Success Rate**: Should be 100% (295/295 tests passing)
- **Build Time**: 2-3 minutes typical, investigate if >5 minutes
- **Coverage Percentage**: 76% current, target 85%+
- **Workflow Success Rate**: Track via GitHub Actions dashboard

### Logs

**GitHub Actions Logs:**

1. Go to **Actions** tab
2. Click on workflow run
3. Expand job and step to see detailed logs

**Local CI Logs:**

```bash
# View all services
docker compose -f compose/docker-compose.ci.yml logs -f

# View specific service
docker compose -f compose/docker-compose.ci.yml logs -f app
```

**Coverage Reports:**

- Download artifacts from GitHub Actions workflow run
- Extract `test-results.zip` → `htmlcov/` folder
- Open `htmlcov/index.html` in browser

## Troubleshooting

### Issue 1: Workflow Not Running

**Symptoms:**

- Push to branch but no workflow appears in Actions tab
- No status checks on PR

**Diagnosis:**

```bash
# Verify workflow file exists
ls -la .github/workflows/

# Check YAML syntax
cat .github/workflows/test.yml | head -20
```

**Solution:**

1. Verify file is at `.github/workflows/test.yml`
2. Check YAML indentation (use spaces, not tabs)
3. Ensure GitHub Actions is enabled: **Settings** → **Actions** → **Allow all actions**

### Issue 2: Tests Failing in CI but Pass Locally

**Symptoms:**

- `make test` passes locally
- GitHub Actions workflow fails with test errors

**Diagnosis:**

```bash
# Run CI environment locally
make ci-test

# Check environment differences
diff .env.test .env.ci.example
```

**Solution:**

1. Ensure `.env.ci` is committed and up to date
2. Run `make ci-test` locally to reproduce issue
3. Check for timezone-related failures (use `datetime.now(timezone.utc)`)
4. Verify Docker cache is not causing issues (rebuild: `docker compose build --no-cache`)

### Issue 3: Codecov Upload Failing

**Symptoms:**

- Tests pass but coverage upload fails
- Coverage badge shows "unknown"

**Diagnosis:**

```bash
# Check if CODECOV_TOKEN is set (GitHub UI)
# Settings → Secrets and variables → Actions

# Check codecov.yml syntax
cat codecov.yml
```

**Solution:**

1. Verify `CODECOV_TOKEN` secret exists in GitHub
2. Check `codecov.yml` syntax is valid
3. Ensure coverage XML file is generated: `pytest --cov=src --cov-report=xml`
4. Re-run workflow after fixing

### Issue 4: Branch Protection Preventing Merge

**Symptoms:**

- PR shows "Required status checks are failing"
- Cannot merge even with approval

**Diagnosis:**

- Check which status check is failing (red X in PR)
- Click on "Details" to view logs

**Solution:**

1. Fix failing test or linting issue
2. Push fix to PR branch
3. Wait for checks to re-run and pass
4. If checks are stale: update branch with latest from `development`

## Maintenance

### Regular Tasks

- **Daily:** Monitor CI runs for failures
- **Weekly:** Review coverage trends on Codecov
- **Monthly:** Review and update CI dependencies (GitHub Actions versions)
- **Quarterly:** Audit branch protection rules and adjust as needed

### Backup Procedures

No backup needed - CI is stateless and configuration is version-controlled.

**Configuration Backup:**

```bash
# All CI configuration is in git
git log -- .github/workflows/ compose/docker-compose.ci.yml env/.env.ci.example
```

### Update Procedures

**Update GitHub Actions Versions:**

```bash
# Update actions in .github/workflows/test.yml
# Example: actions/checkout@v4 → actions/checkout@v5

# Test locally
make ci-test

# Commit and push
git add .github/workflows/test.yml
git commit -m "ci: update GitHub Actions to v5"
git push
```

**Update Docker Images:**

```bash
# Update base images in compose/docker-compose.ci.yml
# Example: postgres:17.6 → postgres:17.7

# Test
make ci-rebuild && make ci-test

# Commit
git add compose/docker-compose.ci.yml
git commit -m "ci: update PostgreSQL to 17.7"
```

## Security

### Security Considerations

- **Secrets Management**: All secrets stored in GitHub Secrets (encrypted at rest)
  - Never log secrets in workflow output
  - Use `${{ secrets.NAME }}` syntax only
  - Rotate `CODECOV_TOKEN` annually

- **Docker Security**: CI uses non-root user (`appuser` UID 1000)
  - All containers run as `appuser`
  - No privileged mode
  - Isolated Docker networks

- **Branch Protection**: Prevents unauthorized changes to `development` and `main`
  - Required PR reviews
  - Required status checks
  - No force pushes

### Access Control

**GitHub Actions:**

- Only repository collaborators can view workflow runs
- Secrets are not exposed in logs
- Fork PRs run with limited permissions

**Codecov:**

- OAuth integration with GitHub
- Only authorized team members can access dashboard
- Coverage data is public (open source project)

### Network Security

- CI containers use isolated Docker networks (`dashtam-ci-network`)
- No external network access except:
  - GitHub for code checkout
  - Codecov for coverage upload
  - Docker Hub for base images
- Internal services communicate via Docker DNS

## Performance Optimization

### Performance Tuning

- **Docker Layer Caching**: Workflow uses Docker's built-in caching
  - Base image layers cached
  - Dependency layers cached
  - Only application code rebuilt on changes

- **Parallel Jobs**: Test and lint run simultaneously
  - Reduces total workflow time by ~50%

- **Matrix Strategy** (future): Run tests across multiple Python versions
  - Currently single version (3.13)
  - Future: 3.11, 3.12, 3.13 matrix

### Resource Limits

**GitHub Actions Runner:**

```yaml
# Free tier limits (per repository)
storage: 500 MB artifacts
concurrent_jobs: 20
```

**Docker Resources** (CI environment):

```yaml
# compose/docker-compose.ci.yml services
app:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
postgres:
  deploy:
    resources:
      limits:
        cpus: '1'
        memory: 1G
```

### Current Performance Metrics

- **Total Duration:** 2-3 minutes per run
- **Test Execution:** ~45 seconds (295 tests)
- **Docker Build:** ~60-90 seconds (with cache)
- **Linting:** ~10 seconds
- **Coverage Upload:** ~5 seconds
- **Success Rate:** 100% (stable pipeline)

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Compose v2 CLI Reference](https://docs.docker.com/compose/cli-command/)
- [Codecov Documentation](https://docs.codecov.com/)
- [Branch Protection Rules Guide](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [Internal: Docker Setup Guide](docker-setup.md)
- [Internal: Testing Strategy](../../testing/strategy.md)

---

## Document Information

**Template:** [infrastructure-template.md](../../templates/infrastructure-template.md)
**Created:** 2025-10-12
**Last Updated:** 2025-01-17
