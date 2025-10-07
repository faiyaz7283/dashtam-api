# Dashtam - Financial Data Aggregation Platform

[![Test Suite](https://github.com/faiyaz7283/Dashtam/workflows/Test%20Suite/badge.svg)](https://github.com/faiyaz7283/Dashtam/actions)
[![codecov](https://codecov.io/gh/faiyaz7283/Dashtam/branch/development/graph/badge.svg)](https://codecov.io/gh/faiyaz7283/Dashtam)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![Code Coverage](https://img.shields.io/badge/coverage-76%25-yellowgreen.svg)](https://codecov.io/gh/faiyaz7283/Dashtam)

A secure, modern financial data aggregation platform that connects to multiple financial institutions through OAuth2, providing a unified API for accessing accounts, transactions, and financial data.

> **Status**: Active Development | **Phase**: Financial Data API (Next) | **Test Coverage**: 76% (295 tests passing) | **REST Compliance**: 10/10

## 🚀 Features

### Core Infrastructure
- ✅ **Multi-Provider Support**: Connect to multiple financial institutions (Charles Schwab implemented)
- ✅ **OAuth2 Authentication**: Secure authentication with financial providers
- ✅ **Token Encryption**: All OAuth tokens encrypted at rest with AES-256
- ✅ **Token Rotation**: Universal token rotation detection (supports rotating and non-rotating providers)
- ✅ **HTTP Timeouts**: Configurable connection timeouts (prevents hanging requests)
- ✅ **Async Architecture**: Built with FastAPI and async/await for high performance
- ✅ **Type Safety**: Full typing with Pydantic v2 and SQLModel
- ✅ **Docker-First**: Containerized development and deployment with parallel environments
- ✅ **HTTPS Everywhere**: SSL/TLS enabled by default for all services
- ✅ **Database Migrations**: Alembic integration with automatic migrations
- ✅ **Timezone-Aware**: All datetimes use PostgreSQL TIMESTAMPTZ
- ✅ **Audit Logging**: Comprehensive audit trail for all provider operations
- ✅ **CI/CD Pipeline**: GitHub Actions with automated testing and code coverage
- ✅ **Test Coverage**: 76% coverage with 295 passing tests

### Authentication & Security
- ✅ **JWT Authentication**: Stateless JWT access tokens (30 min TTL)
- ✅ **Refresh Tokens**: Opaque refresh tokens with rotation support (30 day TTL)
- ✅ **Password Security**: bcrypt hashing with complexity requirements
- ✅ **Email Verification**: Required email verification with token-based flow
- ✅ **Password Reset**: Secure password reset with time-limited tokens
- ✅ **Account Lockout**: Brute-force protection with automatic account lockout
- ✅ **User Profile Management**: GET/PATCH /auth/me endpoints

### API Design
- ✅ **RESTful Compliance**: 100% REST-compliant API (10/10 audit score)
- ✅ **Resource-Oriented**: All endpoints follow REST principles
- ✅ **Schema Separation**: Complete Pydantic schema organization
- ✅ **Proper HTTP Methods**: GET, POST, PATCH, DELETE used correctly
- ✅ **Standard Status Codes**: Consistent HTTP status code usage
- ✅ **API Documentation**: Auto-generated OpenAPI/Swagger docs

### Next Phase
- 🚧 **Financial Data API**: Account and transaction endpoints
- 🚧 **Rate Limiting**: API rate limiting and throttling
- 🚧 **Additional Providers**: Plaid, Chase, Bank of America integrations

## 🎉 Recent Accomplishments (October 2025)

### P0 Critical Items ✅
- **Timezone-Aware Datetimes** (PR #5): Full PostgreSQL TIMESTAMPTZ implementation
- **Database Migrations** (PR #6): Alembic integration with automatic migrations in all environments

### P1 High-Priority Items ✅
- **HTTP Connection Timeouts** (PR #7): Configurable timeouts for all provider API calls
- **OAuth Token Rotation** (PR #8): Universal token rotation detection supporting both rotating and non-rotating providers
- **JWT User Authentication** (PRs #9-13): Complete JWT authentication with refresh tokens, email verification, password reset
- **REST API Compliance** (PRs #10-14): Achieved 10/10 REST compliance score with comprehensive audit

### Architecture & Documentation 📚
- **Authentication Architecture**: Comprehensive JWT authentication design (828 lines)
- **RESTful API Design**: Complete REST API architecture guide (981 lines)
- **Schema Design**: Pydantic schema organization patterns (1,133 lines)
- **Implementation Guides**: JWT auth, REST compliance implementation guides (archived after completion)
- **Code Reviews**: REST API audit achieving 10/10 compliance score

## 🗺️ Roadmap

### Phase 1: Enhanced Security (Next) 🔥
- Rate limiting (Redis-based)
- Token breach detection and rotation
- Audit log enhancements
- Secret management (Vault/AWS Secrets Manager)
- **Complexity**: Moderate

### Phase 2: Financial Data API
- Account aggregation endpoints
- Transaction history API
- Balance tracking and analytics
- Real-time data synchronization
- Account categorization
- **Complexity**: Moderate-High

### Phase 3: Provider Expansion
- Plaid integration (broad bank support)
- Chase direct integration
- Bank of America integration
- Additional brokerage providers (Fidelity, E*TRADE)
- **Complexity**: High

### Phase 4: Advanced Authentication
- Social authentication (Google, Apple)
- Passkeys / WebAuthn (passwordless)
- Multi-factor authentication (TOTP, SMS)
- Biometric support
- **Complexity**: Moderate (per feature)

### Phase 5: Advanced Features
- Budget tracking and forecasting
- Investment portfolio analysis
- Bill pay integrations
- Webhooks for real-time updates
- Mobile app (React Native)
- **Complexity**: High

## 📋 Prerequisites

- Docker and Docker Compose (v2.0+)
- Make (for convenience commands)
- OpenSSL (for SSL certificate generation)

> **Note**: All development happens in Docker containers. You do NOT need Python installed locally.

## 🛠️ Quick Start

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd Dashtam
```

### 2. Initial Setup

Run the setup command to generate SSL certificates and application keys:

```bash
make setup
```

This will:
- Generate self-signed SSL certificates for HTTPS
- Create secure encryption keys for token storage
- Create `env/.env.dev` file with secure defaults
- Create `env/.env.test` file for testing

### 3. Configure OAuth Credentials

Edit the `env/.env.dev` file and add your OAuth credentials:

```env
# Charles Schwab OAuth (get from https://developer.schwab.com/)
SCHWAB_API_KEY=your_client_id_here
SCHWAB_API_SECRET=your_client_secret_here
SCHWAB_REDIRECT_URI=https://127.0.0.1:8182
```

### 4. Start Development Environment

```bash
# Start development services
make dev-up
```

The development environment will be available at:
- **Main API**: https://localhost:8000
- **API Documentation**: https://localhost:8000/docs (Swagger UI)
- **Alternative API Docs**: https://localhost:8000/redoc (ReDoc)
- **OAuth Callback Server**: https://127.0.0.1:8182
- **Health Check**: https://localhost:8000/health

## 📦 Project Structure

```
Dashtam/
├── compose/                 # Docker Compose configurations
│   ├── docker-compose.dev.yml    # Development environment
│   ├── docker-compose.test.yml   # Test environment
│   ├── docker-compose.ci.yml     # CI/CD environment
│   └── docker-compose.prod.yml.example  # Production template
├── docker/                  # Docker configuration
│   ├── Dockerfile           # Multi-stage Dockerfile (dev, builder, production, callback)
│   └── .dockerignore        # Docker build context exclusions
├── env/                     # Environment configurations
│   ├── .env.dev             # Development variables (gitignored)
│   ├── .env.test            # Test variables (gitignored)
│   ├── .env.ci              # CI variables (committed)
│   ├── .env.example         # Template for non-production
│   ├── .env.prod.example    # Template for production
│   └── README.md            # Environment configuration guide
├── src/                     # Application source code
│   ├── api/                 # API endpoints
│   │   └── v1/              # API version 1
│   ├── core/                # Core functionality
│   │   ├── config.py        # Application configuration
│   │   ├── database.py      # Database setup
│   │   └── init_db.py       # Database initialization
│   ├── models/              # SQLModel database models
│   │   ├── base.py          # Base model classes
│   │   ├── user.py          # User model
│   │   ├── auth.py          # Authentication models
│   │   └── provider.py      # Provider models
│   ├── providers/           # Financial provider implementations
│   │   ├── base.py          # Base provider interface
│   │   ├── registry.py      # Provider registry
│   │   └── schwab.py        # Schwab implementation
│   ├── services/            # Business logic services
│   │   ├── encryption.py    # Token encryption
│   │   ├── token_service.py # Token management
│   │   ├── jwt_service.py   # JWT authentication
│   │   ├── auth_service.py  # User authentication
│   │   └── email_service.py # Email notifications
│   ├── schemas/             # Pydantic schemas
│   │   ├── auth.py          # Authentication schemas
│   │   ├── provider.py      # Provider schemas
│   │   └── common.py        # Common schemas
│   └── main.py              # FastAPI application
├── scripts/                 # Utility scripts
│   ├── generate-certs.sh    # SSL certificate generation
│   └── generate-keys.sh     # Security key generation
├── tests/                   # Test suite (295 tests, 76% coverage)
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── api/                 # API endpoint tests
├── alembic/                 # Database migrations
├── docs/                    # Documentation
│   ├── development/         # Development guides
│   └── research/            # Architecture research
├── pyproject.toml           # Project dependencies (UV)
├── uv.lock                  # Locked dependency versions
├── Makefile                 # Convenience commands
├── Makefile.workflows       # Workflow commands
└── README.md                # This file
```

## 🔧 Development

### Parallel Environments

The project supports three isolated environments that can run in parallel:

1. **Development** (`dev-*` commands) - For active development with hot reload
2. **Test** (`test-*` commands) - For running automated tests
3. **CI** (`ci-*` commands) - For continuous integration

### Available Commands

```bash
# Development Environment
make dev-up         # Start development services
make dev-down       # Stop development services
make dev-logs       # View development logs
make dev-status     # Check development service status
make dev-shell      # Open shell in dev app container
make dev-restart    # Restart development environment
make dev-rebuild    # Rebuild dev images from scratch

# Test Environment
make test-up        # Start test services
make test-down      # Stop test services
make test-status    # Check test service status
make test-rebuild   # Rebuild test images from scratch
make test-restart   # Restart test environment

# Running Tests
make test-main      # Run main test suite (305 tests, excludes smoke tests)
make test-smoke     # Run smoke tests only (5 tests, isolated session)
make test           # Run all tests (main + smoke) with coverage
make test-unit      # Run unit tests only
make test-integration # Run integration tests only
make test-verify    # Quick core functionality verification

# Code Quality (runs in dev environment)
make lint           # Run code linting (ruff check)
make format         # Format code (ruff format)

# CI/CD (run tests as they run in GitHub Actions)
make ci-test        # Run CI tests locally
make ci-build       # Build CI images
make ci-down        # Clean up CI environment

# Setup & Configuration
make certs          # Generate SSL certificates
make keys           # Generate application keys
make setup          # Run initial setup (certs + keys + env files)

# Utilities
make status-all     # Check status of all environments
make clean          # Clean up everything (all environments)

# Database Migrations (dev environment)
make migrate-up        # Run pending migrations
make migrate-down      # Rollback last migration
make migrate-create    # Create new migration
make migrate-history   # View migration history
make migrate-current   # Show current migration version

# Provider Authentication (dev environment)
make auth-schwab    # Start Schwab OAuth flow
```

### Running Tests

Tests run in an isolated test environment with three test execution modes:

```bash
# Start test environment
make test-up

# Run all tests (main + smoke in separate sessions)
make test                # 310 tests total: 305 main + 5 smoke

# Run specific test suites
make test-main           # Main test suite only (305 tests, excludes smoke)
make test-smoke          # Smoke tests only (5 tests, isolated session)
make test-unit           # Unit tests only
make test-integration    # Integration tests only
make test-verify         # Quick core functionality verification

# Stop test environment
make test-down
```

#### Test Isolation

The test suite uses **pytest markers** for isolation:

- **Main tests** (`make test-main`): Run with `-m "not smoke"` to exclude smoke tests
- **Smoke tests** (`make test-smoke`): Run with `-m smoke` in isolated pytest session
- **All tests** (`make test`): Runs main tests first, then smoke tests separately

**Why separate sessions?**
- Smoke tests validate end-to-end auth flows with persistent state
- Running in separate sessions prevents database state conflicts
- Provides clearer test output and better debugging
- CI/CD shows progress for both suites independently

### Code Quality

```bash
# Format code
make format

# Check linting
make lint

# Run both in CI mode locally
make ci-test
```

### Development Workflow

```bash
# 1. Start development environment
make dev-up

# 2. Make changes to code (hot reload is enabled)

# 3. Run tests in parallel (different ports)
make test-up
make test

# 4. Check code quality
make lint
make format

# 5. Clean up when done
make dev-down
make test-down
```

## 🏗️ Architecture

### Technology Stack

- **Backend Framework**: FastAPI
- **Database**: PostgreSQL 17.6 with SQLModel ORM
- **Cache**: Redis 8.2.1
- **Authentication**: OAuth2 + JWT with encrypted token storage
- **Package Management**: UV (uv sync --frozen for fast, deterministic builds)
- **Containerization**: Docker & Docker Compose with multi-stage builds
- **Security**: Non-root containers (appuser, UID 1000) for all environments

### Key Components

1. **Provider Registry**: Dynamic provider registration system
2. **Token Service**: Secure token storage and refresh management
3. **Encryption Service**: AES encryption for sensitive data
4. **Audit Logging**: Comprehensive activity tracking

### Database Schema

The platform uses the following main tables:
- `users`: Application users
- `providers`: User's provider connections
- `provider_connections`: Connection status and sync tracking
- `provider_tokens`: Encrypted OAuth tokens
- `provider_audit_logs`: Audit trail of all operations

## 🚀 CI/CD

### GitHub Actions

The project uses GitHub Actions for continuous integration:

- **Automated Testing**: Runs on every push to `development` branch
- **Code Quality Checks**: Linting and formatting enforcement
- **Branch Protection**: Development branch requires passing checks before merge
- **Coverage Reporting**: Integrated with Codecov (when tests pass)

### Workflow Status

- ✅ **Code Quality**: Automated linting (ruff) and formatting checks
- ✅ **Test Coverage**: 122 tests passing, 68% code coverage
- ✅ **Branch Protection**: Development branch protected with required checks
- ✅ **Coverage Reporting**: Codecov integration active

### Local CI Testing

Test your changes exactly as they'll run in CI:

```bash
# Run full CI test suite locally
make ci-test

# Check status
make ci-down
```

### Branch Protection

The `development` branch is protected with:
- Required status checks (Code Quality must pass)
- Pull request reviews recommended
- Branch must be up to date before merging

## 🔐 Security

### Current Security Features
- ✅ **HTTPS Everywhere**: All services use SSL/TLS (self-signed in dev, proper certs in prod)
- ✅ **Token Encryption**: OAuth tokens encrypted using AES-256 before storage
- ✅ **Secure Key Generation**: Cryptographically secure key generation scripts
- ✅ **Token Rotation**: Universal token rotation detection (rotating and non-rotating providers)
- ✅ **HTTP Timeouts**: Configurable timeouts prevent hanging requests and DoS
- ✅ **Audit Trail**: All provider operations logged with IP and user agent
- ✅ **Environment Isolation**: Separate dev, test, and CI environments (no conflicts)
- ✅ **Timezone-Aware Storage**: All timestamps use PostgreSQL TIMESTAMPTZ

### Planned Security Enhancements
- 🚧 **Rate Limiting**: API rate limiting and throttling
- 🚧 **MFA**: Multi-factor authentication support
- 🚧 **Passkeys**: WebAuthn/FIDO2 passwordless authentication

## 🌐 API Documentation

### Manual Testing & API Flows

For hands-on, HTTPS-first manual testing guides with copy-paste examples, see:
- **[API Flows Documentation](docs/api-flows/)** - Complete manual testing guides
- **[Authentication Flows](docs/api-flows/auth/)** - Registration, login, password reset
- **[Provider Flows](docs/api-flows/providers/)** - Provider onboarding and OAuth
- **[Complete Auth Flow](docs/api-flows/auth/complete-auth-flow.md)** - End-to-end smoke test

### Development Mode: Email Token Extraction

**Important for development/testing**: In development mode (`DEBUG=True`), emails are **logged to console** instead of sent via AWS SES.

**To extract verification/reset tokens from logs:**

```bash
# View recent email logs
docker logs dashtam-dev-app --tail 100 2>&1 | grep -A 20 '📧 EMAIL'

# Look for URLs containing tokens:
# https://localhost:3000/verify-email?token=YOUR_TOKEN_HERE
# https://localhost:3000/reset-password?token=YOUR_TOKEN_HERE

# Extract and use the token
export VERIFICATION_TOKEN="<token-from-logs>"
export RESET_TOKEN="<token-from-logs>"
```

**Why this works**: No AWS credentials needed in dev! The `EmailService` automatically detects `DEBUG=True` and logs emails with full content including tokens.

See individual flow guides for detailed examples: [docs/api-flows/auth/](docs/api-flows/auth/)

### Base URL
```
https://localhost:8000/api/v1
```

### Available Endpoints

#### System & Health
- `GET /` - Root endpoint with API information
- `GET /health` - Health check endpoint
- `GET /api/v1/health` - API version health check

#### Provider Management
- `GET /api/v1/providers/available` - List all available provider types
- `GET /api/v1/providers/configured` - List configured providers ready to use
- `POST /api/v1/providers/create` - Create a new provider instance
- `GET /api/v1/providers/` - List user's provider instances
- `GET /api/v1/providers/{provider_id}` - Get specific provider details
- `DELETE /api/v1/providers/{provider_id}` - Delete a provider instance

#### OAuth Authentication
- `GET /api/v1/auth/{provider_id}/authorize` - Get OAuth authorization URL
- `GET /api/v1/auth/{provider_id}/authorize/redirect` - Redirect to OAuth page
- `GET /api/v1/auth/{provider_id}/callback` - Handle OAuth callback (internal)
- `POST /api/v1/auth/{provider_id}/refresh` - Manually refresh tokens
- `GET /api/v1/auth/{provider_id}/status` - Get token status
- `DELETE /api/v1/auth/{provider_id}/disconnect` - Disconnect provider

#### User Authentication ✅
- `POST /api/v1/auth/register` - Create new user account
- `POST /api/v1/auth/verify-email` - Verify email address
- `POST /api/v1/auth/login` - Login with email/password (returns JWT tokens)
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - Logout and revoke refresh token
- `GET /api/v1/auth/me` - Get current user profile
- `PATCH /api/v1/auth/me` - Update user profile
- `POST /api/v1/password-resets` - Request password reset
- `GET /api/v1/password-resets/{token}` - Verify reset token
- `PATCH /api/v1/password-resets/{token}` - Complete password reset with new password

**Manual Testing Guides**: See [Authentication Flows](docs/api-flows/auth/) for copy-paste examples

#### Financial Data (Coming Soon)
- `GET /api/v1/accounts` - Get all connected accounts
- `GET /api/v1/accounts/{account_id}` - Get specific account details
- `GET /api/v1/transactions` - Get transactions across all accounts
- `GET /api/v1/balances` - Get account balances

### 🔐 Complete OAuth Connection Flow

#### Step 1: Create a Provider Instance

First, create a provider instance for the user. This doesn't connect to the provider yet, it just creates a record in your system.

```bash
curl -X POST https://localhost:8000/api/v1/providers/create \
  -H "Content-Type: application/json" \
  -d '{
    "provider_key": "schwab",
    "alias": "My Schwab Account"
  }' \
  --insecure
```

**Response:**
```json
{
  "id": "81f8773a-3e63-4003-8206-d1e0fb1dba6c",
  "provider_key": "schwab",
  "alias": "My Schwab Account",
  "status": "pending",
  "is_connected": false,
  "needs_reconnection": true,
  "connected_at": null,
  "last_sync_at": null,
  "accounts_count": 0
}
```

Save the `id` field - you'll need it for the next steps.

#### Step 2: Get Authorization URL

Use the provider ID to get the OAuth authorization URL:

```bash
curl https://localhost:8000/api/v1/auth/{provider_id}/authorize \
  --insecure
```

Replace `{provider_id}` with the ID from Step 1.

**Response:**
```json
{
  "auth_url": "https://api.schwabapi.com/v1/oauth/authorize?...",
  "message": "Visit this URL to authorize My Schwab Account"
}
```

#### Step 3: Authorize with Provider

1. Copy the `auth_url` from the response
2. Open it in your web browser
3. Log in to your Schwab account
4. Review and approve the permissions
5. You'll be redirected to `https://127.0.0.1:8182`

**Note**: Your browser will show a security warning about the self-signed certificate. This is expected. Click "Advanced" and "Proceed to 127.0.0.1 (unsafe)".

#### Step 4: OAuth Callback

The callback server automatically:
1. Receives the authorization code from Schwab
2. Forwards it to the main API
3. Exchanges the code for access/refresh tokens
4. Stores tokens securely (encrypted)
5. Shows a success page

#### Step 5: Verify Connection

Check that the provider is now connected:

```bash
curl https://localhost:8000/api/v1/providers/{provider_id} \
  --insecure | python3 -m json.tool
```

**Response:**
```json
{
  "id": "81f8773a-3e63-4003-8206-d1e0fb1dba6c",
  "provider_key": "schwab",
  "alias": "My Schwab Account",
  "status": "connected",
  "is_connected": true,
  "needs_reconnection": false,
  "connected_at": "2024-01-24T12:00:00",
  "last_sync_at": null,
  "accounts_count": 0
}
```

### 🔍 Interactive API Documentation

FastAPI provides automatic interactive API documentation. When running in development mode:

- **Swagger UI**: https://localhost:8000/docs
- **ReDoc**: https://localhost:8000/redoc

These interfaces allow you to:
- Browse all available endpoints
- See request/response schemas
- Test endpoints directly from the browser
- View detailed parameter descriptions

### 📝 API Examples

#### List Available Providers
```bash
curl https://localhost:8000/api/v1/providers/available \
  --insecure | python3 -m json.tool
```

#### List Your Connected Providers
```bash
curl https://localhost:8000/api/v1/providers/ \
  --insecure | python3 -m json.tool
```

#### Check Token Status
```bash
curl https://localhost:8000/api/v1/auth/{provider_id}/status \
  --insecure | python3 -m json.tool
```

#### Manually Refresh Tokens
```bash
curl -X POST https://localhost:8000/api/v1/auth/{provider_id}/refresh \
  --insecure
```

#### Disconnect a Provider
```bash
curl -X DELETE https://localhost:8000/api/v1/auth/{provider_id}/disconnect \
  --insecure
```

#### Delete a Provider Instance
```bash
curl -X DELETE https://localhost:8000/api/v1/providers/{provider_id} \
  --insecure
```

### 🔧 Testing with Curl

For all HTTPS requests in development, use the `--insecure` flag to bypass SSL certificate verification:

```bash
curl --insecure https://localhost:8000/api/v1/health
```

For pretty JSON output, pipe to Python:

```bash
curl --insecure https://localhost:8000/api/v1/providers/available | python3 -m json.tool
```

## 🚢 Deployment

### Production Considerations

1. **Environment Variables**: Use a secure secrets manager
2. **SSL Certificates**: Use proper certificates from a CA
3. **Database**: Use managed PostgreSQL service
4. **Redis**: Use managed Redis service
5. **Monitoring**: Add application monitoring (Datadog, New Relic, etc.)
6. **Backup**: Implement database backup strategy

### Docker Production Build

```bash
docker build --target production -f docker/Dockerfile -t dashtam:prod .
```

## 📝 Configuration

### Environment Variables

Key environment variables (see `.env.example` for full list):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `SECRET_KEY` | Application secret key | Auto-generated |
| `ENCRYPTION_KEY` | Token encryption key | Auto-generated |
| `SCHWAB_API_KEY` | Schwab OAuth client ID | None |
| `SCHWAB_API_SECRET` | Schwab OAuth client secret | None |
| `DEBUG` | Enable debug mode | `false` |

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## 📄 License

[Your License Here]

## 🆘 Troubleshooting

### OAuth Flow Issues

**"Invalid host header" Error**
- This occurs when the TrustedHostMiddleware blocks requests
- Solution: Ensure Docker services are running properly
- The fix is already applied in the codebase

**"greenlet_spawn has not been called" Error**
- This is an async SQLAlchemy error
- Happens when relationships aren't properly loaded
- Solution: Restart the backend service
  ```bash
  docker restart dashtam-app
  ```

**Callback Server Not Receiving OAuth Callback**
- Check if callback server is running:
  ```bash
  docker logs dashtam-callback
  ```
- Ensure SSL certificates exist:
  ```bash
  ls -la certs/
  ```
- Verify redirect URI matches exactly: `https://127.0.0.1:8182`

**"Connection Error" from Callback Server**
- This means the callback server can't reach the backend
- Check both services are running:
  ```bash
  docker ps | grep dashtam
  ```
- Check backend logs:
  ```bash
  docker logs dashtam-app --tail 50
  ```

### Common Issues

**Port Already in Use**
```bash
# Check what's using the ports
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis
lsof -i :8000  # Main app
lsof -i :8182  # Callback server

# Clean up everything
make clean
```

**SSL Certificate Issues**
```bash
# Regenerate certificates
rm -rf certs/*.pem
make certs
```

**Database Connection Issues**
```bash
# Check database logs
docker logs dashtam-postgres

# Recreate database
make clean
make up
```

**Token Encryption Issues**
```bash
# Regenerate encryption keys (WARNING: will invalidate existing tokens)
make keys
make restart
```

**Provider Not Showing as Connected**
1. Check the provider status:
   ```bash
   curl https://localhost:8000/api/v1/providers/{provider_id} --insecure
   ```
2. Check token status:
   ```bash
   curl https://localhost:8000/api/v1/auth/{provider_id}/status --insecure
   ```
3. Try manually refreshing tokens:
   ```bash
   curl -X POST https://localhost:8000/api/v1/auth/{provider_id}/refresh --insecure
   ```

## 📞 Support

For issues, questions, or contributions, please open an issue on GitHub.

## 🎯 Roadmap

- [ ] Add more financial providers (Chase, Bank of America, Fidelity)
- [ ] Implement Plaid integration
- [ ] Add transaction categorization
- [ ] Build web UI dashboard
- [ ] Add portfolio analytics
- [ ] Implement real-time notifications
- [ ] Add export functionality (CSV, JSON, etc.)
