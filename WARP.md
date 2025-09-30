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
- ✅ Comprehensive test coverage plan designed and ready for implementation
- 🚧 Financial data endpoints (accounts, transactions) pending implementation
- 🚧 Additional provider integrations pending
- 🚧 Test implementation pending (see TEST_COVERAGE_PLAN.md)

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

### Docker Service Names
Always use these exact service names:
- `dashtam-app` - Main FastAPI application
- `dashtam-callback` - OAuth callback server
- `dashtam-postgres` - PostgreSQL database
- `dashtam-redis` - Redis cache

### Network Configuration
- Internal Docker network name: `dashtam-network`
- Backend internal hostname: `app` (NOT `backend` or `localhost`)
- Callback server port: `8182`
- Main API port: `8000`

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
- **Comprehensive test coverage plan** available in `TEST_COVERAGE_PLAN.md`
- **Target coverage**: 85%+ overall, 95%+ for critical components
- **Test pyramid approach**: 70% unit, 20% integration, 10% e2e tests
- **Ready for implementation**: All test infrastructure designed

### Local Development Commands
Always use the Makefile for common operations:
- `make up` - Start all services
- `make down` - Stop all services
- `make logs` - View logs
- `make test` - Run tests (implementation pending)
- `make format` - Format code
- `make clean` - Clean everything

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

### Commit Messages
Use conventional commits format:
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Test additions/changes
- `chore:` Maintenance tasks

### Branch Strategy
- `main` - Production-ready code
- `develop` - Development branch
- `feature/*` - Feature branches
- `fix/*` - Bug fix branches

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
6. ✅ Comprehensive test coverage plan designed

**Pending:**
1. Implement test coverage (plan ready in TEST_COVERAGE_PLAN.md)
2. Implement Alembic for database migrations
3. Set up CI/CD pipeline
4. Implement API versioning strategy
5. Add request/response caching
6. Implement retry logic with exponential backoff
7. Add metrics and monitoring (Prometheus/Grafana)

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