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

import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.constants import BCRYPT_ROUNDS_DEFAULT
from src.core.enums import Environment


@lru_cache(maxsize=1)
def _get_version_from_pyproject() -> str:
    """
    Read application version from pyproject.toml.

    This ensures version is managed in a single source of truth.
    The function is cached to avoid repeated file I/O.

    Returns:
        str: Application version (e.g., "1.0.0").

    Raises:
        FileNotFoundError: If pyproject.toml is not found.
        KeyError: If version is not defined in pyproject.toml.
    """
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        pyproject = tomllib.load(f)
    version: str = pyproject["project"]["version"]
    return version


class Settings(BaseSettings):
    """
    Main application settings (flat structure).

    Loads configuration from environment variables.
    Docker compose specifies which .env file to use via env_file directive.

    Configuration precedence:
        1. Environment variables (set by Docker compose from .env files)
        2. Default values (only for non-sensitive config)
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
        default_factory=_get_version_from_pyproject,
        description="Application version (read from pyproject.toml)",
    )

    # Event System Configuration (F7.7: Domain Events Compliance)
    events_strict_mode: bool = Field(
        default=True,
        description="Event handler strict mode. When True, fails fast if required handlers missing. "
        "When False, skips missing handlers gracefully (logs warning). "
        "Default: True (production safety - catches missing handlers at startup).",
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
    cache_key_prefix: str = Field(
        default="dashtam",
        description="Cache key prefix for namespacing (prevents collisions with other apps)",
    )
    cache_user_ttl: int = Field(
        default=300,
        description="User data cache TTL in seconds (default: 5 minutes)",
    )
    cache_provider_ttl: int = Field(
        default=300,
        description="Provider connection cache TTL in seconds (default: 5 minutes)",
    )
    cache_schwab_ttl: int = Field(
        default=300,
        description="Schwab API response cache TTL in seconds (default: 5 minutes)",
    )
    cache_accounts_ttl: int = Field(
        default=300,
        description="Account list cache TTL in seconds (default: 5 minutes)",
    )
    cache_security_ttl: int = Field(
        default=60,
        description="Security config (token versions) cache TTL in seconds (default: 1 minute)",
    )

    # SSE (Server-Sent Events) configuration
    sse_enable_retention: bool = Field(
        default=False,
        description="Enable SSE event retention in Redis Streams for Last-Event-ID replay. "
        "When True, events are stored in Redis Streams for reconnection replay. "
        "When False, only live pub/sub is used (no replay capability).",
    )

    # Geolocation configuration
    geoip_db_path: str | None = Field(
        default="/app/data/geoip/GeoLite2-City.mmdb",
        description="Path to MaxMind GeoIP2 database file (GeoLite2-City.mmdb). "
        "Set to None to disable geolocation enrichment.",
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
        default=15,
        description="Access token expiration time in minutes (15 recommended for security)",
    )
    refresh_token_expire_days: int = Field(
        default=30,
        description="Refresh token expiration time in days",
    )
    bcrypt_rounds: int = Field(
        default=BCRYPT_ROUNDS_DEFAULT,
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

    # Provider: Alpaca Configuration
    alpaca_client_id: str | None = Field(
        default=None,
        description="Alpaca OAuth client ID",
    )
    alpaca_client_secret: str | None = Field(
        default=None,
        description="Alpaca OAuth client secret",
    )
    alpaca_api_base_url: str = Field(
        default="https://paper-api.alpaca.markets",
        description="Alpaca Trading API base URL (paper or live)",
    )
    alpaca_redirect_uri: str | None = Field(
        default=None,
        description="OAuth redirect URI for Alpaca callback",
    )

    model_config = SettingsConfigDict(
        # env_file handled by Docker compose (not coupled to specific environment)
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """
        Validate JWT secret key minimum length.

        Args:
            v: Secret key string.

        Returns:
            str: Validated secret key.

        Raises:
            ValueError: If key is shorter than 32 bytes (256 bits).
        """
        if len(v) < 32:
            raise ValueError(
                f"secret_key must be at least 32 characters (256 bits), got {len(v)}"
            )
        return v

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """
        Validate encryption key length for AES-256.

        Args:
            v: Encryption key string.

        Returns:
            str: Validated encryption key.

        Raises:
            ValueError: If key is not exactly 32 characters (256 bits).
        """
        if len(v) != 32:
            raise ValueError(
                f"encryption_key must be exactly 32 characters (256 bits), got {len(v)}"
            )
        return v

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
