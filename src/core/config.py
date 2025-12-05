"""
Configuration management using Pydantic Settings.

This module provides type-safe, validated configuration loading from environment
variables. Docker compose specifies which .env file to use per environment.

Architecture:
- Flat Settings structure (no nesting)
- All config loaded from environment variables
- Type validation via Pydantic
- No hard-coded values per checklist Section 22

Usage:
    from src.core.config import settings

    # Access config
    db_url = settings.database_url
    api_key = settings.schwab_api_key

    # Environment detection
    if settings.is_development:
        # Dev-specific behavior
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.enums import Environment


class Settings(BaseSettings):
    """
    Main application settings (flat structure).

    Loads configuration from environment variables.
    Docker compose specifies which .env file to use via env_file directive.

    Configuration precedence:
        1. Environment variables (set by Docker compose from .env files)
        2. Default values (only for non-sensitive config)

    Returns:
        Settings: Application configuration loaded from environment.
    """

    # Environment detection
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment (development, testing, ci, production)",
    )

    # Core application settings
    debug: bool = Field(
        default=False,
        description="Enable debug mode (verbose logging, detailed errors)",
    )
    host: str = Field(
        default="0.0.0.0",
        description="Server bind host",
    )
    port: int = Field(
        default=8000,
        description="Server bind port",
    )
    reload: bool = Field(
        default=False,
        description="Enable auto-reload on code changes (development only)",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    aws_region: str = Field(
        default="us-east-1",
        description="AWS region for cloud services (e.g., CloudWatch)",
    )
    instance_id: str | None = Field(
        default=None,
        description="Instance identifier for log stream naming. Defaults to hostname if not set. "
        "In AWS EC2, can be set to the instance ID (e.g., i-0123456789abcdef0).",
    )

    # Application metadata
    app_name: str = Field(
        default="Dashtam",
        description="Application name",
    )
    app_version: str = Field(
        default="0.1.0",
        description="Application version",
    )

    # Database configuration
    database_url: str = Field(
        description="Database connection URL (e.g., postgresql+asyncpg://user:pass@host:port/db)",
    )
    db_echo: bool = Field(
        default=False,
        description="Log all SQL queries (useful for debugging, disabled in production)",
    )

    # Cache configuration (Redis)
    redis_url: str = Field(
        description="Redis connection URL (e.g., redis://host:port/db)",
    )

    # Security configuration
    secret_key: str = Field(
        description="Secret key for JWT token signing (must be kept secure)",
    )
    encryption_key: str = Field(
        description="Encryption key for sensitive data (32 characters for AES-256)",
    )
    algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    access_token_expire_minutes: int = Field(
        default=30,
        description="Access token expiration time in minutes",
    )
    refresh_token_expire_days: int = Field(
        default=30,
        description="Refresh token expiration time in days",
    )
    bcrypt_rounds: int = Field(
        default=12,
        description="Number of bcrypt hashing rounds (10-14 recommended, 12 = ~300ms)",
    )

    # API configuration
    api_base_url: str = Field(
        description="API base URL (e.g., https://dashtam.local)",
    )
    api_v1_prefix: str = Field(
        default="/api/v1",
        description="API v1 route prefix",
    )
    callback_base_url: str = Field(
        description="OAuth callback server base URL (e.g., https://127.0.0.1:8182)",
    )
    verification_url_base: str = Field(
        description="Base URL for email verification links (e.g., https://dashtam.local)",
    )

    # CORS configuration
    cors_origins: str = Field(
        description="Allowed CORS origins (comma-separated)",
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="Allow cookies and authentication headers in CORS requests",
    )

    # Provider configuration (optional placeholders for F4.x)
    schwab_api_key: str | None = Field(
        default=None,
        description="Schwab API client ID (OAuth) - optional until Provider phase",
    )
    schwab_api_secret: str | None = Field(
        default=None,
        description="Schwab API client secret (OAuth) - optional until Provider phase",
    )
    schwab_api_base_url: str = Field(
        default="https://api.schwabapi.com",
        description="Schwab API base URL",
    )
    schwab_redirect_uri: str | None = Field(
        default=None,
        description="OAuth redirect URI for Schwab callback",
    )

    model_config = SettingsConfigDict(
        # env_file handled by Docker compose (not coupled to specific environment)
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("bcrypt_rounds")
    @classmethod
    def validate_bcrypt_rounds(cls, v: int) -> int:
        """
        Validate bcrypt rounds are within safe range.

        Args:
            v: Number of bcrypt rounds.

        Returns:
            int: Validated bcrypt rounds.

        Raises:
            ValueError: If rounds are not between 4 and 31.
        """
        if not 4 <= v <= 31:
            raise ValueError("bcrypt_rounds must be between 4 and 31")
        return v

    @field_validator("api_base_url", "callback_base_url", "verification_url_base")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """
        Remove trailing slashes from URLs.

        Args:
            v: URL string.

        Returns:
            str: URL without trailing slash.
        """
        return v.rstrip("/")

    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, v: str) -> list[str]:
        """
        Parse comma-separated CORS origins.

        Args:
            v: Comma-separated origins string.

        Returns:
            list[str]: List of origin URLs.
        """
        return [origin.strip() for origin in v.split(",")]

    # Convenience properties for environment checks
    @property
    def is_development(self) -> bool:
        """
        Check if running in development environment.

        Returns:
            bool: True if environment is DEVELOPMENT, False otherwise.
        """
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        """
        Check if running in testing environment.

        Returns:
            bool: True if environment is TESTING, False otherwise.
        """
        return self.environment == Environment.TESTING

    @property
    def is_ci(self) -> bool:
        """
        Check if running in CI environment.

        Returns:
            bool: True if environment is CI, False otherwise.
        """
        return self.environment == Environment.CI

    @property
    def is_production(self) -> bool:
        """
        Check if running in production environment.

        Returns:
            bool: True if environment is PRODUCTION, False otherwise.
        """
        return self.environment == Environment.PRODUCTION

    @classmethod
    def from_secrets_manager(
        cls,
        secrets: "SecretsProtocol",  # type: ignore  # noqa: F821
    ) -> "Settings":
        """
        Load settings from secrets manager (production environments).

        This method loads all secrets from a backend (AWS Secrets Manager,
        HashiCorp Vault, etc.) instead of environment variables.

        Args:
            secrets: Secrets manager implementing SecretsProtocol.

        Returns:
            Settings: Configuration loaded from secrets backend.

        Raises:
            SecretsError: If required secrets are missing or inaccessible.

        Example:
            >>> from src.core.container import get_secrets
            >>> secrets = get_secrets()  # Returns AWS/Vault adapter
            >>> settings = Settings.from_secrets_manager(secrets)
            >>> # All config loaded from secrets backend
        """
        from src.core.result import Success

        # Load secrets with error handling
        def get_required(path: str) -> str:
            result = secrets.get_secret(path)
            if isinstance(result, Success):
                value: str = result.value  # Type annotation for mypy
                return value
            raise ValueError(f"Required secret not found: {path}")

        def get_optional(path: str) -> str | None:
            result = secrets.get_secret(path)
            if isinstance(result, Success):
                value: str = result.value  # Type annotation for mypy
                return value
            return None

        # Build settings from secrets
        return cls(
            # Core settings (still from env)
            environment=Environment.PRODUCTION,  # Override to production
            # Database
            database_url=get_required("database/url"),
            # Cache
            redis_url=get_required("cache/redis_url"),
            # Security
            secret_key=get_required("security/secret_key"),
            encryption_key=get_required("security/encryption_key"),
            # API
            api_base_url=get_required("api/base_url"),
            callback_base_url=get_required("api/callback_base_url"),
            verification_url_base=get_required("api/verification_url_base"),
            # CORS
            cors_origins=get_required("api/cors_origins"),
            # Providers (optional)
            schwab_api_key=get_optional("providers/schwab/api_key"),
            schwab_api_secret=get_optional("providers/schwab/api_secret"),
            schwab_redirect_uri=get_optional("providers/schwab/redirect_uri"),
        )


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are loaded only once per process.
    This is important for performance and consistency.

    Returns:
        Settings: Cached settings instance.
    """
    return Settings()  # type: ignore[call-arg]  # Pydantic Settings loads from env


# Global settings instance (singleton pattern)
settings = get_settings()
