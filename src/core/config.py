"""Application configuration management.

This module handles all configuration settings for the Dashtam application,
including environment variables, database settings, and provider configurations.
All settings are validated at startup to ensure the application has proper
configuration before running.

The settings are loaded once and cached for performance. They can be accessed
throughout the application via the `settings` singleton.

Example:
    >>> from src.core.config import settings
    >>> print(settings.APP_NAME)
    'Dashtam'
    >>> print(settings.DATABASE_URL)
    'postgresql+asyncpg://postgres:postgres@localhost:5432/dashtam'
"""

from typing import Optional, List, TYPE_CHECKING
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from functools import lru_cache
from pathlib import Path

if TYPE_CHECKING:
    import httpx


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    This class uses Pydantic to load, validate, and type-check all application
    settings from environment variables or a .env file. Settings are validated
    at startup, ensuring the application fails fast if misconfigured.

    All settings have sensible defaults for development, but should be properly
    configured for production deployment.

    Attributes:
        APP_NAME: Application name used in API responses and logging.
        APP_VERSION: Current version of the application.
        ENVIRONMENT: Application environment (development/staging/production).
        DEBUG: Enable debug mode with verbose logging and auto-reload.
        API_V1_PREFIX: URL prefix for API version 1 endpoints.
        HOST: Host interface to bind the server to.
        PORT: Port number for the main API server.
        RELOAD: Enable auto-reload on code changes (development only).
        SECRET_KEY: Secret key for JWT token signing and encryption.
        ALGORITHM: Algorithm used for JWT token encoding.
        ACCESS_TOKEN_EXPIRE_MINUTES: Access token TTL in minutes.
        REFRESH_TOKEN_EXPIRE_DAYS: Refresh token TTL in days.
        DATABASE_URL: PostgreSQL connection URL with async driver.
        DB_ECHO: Enable SQLAlchemy query logging.
        CORS_ORIGINS: List of allowed CORS origins.
        SSL_CERT_FILE: Path to SSL certificate for HTTPS.
        SSL_KEY_FILE: Path to SSL private key for HTTPS.
        CALLBACK_SERVER_HOST: Host for OAuth callback server.
        CALLBACK_SERVER_PORT: Port for OAuth callback server.
        CALLBACK_SSL_CERT_FILE: SSL certificate for callback server.
        CALLBACK_SSL_KEY_FILE: SSL private key for callback server.
        SCHWAB_API_KEY: Charles Schwab API client ID.
        SCHWAB_API_SECRET: Charles Schwab API client secret.
        SCHWAB_API_BASE_URL: Base URL for Schwab API endpoints.
        SCHWAB_REDIRECT_URI: OAuth redirect URI registered with Schwab.
        PLAID_CLIENT_ID: Plaid API client ID (future).
        PLAID_SECRET: Plaid API secret key (future).
        PLAID_ENVIRONMENT: Plaid environment (sandbox/development/production).
    """

    # Application
    APP_NAME: str = "Dashtam"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="production")
    DEBUG: bool = Field(default=False)
    API_V1_PREFIX: str = "/api/v1"

    # Server
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    RELOAD: bool = Field(default=False)

    # Security
    SECRET_KEY: str = Field(default="change-me-in-production-use-secrets-manager")
    ENCRYPTION_KEY: str = Field(
        default="change-me-in-production-use-secrets-manager-for-encryption"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/dashtam"
    )
    DB_ECHO: bool = Field(default=False)

    # CORS
    CORS_ORIGINS: str = Field(default="https://localhost:3000")

    # SSL/TLS Configuration (HTTPS everywhere)
    SSL_CERT_FILE: str = Field(default="certs/cert.pem")
    SSL_KEY_FILE: str = Field(default="certs/key.pem")

    # Callback Server (for OAuth providers)
    CALLBACK_SERVER_HOST: str = Field(default="0.0.0.0")
    CALLBACK_SERVER_PORT: int = Field(default=8182)
    CALLBACK_SSL_CERT_FILE: str = Field(default="certs/callback_cert.pem")
    CALLBACK_SSL_KEY_FILE: str = Field(default="certs/callback_key.pem")

    # Provider Configuration - Schwab
    SCHWAB_API_KEY: Optional[str] = Field(default=None)
    SCHWAB_API_SECRET: Optional[str] = Field(default=None)
    SCHWAB_API_BASE_URL: str = Field(default="https://api.schwabapi.com")
    SCHWAB_REDIRECT_URI: str = Field(default="https://127.0.0.1:8182")

    # Provider Configuration - Plaid (Future)
    PLAID_CLIENT_ID: Optional[str] = Field(default=None)
    PLAID_SECRET: Optional[str] = Field(default=None)
    PLAID_ENVIRONMENT: str = Field(default="sandbox")

    # HTTP Client Configuration
    HTTP_TIMEOUT_TOTAL: float = Field(
        default=30.0, description="Total timeout for HTTP requests in seconds"
    )
    HTTP_TIMEOUT_CONNECT: float = Field(
        default=10.0, description="Connection timeout for HTTP requests in seconds"
    )
    HTTP_TIMEOUT_READ: float = Field(
        default=30.0, description="Read timeout for HTTP requests in seconds"
    )
    HTTP_TIMEOUT_POOL: float = Field(
        default=5.0, description="Pool acquisition timeout for HTTP requests in seconds"
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    @field_validator("DEBUG", mode="after")
    @classmethod
    def set_debug_from_environment(cls, v: bool, values) -> bool:
        """Auto-set DEBUG mode based on ENVIRONMENT if not explicitly set.

        In development and staging environments, DEBUG should be True by default
        to enable features like API documentation and detailed error messages.

        Args:
            v: Current DEBUG value
            values: All field values including ENVIRONMENT

        Returns:
            Updated DEBUG value based on environment
        """
        # If DEBUG is explicitly set to True, keep it
        if v is True:
            return v

        # Get environment from the field values
        environment = getattr(values, "ENVIRONMENT", "production")

        # Auto-enable DEBUG for development and staging
        if environment.lower() in ["development", "dev", "staging", "stage"]:
            return True

        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string to list.

        This property converts the CORS_ORIGINS string (comma-separated)
        into a list of origin URLs for use in FastAPI CORS middleware.

        Returns:
            List of validated CORS origin URLs.

        Example:
            Input (CORS_ORIGINS): "https://localhost:3000,https://app.dashtam.com"
            Output: ["https://localhost:3000", "https://app.dashtam.com"]
        """
        if not self.CORS_ORIGINS or self.CORS_ORIGINS == "":
            return ["https://localhost:3000"]  # Default

        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]

    def get_http_timeout(self) -> "httpx.Timeout":
        """Create httpx.Timeout object from configuration.

        Returns configured timeout settings for all HTTP/HTTPS client operations.
        This prevents hanging requests and resource exhaustion.

        Timeout Breakdown:
            - connect: Time allowed to establish a connection
            - read: Time allowed to read response data
            - pool: Time allowed to acquire a connection from the pool
            - timeout: Total time allowed for the entire request

        Returns:
            httpx.Timeout object with configured timeouts.

        Example:
            >>> from src.core.config import settings
            >>> import httpx
            >>> async with httpx.AsyncClient(timeout=settings.get_http_timeout()) as client:
            ...     response = await client.get(url)
        """
        import httpx

        return httpx.Timeout(
            timeout=self.HTTP_TIMEOUT_TOTAL,
            connect=self.HTTP_TIMEOUT_CONNECT,
            read=self.HTTP_TIMEOUT_READ,
            pool=self.HTTP_TIMEOUT_POOL,
        )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure DATABASE_URL uses asyncpg driver for async operations.

        This validator automatically converts standard PostgreSQL URLs to use
        the asyncpg driver, which is required for async database operations
        with SQLAlchemy and SQLModel.

        Args:
            v: Database URL string.

        Returns:
            Database URL with asyncpg driver.

        Example:
            Input: "postgresql://user:pass@localhost/db"
            Output: "postgresql+asyncpg://user:pass@localhost/db"
        """
        if "postgresql://" in v and "asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://")
        if "postgresql+psycopg://" in v:
            return v.replace("postgresql+psycopg://", "postgresql+asyncpg://")
        return v

    @field_validator(
        "SSL_CERT_FILE",
        "SSL_KEY_FILE",
        "CALLBACK_SSL_CERT_FILE",
        "CALLBACK_SSL_KEY_FILE",
    )
    @classmethod
    def validate_ssl_files(cls, v: str, info) -> str:
        """Validate that SSL certificate files exist.

        This validator checks if the specified SSL certificate and key files
        exist on the filesystem. In development, it provides helpful guidance
        if certificates are missing.

        Args:
            v: Path to SSL certificate or key file.
            info: Pydantic validation context.

        Returns:
            The validated file path.

        Note:
            In development, missing certificates will show a warning but won't
            fail validation. In production, you should ensure certificates exist.
        """
        file_path = Path(v)
        if not file_path.exists():
            # In development, we'll generate these if they don't exist
            print(f"⚠️  SSL file not found: {v}")
            print("   Run: make generate-certs")
        return v

    @property
    def server_url(self) -> str:
        """Get the full HTTPS URL for the main API server.

        Constructs the complete URL including protocol, host, and port
        for the main FastAPI application server.

        Returns:
            Full HTTPS URL for the API server.

        Example:
            >>> settings.server_url
            'https://0.0.0.0:8000'
        """
        return f"https://{self.HOST}:{self.PORT}"

    @property
    def callback_server_url(self) -> str:
        """Get the full HTTPS URL for the OAuth callback server.

        Constructs the complete URL including protocol, host, and port
        for the OAuth callback server that handles provider redirects.

        Returns:
            Full HTTPS URL for the callback server.

        Example:
            >>> settings.callback_server_url
            'https://0.0.0.0:8182'
        """
        return f"https://{self.CALLBACK_SERVER_HOST}:{self.CALLBACK_SERVER_PORT}"


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings singleton.

    This function returns a cached instance of Settings to avoid re-reading
    and re-validating environment variables on every call. The settings are
    loaded once at application startup and reused throughout the application
    lifecycle.

    The @lru_cache decorator ensures that only one Settings instance is created,
    making this function act as a singleton factory.

    Returns:
        Application configuration instance with all settings loaded from
        environment variables and validated according to their type annotations
        and validators.

    Raises:
        pydantic.ValidationError: If required settings are missing or invalid.

    Example:
        >>> settings = get_settings()
        >>> print(settings.APP_NAME)
        'Dashtam'
        >>> print(settings.DATABASE_URL)
        'postgresql+asyncpg://postgres:postgres@localhost:5432/dashtam'
    """
    return Settings()


# Export singleton instance for convenience
# This allows: from src.core.config import settings
settings = get_settings()
