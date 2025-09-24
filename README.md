# Dashtam - Financial Data Aggregation Platform

A secure, modern financial data aggregation platform that connects to multiple financial institutions through OAuth2, providing a unified API for accessing accounts, transactions, and financial data.

## 🚀 Features

- **Multi-Provider Support**: Connect to multiple financial institutions (starting with Charles Schwab)
- **OAuth2 Authentication**: Secure authentication with financial providers
- **Encrypted Token Storage**: All OAuth tokens are encrypted at rest
- **Async Architecture**: Built with FastAPI and async/await for high performance
- **Type Safety**: Full typing with Pydantic and SQLModel
- **Docker-First**: Containerized development and deployment
- **HTTPS Everywhere**: SSL/TLS enabled by default for all services
- **Audit Logging**: Comprehensive audit trail for all provider operations

## 📋 Prerequisites

- Docker and Docker Compose
- Python 3.13+ (for local development)
- Make (for convenience commands)
- OpenSSL (for certificate generation)

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
- Create a `.env` file with secure defaults

### 3. Configure OAuth Credentials

Edit the `.env` file and add your OAuth credentials:

```env
# Charles Schwab OAuth (get from https://developer.schwab.com/)
SCHWAB_API_KEY=your_client_id_here
SCHWAB_API_SECRET=your_client_secret_here
SCHWAB_REDIRECT_URI=https://127.0.0.1:8182
```

### 4. Build and Start Services

```bash
# Build Docker images
make build

# Start all services
make up
```

The platform will be available at:
- **Main API**: https://localhost:8000
- **OAuth Callback Server**: https://127.0.0.1:8182

## 📦 Project Structure

```
Dashtam/
├── docker/                  # Docker configuration
│   └── Dockerfile           # Multi-stage Dockerfile
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
│   │   └── provider.py      # Provider models
│   ├── providers/           # Financial provider implementations
│   │   ├── base.py          # Base provider interface
│   │   ├── registry.py      # Provider registry
│   │   └── schwab.py        # Schwab implementation
│   ├── services/            # Business logic services
│   │   ├── encryption.py    # Token encryption
│   │   └── token_service.py # Token management
│   └── main.py              # FastAPI application
├── scripts/                 # Utility scripts
│   ├── generate-certs.sh    # SSL certificate generation
│   └── generate-keys.sh     # Security key generation
├── tests/                   # Test suite
├── alembic/                 # Database migrations
├── requirements.txt         # Python dependencies
├── requirements-dev.txt     # Development dependencies
├── docker-compose.yml       # Docker services configuration
├── Makefile                 # Convenience commands
└── .env.example             # Environment variables template
```

## 🔧 Development

### Available Commands

```bash
# Docker Management
make up         # Start all services
make down       # Stop all services
make restart    # Restart all services
make build      # Rebuild Docker images
make logs       # View application logs
make status     # Check service status
make clean      # Clean up everything (containers, volumes, images)

# Development Tools
make dev        # Start in development mode with hot reload
make shell      # Open shell in app container
make db-shell   # Open PostgreSQL shell
make redis-cli  # Open Redis CLI

# Setup & Configuration
make certs      # Generate SSL certificates
make keys       # Generate application keys
make setup      # Run initial setup (certs + keys)

# Code Quality
make test       # Run tests
make lint       # Run linters
make format     # Format code

# Database
make migrate    # Run database migrations
make migration  # Create new migration

# Provider Authentication
make auth-schwab # Start Schwab OAuth flow
```

### Running Tests

```bash
make test
```

### Code Formatting

```bash
make format
```

## 🏗️ Architecture

### Technology Stack

- **Backend Framework**: FastAPI
- **Database**: PostgreSQL with SQLModel ORM
- **Cache**: Redis
- **Authentication**: OAuth2 with encrypted token storage
- **Package Management**: UV
- **Containerization**: Docker & Docker Compose

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

## 🔐 Security

- **HTTPS Only**: All services use SSL/TLS
- **Encrypted Storage**: OAuth tokens are encrypted using AES-256
- **Secure Keys**: Cryptographically secure key generation
- **Token Rotation**: Automatic token refresh with rotation support
- **Audit Trail**: All provider operations are logged

## 🌐 API Documentation

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
