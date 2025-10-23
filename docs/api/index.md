# API Reference

Auto-generated API documentation for Dashtam's Python codebase.

This API reference is generated from Google-style docstrings in the source code using mkdocstrings. It provides complete documentation for all internal classes, functions, and methods.

## What's Documented Here

This section documents the **internal Python API** - the classes, services, and utilities that make up Dashtam's backend. If you're looking for the **REST API** (HTTP endpoints), see `/docs` or `/redoc` when running the application.

### For Developers

Use this reference to:

- Understand service layer architecture (`AuthService`, `TokenService`, etc.)
- Learn about database models (`User`, `Provider`, `Token`)
- Explore utility functions (encryption, validation, etc.)
- See complete method signatures and parameters
- Understand return types and exceptions

## Sections

### [Services](services.md)

Business logic and service layer classes:

- `AuthService` - User authentication and registration
- `TokenService` - OAuth token management
- `PasswordService` - Password hashing and validation
- `JWTService` - JWT token generation and validation
- `EmailService` - Email sending via AWS SES
- `EncryptionService` - Token encryption/decryption

### [Models](models.md)

SQLModel database models:

- `User` - User accounts and authentication
- `Provider` - OAuth provider connections
- `Token` - OAuth access/refresh tokens
- `RefreshToken` - User refresh tokens
- `ProviderAuditLog` - Audit trail

### [Core](core.md)

Core utilities and configuration:

- `Settings` - Application configuration
- Database session management
- Core initialization utilities

## Quick Links

**Related Documentation:**

- [FastAPI Documentation](https://fastapi.tiangolo.com/) - Web framework reference
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/) - ORM patterns
- [Pydantic Documentation](https://docs.pydantic.dev/) - Data validation

**Project Documentation:**

- [Architecture Overview](../development/architecture/overview.md) - System design
- [Testing Strategy](../testing/strategy.md) - Testing approach
- [Development Guides](../development/guides/index.md) - How-to guides
