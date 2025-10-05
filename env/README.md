# Environment Configuration

This directory contains environment-specific configuration files for the Dashtam platform.

## 📁 File Structure

```
env/
├── .env.dev              # Development environment (gitignored)
├── .env.test             # Test environment (gitignored)
├── .env.ci               # CI environment (committed, no secrets)
├── .env.example          # Non-production template
├── .env.prod.example     # Production template
└── README.md             # This file
```

## 🔧 Environment Files

### `.env.dev` - Development Environment
- **Purpose**: Local development with hot-reload and debug mode
- **Git Status**: ❌ Gitignored (contains secrets)
- **Usage**: `make dev-up`
- **Features**:
  - DEBUG mode enabled
  - Verbose logging
  - HTTPS with self-signed certificates
  - Hot-reload enabled

### `.env.test` - Test Environment  
- **Purpose**: Isolated testing with ephemeral storage
- **Git Status**: ❌ Gitignored (contains test secrets)
- **Usage**: `make test-up`
- **Features**:
  - Separate ports (8001, 5433, 6380)
  - Ephemeral tmpfs storage
  - Mock external providers
  - Test-specific configurations

### `.env.ci` - CI/CD Environment
- **Purpose**: Automated testing in GitHub Actions
- **Git Status**: ✅ Committed (no real secrets)
- **Usage**: Automatic in GitHub Actions
- **Features**:
  - Speed-optimized PostgreSQL settings
  - No port mappings (internal only)
  - Mock credentials only
  - Minimal logging

### `.env.example` - Non-Production Template
- **Purpose**: Template for creating dev/test environments
- **Git Status**: ✅ Committed
- **Usage**: Copy to create new env files
- **Contains**: All required variables with safe defaults

### `.env.prod.example` - Production Template
- **Purpose**: Template for production deployment
- **Git Status**: ✅ Committed
- **Usage**: Copy and fill with production secrets
- **Contains**: All required variables with placeholder values

## 🚀 Quick Start

### First-Time Setup

```bash
# 1. Copy example file to create your dev environment
cp env/.env.example env/.env.dev

# 2. Edit with your actual credentials
nano env/.env.dev  # or use your preferred editor

# 3. Add your Schwab OAuth credentials
# SCHWAB_API_KEY=your_actual_key
# SCHWAB_API_SECRET=your_actual_secret

# 4. Generate secure keys (if not already done)
make keys

# 5. Start development environment
make dev-up
```

### For Testing

```bash
# Test environment is pre-configured with safe defaults
# No manual setup needed!
make test-up
```

## 🔐 Security Best Practices

### DO ✅
- Keep `.env.dev`, `.env.test`, and `.env.prod` in `.gitignore`
- Use `.env.example` files as templates
- Rotate secrets regularly
- Use different secrets for each environment
- Store production secrets in a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)
- Use `env_file` in docker-compose (already configured)

### DON'T ❌
- Never commit files containing real secrets
- Never share `.env.dev` or `.env.prod` files
- Never use production credentials in development
- Never hardcode secrets in docker-compose files
- Never use `.env.ci` secrets in production

## 📊 Environment Priority

Docker Compose loads environment variables in this order (highest to lowest priority):

1. **Environment variables** set in your shell
2. **`env_file`** specified in docker-compose.yml
3. **Default values** in application code

```yaml
# In docker-compose files
services:
  app:
    env_file:
      - ../env/.env.dev  # Variables loaded from this file
    environment:
      # Individual overrides (highest priority)
      LOG_LEVEL: DEBUG
```

## 🔑 Required Variables

### Core Application
```bash
# Application
APP_NAME=Dashtam
APP_VERSION=0.1.0
ENVIRONMENT=development|testing|production
DEBUG=true|false

# Security
SECRET_KEY=<generate-with-make-keys>
ENCRYPTION_KEY=<generate-with-make-keys>

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
DB_ECHO=false

# Redis
REDIS_URL=redis://host:port/db
```

### Provider Credentials
```bash
# Charles Schwab
SCHWAB_API_KEY=<your-schwab-client-id>
SCHWAB_API_SECRET=<your-schwab-secret>
SCHWAB_API_BASE_URL=https://api.schwabapi.com
SCHWAB_REDIRECT_URI=https://127.0.0.1:8182
```

### Email (AWS SES)
```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=<your-aws-key>
AWS_SECRET_ACCESS_KEY=<your-aws-secret>

# Email Settings
SES_FROM_EMAIL=noreply@dashtam.com
SES_FROM_NAME=Dashtam
```

## 🛠️ How It Works

### Docker Compose Integration

Our docker-compose files use `env_file` to load environment variables:

```yaml
services:
  app:
    env_file:
      - ../env/.env.dev  # Path relative to compose/ directory
    # No hardcoded environment: block needed!
```

### Pydantic Settings

The application reads environment variables automatically via Pydantic:

```python
# src/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Dashtam"
    SECRET_KEY: str
    # ... other settings
    
    model_config = SettingsConfigDict(
        case_sensitive=True,
        extra="ignore"
    )
```

Docker Compose loads variables from `.env` files → Pydantic reads them from the container's environment → Application uses them.

## 🧪 Testing

### Verify Environment Loading

```bash
# Check which variables are loaded
make dev-shell
env | grep -E "SCHWAB|SECRET|DATABASE" | sort
```

### Test Different Environments

```bash
# Development
make dev-up
make dev-logs

# Test
make test-up  
make test

# CI (local simulation)
make ci-test
```

## 🔄 Migration from Old Structure

If you're migrating from the old structure where `.env` files were in the root:

```bash
# Old structure (deprecated)
.env.dev           # ❌ Root directory
docker-compose.dev.yml  # ❌ Root directory

# New structure (current)
env/.env.dev       # ✅ env/ directory
compose/docker-compose.dev.yml  # ✅ compose/ directory
```

The Makefile has been updated to use the new paths automatically.

## 📚 Additional Resources

- [Docker Compose env_file documentation](https://docs.docker.com/compose/environment-variables/)
- [Pydantic Settings documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [12-Factor App: Config](https://12factor.net/config)

## 🆘 Troubleshooting

### "Environment variable not found"
- Check that the variable exists in your `.env.dev` file
- Ensure the file is properly formatted (KEY=value, no spaces around =)
- Verify the env_file path in docker-compose is correct
- Rebuild containers: `make dev-rebuild`

### "Connection refused" errors
- Check DATABASE_URL and REDIS_URL point to correct hostnames
- In Docker, use service names (postgres, redis) not localhost
- Verify ports are correct for your environment

### "Permission denied" on files
- All files should be owned by your user (not root)
- The non-root user in containers (appuser) has UID 1000
- Check file permissions: `ls -la env/`

### "Cannot find .env file"
- Makefile expects files in `env/` directory
- Ensure you've copied `.env.example` to `.env.dev`
- Check that the file isn't named `.env.dev.txt` or similar

---

**Last Updated**: 2025-10-05
**Maintained By**: Dashtam Development Team
