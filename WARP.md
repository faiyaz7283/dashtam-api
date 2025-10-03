# Dashtam Project Rules and Context

This file contains project-specific rules, coding standards, and context for AI agents working on the Dashtam financial data aggregation platform.

## Project Overview

Dashtam is a secure, modern financial data aggregation platform that connects to multiple financial institutions through OAuth2, providing a unified API for accessing accounts, transactions, and financial data. The platform is built with FastAPI, PostgreSQL, Redis, and Docker, emphasizing type safety, async operations, and security.

### Current Status
- ✅ OAuth2 flow fully implemented and tested with Charles Schwab
- ✅ Token encryption and secure storage implemented
- ✅ Database models and relationships established
- ✅ Docker containerization complete with SSL/HTTPS everywhere
- ✅ Callback server for OAuth redirects operational
- ✅ Environment configuration properly set up (DEBUG mode, .env variables)
- ✅ Database async operations working without errors (no greenlet_spawn issues)
- ✅ Pydantic v2 compatibility fully implemented (all models updated)
- ✅ API documentation endpoints working (/docs, /redoc)
- ✅ All advertised API endpoints functional and tested
- ✅ Docker following UV 0.8.22 best practices
- ✅ **PHASE 1 INFRASTRUCTURE COMPLETE** - Parallel Environments
  - ✅ Separate dev and test Docker Compose configurations
  - ✅ Isolated networks and container naming (no conflicts)
  - ✅ Environment-specific ports and volumes
  - ✅ Health checks for all services (postgres, redis)
  - ✅ Make-based workflow for all environments
- ✅ **PHASE 1 TEST INFRASTRUCTURE COMPLETE**
  - ✅ Synchronous testing strategy implemented (FastAPI TestClient pattern)
  - ✅ Unit tests for core services (encryption, 9 tests)
  - ✅ Integration tests for database operations and relationships (11 tests)
  - ✅ API endpoint tests for providers (19 tests)
  - ✅ Comprehensive test fixtures and mocks
  - ✅ Docker-based test environment with isolated PostgreSQL
  - ✅ Make-based test workflow (test-verify, test-unit, test-integration)
  - ✅ Code quality automation (linting, formatting)
  - ✅ **39 tests passing, 51% code coverage**
- ✅ **PHASE 2 CI/CD COMPLETE**
  - ✅ GitHub Actions workflow configured and operational
  - ✅ Automated linting and code formatting checks
  - ✅ CI-specific Docker Compose configuration (optimized)
  - ✅ Branch protection enabled on development branch
  - ✅ Codecov integration configured with codecov.yml
  - ✅ Coverage reporting to Codecov on all CI runs
  - ✅ Docker Compose v2 migration complete
  - ✅ All tests passing in CI pipeline
- 🚧 Financial data endpoints (accounts, transactions) pending implementation
- 🚧 Additional provider integrations pending
- 📋 Test coverage expansion (Phase 2+) - targeting 85% overall coverage

## Architecture Rules

### Technology Stack Requirements
- **Backend Framework**: Always use FastAPI with async/await patterns
- **Database**: PostgreSQL with SQLModel ORM (NOT SQLAlchemy ORM directly)
- **Async Operations**: Use SQLAlchemy's AsyncSession with proper async patterns
- **Cache**: Redis for session and temporary data storage
- **Package Management**: Use UV (not pip or poetry)
- **Python Version**: Python 3.13+ required
- **Containerization**: Docker and Docker Compose for all services

### Database Access Patterns

**CRITICAL**: This project uses SQLAlchemy's AsyncSession. NEVER use these patterns:
```python
# ❌ WRONG - These don't work with AsyncSession
provider = await session.get(Provider, provider_id)
await session.refresh(provider, ["relationship"])
```

**ALWAYS use these patterns instead:**
```python
# ✅ CORRECT - Proper async patterns
from sqlmodel import select
from sqlalchemy.orm import selectinload

# For simple queries
result = await session.execute(
    select(Provider).where(Provider.id == provider_id)
)
provider = result.scalar_one_or_none()

# For queries with relationships
result = await session.execute(
    select(Provider)
    .options(selectinload(Provider.connection))
    .where(Provider.id == provider_id)
)
provider = result.scalar_one_or_none()
```

### Security Requirements
- **HTTPS Only**: All services must use SSL/TLS (self-signed in dev, proper certs in prod)
- **Token Encryption**: All OAuth tokens must be encrypted using AES-256 before storage
- **No Secrets in Code**: Use environment variables for all sensitive data
- **Audit Logging**: All provider operations must be logged in provider_audit_logs table

## Coding Standards

### Python Code Style
- **Type Hints**: ALWAYS use type hints for function parameters and return values
- **Docstrings**: Use Google-style docstrings for all functions and classes
- **Async/Await**: Prefer async functions for all database and I/O operations
- **Error Handling**: Use proper exception handling with specific error messages
- **Logging**: Use structured logging with appropriate log levels

### Import Organization
Always organize imports in this order:
1. Standard library imports
2. Third-party imports
3. Local application imports

Example:
```python
import logging
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.provider import Provider
from src.core.database import get_session
```

### File Naming Conventions
- **Python files**: Use snake_case (e.g., `token_service.py`)
- **Docker files**: Use PascalCase with extensions (e.g., `Dockerfile`)
- **Config files**: Use lowercase with appropriate extensions (e.g., `docker-compose.yml`)
- **Documentation**: Use UPPERCASE for special files (e.g., `README.md`, `WARP.md`)

## Project Structure Rules

### Directory Organization
```
src/
├── api/           # API endpoints only
├── core/          # Core functionality (config, database, security)
├── models/        # SQLModel database models
├── providers/     # Provider implementations
└── services/      # Business logic and service layer
```

### Module Responsibilities
- **api/**: Only HTTP endpoint definitions, no business logic
- **services/**: All business logic, token management, provider operations
- **models/**: Database models with relationships and methods
- **providers/**: Provider-specific OAuth and API implementations
- **core/**: Shared utilities, configuration, database setup

## Docker and Development Rules

### Docker-Only Development Policy
**CRITICAL RULE**: All development, testing, and execution must be done through Docker containers.
- **NEVER run Python directly on host machine** for project-related tasks
- **NEVER install project dependencies on host machine**
- **All testing must be done in Docker containers** using `make test` or `docker-compose exec`
- **Database operations must use containerized database**
- **Package management must use containerized UV**

This ensures:
- Complete environment isolation
- Consistent development experience across machines
- No dependency conflicts with host system
- Production-identical development environment

### Docker Service Names
Environment-specific container names with suffixes:

**Development:**
- `dashtam-dev-app` - Main FastAPI application
- `dashtam-dev-callback` - OAuth callback server
- `dashtam-dev-postgres` - PostgreSQL database
- `dashtam-dev-redis` - Redis cache

**Test:**
- `dashtam-test-app` - Test application
- `dashtam-test-callback` - Test callback server
- `dashtam-test-postgres` - Test PostgreSQL database
- `dashtam-test-redis` - Test Redis cache

**CI/CD:**
- `dashtam-ci-app` - CI application
- `dashtam-ci-postgres` - CI PostgreSQL database
- `dashtam-ci-redis` - CI Redis cache

### Network Configuration
**Development:**
- Network: `dashtam-dev-network`
- Ports: 8000 (app), 8182 (callback), 5432 (postgres), 6379 (redis)

**Test:**
- Network: `dashtam-test-network`
- Ports: 8001 (app), 8183 (callback), 5433 (postgres), 6380 (redis)

**CI:**
- Network: `dashtam-ci-network`
- No external ports (internal only for security)

**Internal Communication:**
- Backend internal hostname: `app` (NOT `backend` or `localhost`)
- All environments use same internal container ports

### Environment Variables
Critical environment variables that must be set:
```bash
DATABASE_URL=postgresql+asyncpg://...  # Must use asyncpg driver
SCHWAB_API_KEY=...                     # OAuth client ID
SCHWAB_API_SECRET=...                   # OAuth client secret
SCHWAB_REDIRECT_URI=https://127.0.0.1:8182
SECRET_KEY=...                          # For JWT signing
ENCRYPTION_KEY=...                      # For token encryption
```

## API Design Rules

### Endpoint Naming
- Use RESTful conventions with clear resource names
- Prefix all API routes with `/api/v1/`
- Use UUID for resource identifiers, not integers
- Provider-specific endpoints: `/api/v1/providers/{provider_id}/...`
- Auth endpoints: `/api/v1/auth/{provider_id}/...`

### Response Format
- Always return consistent JSON responses
- Include appropriate HTTP status codes
- Provide detailed error messages in development
- Use Pydantic models for request/response validation

### Authentication Flow
The OAuth flow must follow this exact sequence:
1. Create provider instance: `POST /api/v1/providers/create`
2. Get authorization URL: `GET /api/v1/auth/{provider_id}/authorize`
3. User authorizes in browser
4. Callback received at `https://127.0.0.1:8182`
5. Tokens stored encrypted in database
6. Provider marked as connected

## Testing and Development Rules

### Test Coverage
- **PHASE 1 COMPLETE**: Synchronous test infrastructure fully operational
- **Test strategy**: FastAPI TestClient with synchronous SQLModel sessions
- **Test pyramid approach**: 70% unit, 20% integration, 10% e2e tests
- **Target coverage**: 85%+ overall, 95%+ for critical components
- **Working test workflow**: Make-based commands for all test operations
- **Current coverage**: 51% overall (39 tests passing) ✅
  - Unit tests: 9 tests (encryption service)
  - Integration tests: 11 tests (database operations, relationships)
  - API tests: 19 tests (provider endpoints)
- **Docker integration**: All tests run in isolated containers ✅
- **Safety features**: Environment validation, test database isolation ✅
- **CI/CD Integration**: Automated testing via GitHub Actions ✅
- **Code Quality**: Automated linting (ruff) and formatting checks ✅
- **Current status**: All 39 tests passing in both local and CI environments ✅

### Local Development Commands
Always use the Makefile for common operations:

**Development Environment:**
- `make dev-up` - Start development services
- `make dev-down` - Stop development services
- `make dev-logs` - View development logs
- `make dev-status` - Check development service status
- `make dev-shell` - Open shell in dev app container
- `make dev-restart` - Restart development environment
- `make dev-rebuild` - Rebuild dev images from scratch (no cache)

**Test Environment:**
- `make test-up` - Start test services
- `make test-down` - Stop test services
- `make test-status` - Check test service status
- `make test-rebuild` - Rebuild test images from scratch
- `make test-restart` - Restart test environment

**Running Tests:**
- `make test-verify` - Quick core functionality verification
- `make test-unit` - Run unit tests
- `make test-integration` - Run integration tests
- `make test` - Run all tests with coverage

**Code Quality:**
- `make lint` - Run code linting (ruff check)
- `make format` - Format code (ruff format)

**CI/CD:**
- `make ci-test` - Run CI tests locally
- `make ci-build` - Build CI images
- `make ci-down` - Clean up CI environment

**Utilities:**
- `make status-all` - Check status of all environments
- `make certs` - Generate SSL certificates
- `make keys` - Generate encryption keys
- `make clean` - Clean everything
- `make setup` - Complete initial setup

### SSL Certificates
- Development uses self-signed certificates
- Located in `certs/` directory
- Must be generated before first run: `make certs`
- Browser warnings are expected in development

### Database Migrations
- Use Alembic for schema migrations (future)
- Currently using `init_db.py` for development
- Tables are created automatically on startup in dev mode

## Error Handling Patterns

### Common Issues and Solutions (RESOLVED)

#### "greenlet_spawn has not been called" Error ✅ FIXED
- **Cause**: Improper async database operations
- **Solution**: All database queries now use proper `session.execute(select(...))` pattern
- **Status**: All async database operations working correctly

#### "Invalid host header" Error ✅ FIXED
- **Cause**: TrustedHostMiddleware blocking requests
- **Solution**: Docker service names properly configured in allowed_hosts
- **Status**: All internal Docker communication working

#### Connection Errors in Callback Server ✅ FIXED
- **Cause**: Wrong internal hostname configuration
- **Solution**: Using correct `app` hostname for internal communication
- **Status**: OAuth callback flow working perfectly

#### API Documentation Not Available ✅ FIXED
- **Cause**: DEBUG mode not properly configured
- **Solution**: Fixed environment configuration to enable DEBUG in development
- **Status**: `/docs` and `/redoc` endpoints now accessible

## Provider Implementation Rules

### Adding New Providers
1. Create provider class in `src/providers/` inheriting from `BaseProvider`
2. Implement required methods: `get_auth_url()`, `authenticate()`, `refresh_authentication()`
3. Register in `ProviderRegistry` in `src/providers/registry.py`
4. Add configuration to `.env` file
5. Test OAuth flow end-to-end before proceeding

### Token Management
- Always encrypt tokens before storage
- Implement automatic refresh logic
- Handle token rotation if provider sends new refresh token
- Log all token operations in audit log

## Git and Version Control Rules

**CRITICAL**: Dashtam follows **Git Flow** workflow with strict branch protection and automated testing requirements. See [Git Workflow Guide](docs/development/guides/git-workflow.md) for complete documentation.

### Branching Strategy (Git Flow)

**Primary Branches**:
- **`main`** - Production-ready code only
  - ✅ Protected with required PR approvals and tests
  - ✅ Tagged with semantic versions (e.g., `v1.2.0`)
  - ✅ Always deployable to production
  - ✅ Receives merges from `release/*` and `hotfix/*` only

- **`development`** - Integration branch for active development
  - ✅ Protected with required PR approvals and tests
  - ✅ Contains unreleased features
  - ✅ Always ahead of `main`
  - ✅ Receives merges from `feature/*` and `fix/*` branches

**Supporting Branches**:
- **`feature/*`** - New features (e.g., `feature/account-api`)
  - Branch from: `development`
  - Merge to: `development`
  - Delete after merge

- **`fix/*`** - Bug fixes (e.g., `fix/token-refresh-error`)
  - Branch from: `development`
  - Merge to: `development`
  - Delete after merge

- **`release/*`** - Release preparation (e.g., `release/v1.2.0`)
  - Branch from: `development`
  - Merge to: `main` AND `development`
  - Protected, requires approval
  - Delete after merge

- **`hotfix/*`** - Emergency production fixes (e.g., `hotfix/v1.1.1`)
  - Branch from: `main`
  - Merge to: `main` AND `development`
  - Protected, requires approval
  - Deploy immediately to production

### Semantic Versioning

All releases follow [Semantic Versioning 2.0.0](https://semver.org/): `vMAJOR.MINOR.PATCH`

- **MAJOR** (v2.0.0): Breaking changes, incompatible API changes
- **MINOR** (v1.2.0): New features, backward-compatible
- **PATCH** (v1.1.1): Bug fixes, backward-compatible

**Pre-release versions**:
- `v1.2.0-alpha.1` - Alpha release (internal testing)
- `v1.2.0-beta.1` - Beta release (external testing)
- `v1.2.0-rc.1` - Release candidate (final testing)

### Commit Message Conventions

Use **Conventional Commits** for automated changelog generation:

**Format**: `<type>(<scope>): <subject>`

**Types**:
- `feat:` New features (bumps MINOR version)
- `fix:` Bug fixes (bumps PATCH version)
- `docs:` Documentation only
- `style:` Code formatting (no logic change)
- `refactor:` Code restructuring (no feature change)
- `test:` Test additions/changes
- `chore:` Maintenance, dependencies
- `perf:` Performance improvements
- `ci:` CI/CD changes
- `build:` Build system changes
- `revert:` Revert previous commit

**Breaking Changes**: Use `BREAKING CHANGE:` in footer or `!` after type
```bash
feat(api)!: change authentication endpoint structure

BREAKING CHANGE: Auth endpoint moved from /auth to /api/v1/auth
```

**Examples**:
```bash
feat(providers): add Plaid provider support
fix(auth): prevent race condition in token refresh
docs(api): update endpoint documentation
test(integration): add OAuth flow tests
chore(deps): update FastAPI to 0.110.0
```

**Commit Rules**:
- ✅ Use present tense ("add" not "added")
- ✅ Use imperative mood ("move" not "moves")
- ✅ Keep subject under 72 characters
- ✅ Reference issues (e.g., "Closes #42")
- ❌ Never commit directly to `main` or `development`
- ❌ Never commit secrets or sensitive data
- ❌ Never commit incomplete work to shared branches

### Branch Protection Requirements

**CRITICAL**: Both `main` and `development` branches MUST be protected with:

✅ **Required Status Checks**:
  - `Test Suite / Run Tests` - All tests must pass
  - `Code Quality / lint` - Linting must pass
  - Branches must be up to date before merging

✅ **Required Pull Request Reviews**:
  - At least 1 approval required
  - Dismiss stale reviews on new commits
  - Require conversation resolution

✅ **Restrictions**:
  - No direct commits (PR required)
  - No force pushes
  - No branch deletion
  - Enforce for administrators (on `main`)

**Setting up branch protection** (see [Git Workflow Guide](docs/development/guides/git-workflow.md#branch-protection-rules)):
```bash
# Via GitHub Web UI: Settings → Branches → Add rule
# Or via GitHub CLI (gh) - see workflow guide
```

### Workflow Process

**Starting New Feature**:
```bash
git checkout development
git pull origin development
git checkout -b feature/my-feature
# ... make changes, commit ...
git push -u origin feature/my-feature
# Create PR to development on GitHub
```

**Creating Release**:
```bash
git checkout -b release/v1.2.0
# Update version, CHANGELOG.md
git push -u origin release/v1.2.0
# PR to main → merge → tag → merge back to development
```

**Emergency Hotfix**:
```bash
git checkout main
git checkout -b hotfix/v1.1.1
# Fix critical issue
# PR to main → merge → tag → merge to development → deploy
```

### Pull Request Process

**All PRs must**:
- ✅ Pass all automated tests (`Test Suite / Run Tests`)
- ✅ Pass linting checks (`Code Quality / lint`)
- ✅ Have at least 1 approval
- ✅ Resolve all review conversations
- ✅ Include tests for new features/fixes
- ✅ Update documentation if needed

**PR Template** (include in description):
```markdown
## Description
[Brief description of changes]

## Type of Change
- [ ] New feature
- [ ] Bug fix
- [ ] Breaking change
- [ ] Documentation

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] All tests pass (`make test`)
- [ ] Linting passes (`make lint`)

## Related Issues
Closes #XX
```

### Git Resources

**For complete Git workflow documentation, see**:
- 📚 [Git Workflow Guide](docs/development/guides/git-workflow.md) - Comprehensive guide with examples
- 📋 [Git Quick Reference](docs/development/guides/git-quick-reference.md) - One-page cheat sheet
- 🔧 [Branch Protection Setup](docs/development/guides/git-workflow.md#branch-protection-rules) - Configuration instructions

## Performance and Optimization Rules

### Database Queries
- Always use eager loading for relationships with `selectinload()`
- Avoid N+1 queries by loading related data upfront
- Use database indexes for frequently queried fields
- Implement pagination for list endpoints

### Async Best Practices
- Don't block the event loop with synchronous operations
- Use `asyncio` for concurrent operations where appropriate
- Implement connection pooling for database connections
- Set appropriate timeout values for external API calls

## Documentation Requirements

### Documentation Structure
**CRITICAL**: All documentation must follow the established structure in `docs/`. NEVER create documentation files in the root directory except for README.md and WARP.md.

**Root Directory** (Only these files):
- `README.md` - Project overview and quick start
- `WARP.md` - This file (AI agent rules and project context)
- `CONTRIBUTING.md` - Contributing guidelines (optional)

**Documentation Organization**:
```
docs/
├── README.md                  # Documentation index
├── development/               # Developer documentation
│   ├── architecture/          # System design and architecture
│   ├── infrastructure/        # Docker, CI/CD, environments
│   ├── testing/               # Testing strategy and guides
│   └── guides/                # Development how-tos
├── research/                  # Technical research and decisions
│   └── archived/              # Historical/completed work
├── setup/                     # User setup guides
├── api/                       # API documentation
└── guides/                    # User guides
```

**When to Create Documentation**:
- **Development docs** → `docs/development/[category]/filename.md`
  - Architecture decisions → `docs/development/architecture/`
  - Infrastructure setup → `docs/development/infrastructure/`
  - Testing guides → `docs/development/testing/`
  - How-to guides → `docs/development/guides/`

- **Research & decisions** → `docs/research/filename.md`
  - Technical research documents
  - Architectural decision records (ADRs)
  - Migration plans and notes
  - Archive when completed → `docs/research/archived/`

- **User-facing docs** → `docs/setup/`, `docs/api/`, or `docs/guides/`
  - Installation guides
  - API endpoint documentation
  - User tutorials and troubleshooting

**Documentation Rules**:
1. ✅ Keep root directory clean (only README.md and WARP.md)
2. ✅ Use descriptive filenames with hyphens (e.g., `oauth-flow.md`)
3. ✅ Create README.md in each major directory as an index
4. ✅ Link between related documents
5. ✅ Update `docs/README.md` index when adding new sections
6. ✅ Archive completed research/migration docs to `docs/research/archived/`
7. ❌ NEVER scatter documentation across random directories
8. ❌ NEVER create temporary summary files (SESSION_SUMMARY.md, ACCOMPLISHMENTS.md, etc.)
9. ✅ Display session summaries in terminal output instead of creating files

### Code Documentation
- Every module must have a module-level docstring
- All public functions need docstrings with parameters and return values
- Complex logic should have inline comments
- Update README.md when adding new features or endpoints

### API Documentation
- FastAPI auto-generates OpenAPI docs at `/docs`
- Ensure all endpoints have proper descriptions
- Include example requests/responses where helpful
- Document error conditions and status codes

## Monitoring and Logging Rules

### Logging Standards
- Use structured logging with appropriate levels:
  - `DEBUG`: Detailed diagnostic information
  - `INFO`: General informational messages
  - `WARNING`: Warning messages for potential issues
  - `ERROR`: Error messages for failures
- Include relevant context (user_id, provider_id, etc.)
- Never log sensitive data (tokens, passwords, secrets)

### Health Checks
- Implement health check endpoints for all services
- Check database connectivity
- Verify Redis connection
- Report degraded state if any service is down

## Future Enhancements to Consider

### Planned Features
1. Additional provider integrations (Chase, Bank of America, Fidelity)
2. Plaid integration for broader bank support
3. Account and transaction data models
4. Balance tracking and analytics
5. Web UI dashboard
6. Webhook support for real-time updates
7. Rate limiting and request throttling
8. Multi-factor authentication

### Technical Improvements
**Completed:**
1. ✅ Fixed all async database operation patterns
2. ✅ Updated all models for Pydantic v2 compatibility
3. ✅ Implemented proper environment configuration
4. ✅ Docker containerization with UV best practices
5. ✅ API documentation setup (/docs, /redoc)
6. ✅ Comprehensive test infrastructure (synchronous testing strategy)
7. ✅ Parallel dev/test/CI environments (no conflicts)
8. ✅ Docker Compose v2 migration complete
9. ✅ GitHub Actions CI/CD pipeline operational
10. ✅ Automated code quality checks (linting, formatting)
11. ✅ Branch protection with status checks
12. ✅ Health checks for all services
13. ✅ Codecov integration with automated coverage reporting
14. ✅ All tests passing (39 tests, 51% coverage)

**Pending:**
1. Expand test coverage to 85%+ (Phase 2+ of TEST_COVERAGE_PLAN.md)
   - Token service tests
   - Auth endpoint tests
   - Provider integration tests (Schwab)
   - Error handling and edge cases
2. Implement Alembic for database migrations
3. Implement API versioning strategy
4. Add request/response caching
5. Implement retry logic with exponential backoff
6. Add metrics and monitoring (Prometheus/Grafana)
7. SSL support for test environment (optional, for OAuth integration tests)

## Development Environment Setup

### Required Tools
- Docker Desktop
- Python 3.13+
- UV package manager
- Make
- Git
- OpenSSL
- curl or HTTPie for testing

### IDE Configuration
- Use type checking (mypy or Pylance)
- Enable format on save with Black
- Configure import sorting with isort
- Set line length to 88 characters (Black default)

## Contact and Resources

### Project Resources
- Repository: [Your GitHub URL]
- Documentation: See README.md
- API Docs: https://localhost:8000/docs (when running)
- Issue Tracker: [GitHub Issues]

### Key Dependencies Versions
- FastAPI: Latest
- SQLModel: Latest
- PostgreSQL: 17.6
- Redis: 8.2.1
- Python: 3.13
- UV: 0.8.22

---

## AI Agent Instructions

When working on this project:
1. Always check this WARP.md file first for project context and rules
2. Follow the established patterns for database operations (async with selectinload)
3. Maintain consistency with existing code style and structure
4. Test OAuth flows end-to-end when making auth-related changes
5. Update documentation when adding new features
6. Use the Makefile commands instead of raw Docker commands
7. Ensure all new code has proper type hints and docstrings
8. Never expose sensitive data in logs or responses
9. Always use HTTPS/SSL for all communications
10. Create audit log entries for significant operations

Remember: This is a financial data platform where security and reliability are paramount. Every decision should prioritize data protection and system stability.