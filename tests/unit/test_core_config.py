"""
Unit tests for configuration management (flat Settings).

Tests cover:
- Settings loading from environment variables
- Environment detection
- Validation (bcrypt_rounds, URLs, CORS parsing)
- Default values
- Cached singleton behavior
"""

import os
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.core.config import Settings, get_settings
from src.core.enums.environment import Environment


@pytest.fixture
def base_test_env():
    """Base environment dict for config tests.

    Provides minimal required settings. Tests can override specific values
    by merging with this dict.

    Note: Keys meet validation requirements:
    - SECRET_KEY: 32+ characters (256 bits)
    - ENCRYPTION_KEY: Exactly 32 characters (256 bits)
    """
    return {
        "DATABASE_URL": "postgresql://test",
        "REDIS_URL": "redis://test",
        "SECRET_KEY": "test-secret-key-minlen-32!!!****",  # Exactly 32 chars
        "ENCRYPTION_KEY": "test-encryption-exactly-32!!!!!!",  # Exactly 32 chars
        "API_BASE_URL": "https://test.com",
        "CALLBACK_BASE_URL": "https://callback.com",
        "CORS_ORIGINS": "https://test.com",
        "VERIFICATION_URL_BASE": "https://test.com",
    }


class TestEnvironmentEnum:
    """Test Environment enum."""

    def test_environment_values(self):
        """Test that all expected environments are defined."""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.TESTING.value == "testing"
        assert Environment.CI.value == "ci"
        assert Environment.PRODUCTION.value == "production"


class TestSettingsValidation:
    """Test Settings field validation."""

    def test_bcrypt_rounds_valid(self, base_test_env):
        """Test bcrypt_rounds validation with valid values."""
        env_values = base_test_env | {"BCRYPT_ROUNDS": "10"}
        with patch.dict(os.environ, env_values, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
            assert settings.bcrypt_rounds == 10

    def test_bcrypt_rounds_too_low(self, base_test_env):
        """Test bcrypt_rounds validation rejects values < 4."""
        env_values = base_test_env | {"BCRYPT_ROUNDS": "3"}
        with patch.dict(os.environ, env_values, clear=True):
            get_settings.cache_clear()
            with pytest.raises(ValidationError) as exc_info:
                Settings()  # type: ignore[call-arg]

            errors = exc_info.value.errors()
            assert any(
                "bcrypt_rounds must be between 4 and 31" in str(error)
                for error in errors
            )

    def test_bcrypt_rounds_too_high(self, base_test_env):
        """Test bcrypt_rounds validation rejects values > 31."""
        env_values = base_test_env | {"BCRYPT_ROUNDS": "32"}
        with patch.dict(os.environ, env_values, clear=True):
            get_settings.cache_clear()
            with pytest.raises(ValidationError) as exc_info:
                Settings()  # type: ignore[call-arg]

            errors = exc_info.value.errors()
            assert any(
                "bcrypt_rounds must be between 4 and 31" in str(error)
                for error in errors
            )

    def test_url_trailing_slash_removed(self, base_test_env):
        """Test that trailing slashes are removed from URLs."""
        env_values = base_test_env | {
            "API_BASE_URL": "https://test.com/",
            "CALLBACK_BASE_URL": "https://callback.com/",
        }
        with patch.dict(os.environ, env_values, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
            assert settings.api_base_url == "https://test.com"
            assert settings.callback_base_url == "https://callback.com"

    def test_cors_origins_parsing(self, base_test_env):
        """Test that comma-separated CORS origins are parsed correctly."""
        env_values = base_test_env | {
            "CORS_ORIGINS": "https://example.com,https://app.example.com, https://test.com",
        }
        with patch.dict(os.environ, env_values, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
            # cors_origins is str in type annotation but list[str] at runtime
            assert settings.cors_origins == [  # type: ignore[comparison-overlap]
                "https://example.com",
                "https://app.example.com",
                "https://test.com",
            ]


class TestSettingsLoading:
    """Test Settings loading from environment variables."""

    def test_settings_from_env(self, base_test_env):
        """Test that Settings loads from environment variables."""
        env_values = base_test_env | {
            "ENVIRONMENT": "testing",
            "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
            "REDIS_URL": "redis://localhost:6379/1",
            "SECRET_KEY": "test-secret-key-minlen-32!!!****",  # Exactly 32 chars
            "API_BASE_URL": "https://test.example.com",
        }
        with patch.dict(os.environ, env_values, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.environment == Environment.TESTING
            assert (
                settings.database_url
                == "postgresql+asyncpg://test:test@localhost:5432/test"
            )
            assert settings.redis_url == "redis://localhost:6379/1"
            assert settings.secret_key == "test-secret-key-minlen-32!!!****"
            assert settings.api_base_url == "https://test.example.com"
            # cors_origins is str in type annotation but list[str] at runtime
            assert settings.cors_origins == ["https://test.com"]  # type: ignore[comparison-overlap]

    def test_settings_defaults(self, base_test_env):
        """Test Settings default values."""
        # Read expected version from pyproject.toml (single source of truth)
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with pyproject_path.open("rb") as f:
            pyproject = tomllib.load(f)
        expected_version = pyproject["project"]["version"]

        with patch.dict(os.environ, base_test_env, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.environment == Environment.DEVELOPMENT  # default
            assert settings.debug is False  # default
            assert settings.host == "0.0.0.0"  # default
            assert settings.port == 8000  # default
            assert settings.reload is False  # default
            assert settings.log_level == "INFO"  # default
            assert settings.app_name == "Dashtam"  # default
            assert settings.app_version == expected_version  # from pyproject.toml
            assert settings.algorithm == "HS256"  # default
            assert settings.access_token_expire_minutes == 15  # default (updated F6.5)
            assert settings.refresh_token_expire_days == 30  # default
            assert settings.bcrypt_rounds == 12  # default
            assert settings.api_v1_prefix == "/api/v1"  # default
            assert settings.cors_allow_credentials is True  # default

    def test_settings_required_fields(self):
        """Test that required fields must be provided."""
        with patch.dict(os.environ, {}, clear=True):
            get_settings.cache_clear()
            with pytest.raises(ValidationError) as exc_info:
                Settings()  # type: ignore[call-arg]

            errors = exc_info.value.errors()
            # Required fields: database_url, redis_url, secret_key, encryption_key,
            # api_base_url, callback_base_url, cors_origins
            required_fields = {
                "database_url",
                "redis_url",
                "secret_key",
                "encryption_key",
                "api_base_url",
                "callback_base_url",
                "cors_origins",
            }
            error_fields = {error["loc"][0] for error in errors}
            assert required_fields.issubset(error_fields)


class TestEnvironmentProperties:
    """Test environment check convenience properties."""

    def test_is_development(self, base_test_env):
        """Test is_development property."""
        env_values = base_test_env | {"ENVIRONMENT": "development"}
        with patch.dict(os.environ, env_values, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.is_development is True
            assert settings.is_testing is False
            assert settings.is_ci is False
            assert settings.is_production is False

    def test_is_testing(self, base_test_env):
        """Test is_testing property."""
        env_values = base_test_env | {"ENVIRONMENT": "testing"}
        with patch.dict(os.environ, env_values, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.is_testing is True
            assert settings.is_development is False

    def test_is_ci(self, base_test_env):
        """Test is_ci property."""
        env_values = base_test_env | {"ENVIRONMENT": "ci"}
        with patch.dict(os.environ, env_values, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.is_ci is True
            assert settings.is_development is False

    def test_is_production(self, base_test_env):
        """Test is_production property."""
        env_values = base_test_env | {"ENVIRONMENT": "production"}
        with patch.dict(os.environ, env_values, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.is_production is True
            assert settings.is_development is False


class TestSettingsCaching:
    """Test Settings singleton caching behavior."""

    def test_get_settings_cached(self, base_test_env):
        """Test that get_settings returns cached instance."""
        with patch.dict(os.environ, base_test_env, clear=True):
            get_settings.cache_clear()

            settings1 = get_settings()
            settings2 = get_settings()

            assert settings1 is settings2  # Same instance (cached)
