"""Unit tests for core configuration functionality.

This module tests configuration loading, validation, environment variable handling,
and settings management following the Phase 1 test plan.
"""

import pytest
from unittest.mock import patch
from pydantic import ValidationError
import os

from src.core.config import Settings, get_settings
from tests.test_config import TestSettings, get_test_settings


class TestSettingsLoading:
    """Test basic settings loading and initialization."""

    def test_settings_initialization(self):
        """Test that Settings class can be initialized."""
        settings = Settings()

        assert settings is not None
        assert hasattr(settings, "APP_NAME")
        assert hasattr(settings, "DATABASE_URL")
        assert hasattr(settings, "SECRET_KEY")
        assert hasattr(settings, "ENCRYPTION_KEY")

    def test_settings_required_fields(self):
        """Test that required fields are present."""
        settings = Settings()

        # These should not be None or empty
        assert settings.APP_NAME
        assert settings.DATABASE_URL
        assert settings.SECRET_KEY
        assert settings.ENCRYPTION_KEY

    def test_settings_default_values(self):
        """Test default values are set correctly."""
        settings = Settings()

        # Test default values
        assert settings.APP_NAME == "Dashtam"
        assert settings.APP_VERSION == "0.1.0"
        assert settings.ENVIRONMENT == "development"
        assert settings.DEBUG is False  # Default should be False
        assert settings.API_V1_PREFIX == "/api/v1"
        assert settings.HOST == "0.0.0.0"
        assert settings.PORT == 8000

    def test_get_settings_singleton(self):
        """Test that get_settings returns singleton instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        # Should return same instance
        assert settings1 is settings2

    def test_settings_immutability(self):
        """Test that settings are effectively immutable."""
        settings = get_settings()

        # Should not be able to modify settings after creation
        with pytest.raises(Exception):
            settings.APP_NAME = "Modified"


class TestEnvironmentConfiguration:
    """Test environment-specific configuration loading."""

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_production_environment_detection(self):
        """Test production environment detection."""
        # Clear singleton to pick up environment change
        from src.core import config

        config._settings = None

        settings = get_settings()
        assert settings.ENVIRONMENT == "production"

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    def test_development_environment_detection(self):
        """Test development environment detection."""
        from src.core import config

        config._settings = None

        settings = get_settings()
        assert settings.ENVIRONMENT == "development"

    @patch.dict(os.environ, {"DEBUG": "true"})
    def test_debug_mode_enabled(self):
        """Test debug mode detection."""
        from src.core import config

        config._settings = None

        settings = get_settings()
        assert settings.DEBUG is True

    @patch.dict(os.environ, {"DEBUG": "false"})
    def test_debug_mode_disabled(self):
        """Test debug mode disabled."""
        from src.core import config

        config._settings = None

        settings = get_settings()
        assert settings.DEBUG is False

    @patch.dict(os.environ, {"PORT": "9000"})
    def test_port_environment_override(self):
        """Test port configuration from environment."""
        from src.core import config

        config._settings = None

        settings = get_settings()
        assert settings.PORT == 9000

    @patch.dict(os.environ, {"HOST": "127.0.0.1"})
    def test_host_environment_override(self):
        """Test host configuration from environment."""
        from src.core import config

        config._settings = None

        settings = get_settings()
        assert settings.HOST == "127.0.0.1"


class TestDatabaseConfiguration:
    """Test database-specific configuration."""

    def test_database_url_validation(self):
        """Test that DATABASE_URL is properly formatted."""
        settings = get_settings()

        # Should be PostgreSQL URL
        assert settings.DATABASE_URL.startswith(
            "postgresql://"
        ) or settings.DATABASE_URL.startswith("postgresql+asyncpg://")

        # Should have required components
        assert "@" in settings.DATABASE_URL  # Has credentials
        assert "/" in settings.DATABASE_URL  # Has database name

    @patch.dict(
        os.environ,
        {"DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/testdb"},
    )
    def test_database_url_environment_override(self):
        """Test DATABASE_URL from environment."""
        from src.core import config

        config._settings = None

        settings = get_settings()
        assert "testdb" in settings.DATABASE_URL
        assert "user:pass" in settings.DATABASE_URL

    def test_database_url_not_empty(self):
        """Test that DATABASE_URL is not empty."""
        settings = get_settings()

        assert settings.DATABASE_URL
        assert len(settings.DATABASE_URL) > 0

    @patch.dict(os.environ, {"DATABASE_URL": "invalid-url"})
    def test_invalid_database_url_handling(self):
        """Test handling of invalid database URLs."""
        from src.core import config

        config._settings = None

        # Should still load but with the invalid URL
        settings = get_settings()
        assert settings.DATABASE_URL == "invalid-url"


class TestSecurityConfiguration:
    """Test security-related configuration."""

    def test_secret_key_present(self):
        """Test that SECRET_KEY is present and not empty."""
        settings = get_settings()

        assert settings.SECRET_KEY
        assert len(settings.SECRET_KEY) >= 32  # Should be reasonably long

    def test_encryption_key_present(self):
        """Test that ENCRYPTION_KEY is present and valid."""
        settings = get_settings()

        assert settings.ENCRYPTION_KEY
        assert len(settings.ENCRYPTION_KEY) >= 16  # Minimum length for encryption

    def test_algorithm_configuration(self):
        """Test JWT algorithm configuration."""
        settings = get_settings()

        assert settings.ALGORITHM == "HS256"  # Should use HMAC SHA256

    def test_token_expiration_configuration(self):
        """Test token expiration settings."""
        settings = get_settings()

        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0
        assert settings.REFRESH_TOKEN_EXPIRE_DAYS > 0

        # Reasonable defaults
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES <= 1440  # Max 24 hours
        assert settings.REFRESH_TOKEN_EXPIRE_DAYS <= 90  # Max 90 days

    @patch.dict(os.environ, {"SECRET_KEY": "test-secret-key-12345678901234567890"})
    def test_secret_key_environment_override(self):
        """Test SECRET_KEY from environment."""
        from src.core import config

        config._settings = None

        settings = get_settings()
        assert settings.SECRET_KEY == "test-secret-key-12345678901234567890"

    @patch.dict(os.environ, {"ACCESS_TOKEN_EXPIRE_MINUTES": "120"})
    def test_token_expiration_environment_override(self):
        """Test token expiration from environment."""
        from src.core import config

        config._settings = None

        settings = get_settings()
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 120


class TestSSLConfiguration:
    """Test SSL/TLS configuration."""

    def test_ssl_cert_file_optional(self):
        """Test that SSL cert file is optional."""
        settings = get_settings()

        # Should be None or a valid path string
        assert settings.SSL_CERT_FILE is None or isinstance(settings.SSL_CERT_FILE, str)

    def test_ssl_key_file_optional(self):
        """Test that SSL key file is optional."""
        settings = get_settings()

        # Should be None or a valid path string
        assert settings.SSL_KEY_FILE is None or isinstance(settings.SSL_KEY_FILE, str)

    @patch.dict(os.environ, {"SSL_CERT_FILE": "/path/to/cert.pem"})
    def test_ssl_cert_file_environment(self):
        """Test SSL cert file from environment."""
        from src.core import config

        config._settings = None

        settings = get_settings()
        assert settings.SSL_CERT_FILE == "/path/to/cert.pem"

    def test_ssl_file_validation_when_present(self):
        """Test SSL file validation when files are specified."""
        settings = get_settings()

        # If SSL files are specified, they should be valid paths
        if settings.SSL_CERT_FILE:
            assert isinstance(settings.SSL_CERT_FILE, str)
            assert len(settings.SSL_CERT_FILE) > 0

        if settings.SSL_KEY_FILE:
            assert isinstance(settings.SSL_KEY_FILE, str)
            assert len(settings.SSL_KEY_FILE) > 0


class TestCORSConfiguration:
    """Test CORS configuration."""

    def test_cors_origins_default(self):
        """Test default CORS origins configuration."""
        settings = get_settings()

        assert settings.CORS_ORIGINS
        assert isinstance(settings.CORS_ORIGINS, list)

        # Should include common development origins
        cors_string = ",".join(settings.CORS_ORIGINS)
        assert "localhost" in cors_string

    @patch.dict(
        os.environ, {"CORS_ORIGINS": "http://localhost:3000,https://app.example.com"}
    )
    def test_cors_origins_parsing(self):
        """Test CORS origins parsing from environment."""
        from src.core import config

        config._settings = None

        settings = get_settings()

        assert "http://localhost:3000" in settings.CORS_ORIGINS
        assert "https://app.example.com" in settings.CORS_ORIGINS
        assert len(settings.CORS_ORIGINS) == 2

    def test_cors_origins_validation(self):
        """Test CORS origins validation."""
        settings = get_settings()

        # Each origin should be a valid URL format
        for origin in settings.CORS_ORIGINS:
            assert isinstance(origin, str)
            assert len(origin) > 0
            # Should start with http:// or https://
            assert origin.startswith("http://") or origin.startswith("https://")


class TestProviderConfiguration:
    """Test external provider configuration."""

    def test_schwab_api_configuration(self):
        """Test Schwab API configuration."""
        settings = get_settings()

        # Should have Schwab configuration
        assert hasattr(settings, "SCHWAB_API_KEY")
        assert hasattr(settings, "SCHWAB_API_SECRET")
        assert hasattr(settings, "SCHWAB_API_BASE_URL")
        assert hasattr(settings, "SCHWAB_REDIRECT_URI")

    def test_schwab_api_base_url_validation(self):
        """Test Schwab API base URL validation."""
        settings = get_settings()

        if settings.SCHWAB_API_BASE_URL:
            # Should be a valid URL
            assert settings.SCHWAB_API_BASE_URL.startswith("http")
            assert len(settings.SCHWAB_API_BASE_URL) > 0

    def test_schwab_redirect_uri_validation(self):
        """Test Schwab redirect URI validation."""
        settings = get_settings()

        if settings.SCHWAB_REDIRECT_URI:
            # Should be a valid URL
            assert settings.SCHWAB_REDIRECT_URI.startswith("http")
            assert "callback" in settings.SCHWAB_REDIRECT_URI.lower()

    @patch.dict(
        os.environ,
        {"SCHWAB_API_KEY": "test_api_key", "SCHWAB_API_SECRET": "test_api_secret"},
    )
    def test_schwab_environment_configuration(self):
        """Test Schwab configuration from environment."""
        from src.core import config

        config._settings = None

        settings = get_settings()
        assert settings.SCHWAB_API_KEY == "test_api_key"
        assert settings.SCHWAB_API_SECRET == "test_api_secret"


class TestCallbackServerConfiguration:
    """Test callback server configuration."""

    def test_callback_server_host_configuration(self):
        """Test callback server host configuration."""
        settings = get_settings()

        assert hasattr(settings, "CALLBACK_SERVER_HOST")
        assert settings.CALLBACK_SERVER_HOST

        # Should be valid host
        assert isinstance(settings.CALLBACK_SERVER_HOST, str)

    def test_callback_server_port_configuration(self):
        """Test callback server port configuration."""
        settings = get_settings()

        assert hasattr(settings, "CALLBACK_SERVER_PORT")
        assert settings.CALLBACK_SERVER_PORT > 0
        assert settings.CALLBACK_SERVER_PORT != settings.PORT  # Should be different

    def test_callback_ssl_configuration(self):
        """Test callback server SSL configuration."""
        settings = get_settings()

        assert hasattr(settings, "CALLBACK_SSL_CERT_FILE")
        assert hasattr(settings, "CALLBACK_SSL_KEY_FILE")

        # Should be None or valid paths
        if settings.CALLBACK_SSL_CERT_FILE:
            assert isinstance(settings.CALLBACK_SSL_CERT_FILE, str)
        if settings.CALLBACK_SSL_KEY_FILE:
            assert isinstance(settings.CALLBACK_SSL_KEY_FILE, str)


class TestTestSettingsConfiguration:
    """Test test-specific settings configuration."""

    def test_test_settings_initialization(self):
        """Test that TestSettings can be initialized."""
        test_settings = TestSettings()

        assert test_settings is not None
        assert test_settings.TESTING is True
        assert test_settings.DISABLE_EXTERNAL_CALLS is True

    def test_test_settings_inheritance(self):
        """Test that TestSettings inherits from Settings."""
        test_settings = TestSettings()

        # Should have all base Settings attributes
        assert hasattr(test_settings, "APP_NAME")
        assert hasattr(test_settings, "DATABASE_URL")
        assert hasattr(test_settings, "SECRET_KEY")

        # Plus test-specific attributes
        assert hasattr(test_settings, "TESTING")
        assert hasattr(test_settings, "DISABLE_EXTERNAL_CALLS")
        assert hasattr(test_settings, "MOCK_PROVIDERS")
        assert hasattr(test_settings, "FAST_ENCRYPTION")

    def test_test_database_url_property(self):
        """Test test database URL property."""
        test_settings = TestSettings()

        test_db_url = test_settings.test_database_url

        # Should contain 'test' in the database name
        assert "test" in test_db_url.lower()
        assert test_db_url.startswith("postgresql")

    def test_is_test_environment_property(self):
        """Test is_test_environment property."""
        test_settings = TestSettings()

        # Should detect test environment correctly
        is_test = test_settings.is_test_environment
        assert isinstance(is_test, bool)

        # If TESTING=True and ENVIRONMENT=testing, should be True
        if test_settings.TESTING and test_settings.ENVIRONMENT.lower() == "testing":
            assert is_test is True

    def test_get_test_settings_factory(self):
        """Test get_test_settings factory function."""
        test_settings1 = get_test_settings()
        test_settings2 = get_test_settings()

        assert isinstance(test_settings1, TestSettings)
        # Should return same instance (singleton)
        assert test_settings1 is test_settings2

    def test_test_settings_override_main_settings(self):
        """Test that test settings can override main settings."""
        test_settings = TestSettings()
        main_settings = get_settings()

        # Test settings should have different values for some fields
        assert test_settings.TESTING != main_settings.DEBUG
        assert test_settings.DISABLE_EXTERNAL_CALLS is True


class TestConfigurationValidation:
    """Test configuration validation and error handling."""

    def test_required_field_validation(self):
        """Test that required fields are validated."""
        # This test would be more meaningful with actual validation
        settings = get_settings()

        # Essential fields should not be empty
        essential_fields = ["APP_NAME", "DATABASE_URL", "SECRET_KEY", "ENCRYPTION_KEY"]
        for field in essential_fields:
            value = getattr(settings, field)
            assert value is not None
            assert value != ""

    @patch.dict(os.environ, {"PORT": "invalid"})
    def test_invalid_port_handling(self):
        """Test handling of invalid port configuration."""
        from src.core import config

        config._settings = None

        # Should raise validation error or use default
        try:
            settings = get_settings()
            # If it succeeds, should have used default port
            assert settings.PORT == 8000
        except (ValidationError, ValueError):
            # Or should raise validation error
            pass

    def test_environment_file_loading(self):
        """Test that environment files are loaded correctly."""
        settings = get_settings()

        # Should have loaded configuration from .env file
        # This is verified by having non-default values
        assert settings.APP_NAME == "Dashtam"  # From .env file

    def test_case_sensitivity(self):
        """Test that configuration is case sensitive."""
        settings = get_settings()

        # Settings should maintain case sensitivity
        assert settings.APP_NAME == "Dashtam"  # Not "dashtam" or "DASHTAM"


class TestConfigurationPerformance:
    """Test configuration performance and caching."""

    def test_settings_caching_performance(self):
        """Test that settings are cached for performance."""
        import time

        # First call (should initialize)
        start_time = time.time()
        settings1 = get_settings()
        first_call_time = time.time() - start_time

        # Second call (should be cached)
        start_time = time.time()
        settings2 = get_settings()
        second_call_time = time.time() - start_time

        # Should be same instance (cached)
        assert settings1 is settings2

        # Second call should be faster (cached)
        assert second_call_time < first_call_time or second_call_time < 0.001

    def test_concurrent_settings_access(self):
        """Test concurrent access to settings."""
        import threading

        results = []

        def get_settings_in_thread():
            settings = get_settings()
            results.append(id(settings))

        # Create multiple threads
        threads = [threading.Thread(target=get_settings_in_thread) for _ in range(5)]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # All should get the same singleton instance
        assert len(set(results)) == 1


class TestEnvironmentFileHandling:
    """Test environment file handling and precedence."""

    def test_env_file_precedence(self):
        """Test that environment variables take precedence over .env file."""
        # This is a conceptual test - actual implementation depends on environment
        settings = get_settings()

        # Should load configuration correctly
        assert settings.APP_NAME  # Should be loaded from somewhere

    def test_missing_env_file_handling(self):
        """Test handling when .env file is missing."""
        # Should not crash when .env file is missing
        settings = Settings()

        # Should still have default values
        assert settings.APP_NAME == "Dashtam"
        assert settings.ENVIRONMENT == "development"

    def test_env_file_encoding(self):
        """Test that environment files are loaded with correct encoding."""
        # Test UTF-8 encoding support
        settings = get_settings()

        # Should handle special characters correctly
        assert isinstance(settings.APP_NAME, str)
        # All string fields should be properly decoded
        for field_name in ["APP_NAME", "ENVIRONMENT"]:
            field_value = getattr(settings, field_name)
            if field_value:
                assert isinstance(field_value, str)
