"""Integration tests for secrets adapters with real environment.

Tests cover:
- EnvAdapter with real environment variables
- Real .env file loading in test environment
- Integration with Settings configuration
- End-to-end secret retrieval

Architecture:
- Integration tests with fresh adapter instances (bypass container)
- Real environment variables from .env.test
- NO mocking - tests actual environment interaction
"""

import os
from unittest.mock import patch

import pytest

from src.core.config import settings
from src.core.errors import ErrorCode
from src.core.result import Failure, Success
from src.infrastructure.secrets.env_adapter import EnvAdapter


@pytest.mark.integration
class TestEnvAdapterIntegration:
    """Integration tests for EnvAdapter with real environment."""

    def test_env_adapter_reads_from_test_environment(self):
        """Test EnvAdapter can read real env vars from test environment."""
        # Test environment has DATABASE_URL set in .env.test
        adapter = EnvAdapter()
        result = adapter.get_secret("database/url")

        assert isinstance(result, Success)
        assert result.value == settings.database_url
        assert "postgresql" in result.value

    def test_env_adapter_reads_redis_url(self):
        """Test EnvAdapter reads Redis URL from environment."""
        adapter = EnvAdapter()
        result = adapter.get_secret("redis/url")

        assert isinstance(result, Success)
        assert result.value == settings.redis_url
        assert "redis://" in result.value

    def test_env_adapter_reads_secret_key(self):
        """Test EnvAdapter reads SECRET_KEY from environment."""
        adapter = EnvAdapter()
        result = adapter.get_secret("secret/key")

        assert isinstance(result, Success)
        assert result.value == settings.secret_key
        assert len(result.value) > 0

    def test_env_adapter_handles_missing_var_in_real_env(self):
        """Test EnvAdapter returns Failure for truly missing env var."""
        adapter = EnvAdapter()
        result = adapter.get_secret("nonexistent/variable/that/should/not/exist")

        assert isinstance(result, Failure)
        assert result.error.code == ErrorCode.SECRET_NOT_FOUND

    def test_multiple_env_adapters_share_same_environment(self):
        """Test multiple EnvAdapter instances read same environment."""
        adapter1 = EnvAdapter()
        adapter2 = EnvAdapter()

        result1 = adapter1.get_secret("database/url")
        result2 = adapter2.get_secret("database/url")

        assert result1.value == result2.value

    def test_env_adapter_with_dynamically_set_var(self):
        """Test EnvAdapter reads dynamically set environment variable."""
        test_var_name = "INTEGRATION_TEST_SECRET"
        test_var_value = "integration_test_value_12345"

        with patch.dict(os.environ, {test_var_name: test_var_value}):
            adapter = EnvAdapter()
            result = adapter.get_secret("integration/test/secret")

            assert isinstance(result, Success)
            assert result.value == test_var_value

    def test_env_adapter_refresh_reflects_environment_changes(self):
        """Test refresh_cache is no-op but new reads reflect env changes."""
        test_var_name = "CHANGING_VAR"

        with patch.dict(os.environ, {test_var_name: "original_value"}):
            adapter = EnvAdapter()
            result1 = adapter.get_secret("changing/var")
            assert result1.value == "original_value"

            # Change environment variable
            os.environ[test_var_name] = "new_value"

            # Refresh (no-op for EnvAdapter)
            adapter.refresh_cache()

            # Read again - should get new value
            result2 = adapter.get_secret("changing/var")
            assert result2.value == "new_value"


@pytest.mark.integration
class TestEnvAdapterWithSettings:
    """Integration tests for EnvAdapter with Settings configuration."""

    def test_settings_values_match_env_adapter_secrets(self):
        """Test Settings and EnvAdapter return same values."""
        adapter = EnvAdapter()

        # Compare database URL
        db_result = adapter.get_secret("database/url")
        assert db_result.value == settings.database_url

        # Compare Redis URL
        redis_result = adapter.get_secret("redis/url")
        assert redis_result.value == settings.redis_url

        # Compare secret key
        secret_result = adapter.get_secret("secret/key")
        assert secret_result.value == settings.secret_key

    def test_env_adapter_can_access_all_required_settings(self):
        """Test EnvAdapter can access all required configuration secrets."""
        adapter = EnvAdapter()

        required_secrets = [
            ("database/url", settings.database_url),
            ("redis/url", settings.redis_url),
            ("secret/key", settings.secret_key),
            ("encryption/key", settings.encryption_key),
        ]

        for secret_path, expected_value in required_secrets:
            result = adapter.get_secret(secret_path)
            assert isinstance(result, Success)
            assert result.value == expected_value
            assert len(result.value) > 0
