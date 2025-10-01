"""Test configuration module for Dashtam tests.

This module provides test-specific configuration that extends the main Settings class
while following the same patterns and validators. It loads configuration from .env.test
and provides additional test-specific settings.
"""

from pydantic_settings import SettingsConfigDict
from pydantic import Field

from src.core.config import Settings


class TestSettings(Settings):
    """Test-specific settings that extend the main Settings class.

    This class inherits all configuration patterns from the main Settings class
    but loads from .env.test file and adds test-specific settings.

    Attributes:
        TESTING: Flag indicating this is a test environment.
        DISABLE_EXTERNAL_CALLS: Disable all external API calls for testing.
        MOCK_PROVIDERS: Use mock provider implementations.
        FAST_ENCRYPTION: Use faster (less secure) encryption for testing.
    """

    # Test-specific flags
    TESTING: bool = Field(default=True)
    DISABLE_EXTERNAL_CALLS: bool = Field(default=True)
    MOCK_PROVIDERS: bool = Field(default=True)
    FAST_ENCRYPTION: bool = Field(default=True)

    # Override model configuration to use .env file
    # In Docker test environment, .env.test is mounted as .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def test_database_url(self) -> str:
        """Get the test database URL, ensuring it points to test database."""
        if "dashtam_test" not in self.DATABASE_URL:
            # If not already a test database, create test version
            if "postgresql+asyncpg://" in self.DATABASE_URL:
                base_url = self.DATABASE_URL.rsplit("/", 1)[0]
                return f"{base_url}/dashtam_test"
        return self.DATABASE_URL

    @property
    def is_test_environment(self) -> bool:
        """Check if this is definitely a test environment."""
        return (
            self.TESTING
            and self.ENVIRONMENT.lower() == "testing"
            and "test" in self.DATABASE_URL.lower()
        )


def get_test_settings() -> TestSettings:
    """Get test settings singleton.

    Returns:
        Test configuration instance with all settings loaded from .env.test
        and validated according to their type annotations and validators.

    Raises:
        pydantic.ValidationError: If required test settings are missing or invalid.

    Example:
        >>> test_settings = get_test_settings()
        >>> print(test_settings.APP_NAME)
        'Dashtam'
        >>> print(test_settings.TESTING)
        True
        >>> print(test_settings.test_database_url)
        'postgresql+asyncpg://test:test@localhost:5432/dashtam_test'
    """
    return TestSettings()


# Export singleton instance for convenience
test_settings = get_test_settings()
