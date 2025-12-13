"""Unit tests for EnvAdapter (environment variables secrets).

Tests cover:
- get_secret() success and failure cases
- get_secret_json() with valid/invalid JSON
- Secret path to environment variable conversion
- Error handling and Result types
- Edge cases (empty strings, special characters)

Architecture:
- Unit tests with mocked os.environ
- NO real environment dependencies
- Tests protocol compliance
"""

import json
import os
from unittest.mock import patch

import pytest

from src.core.enums import ErrorCode
from src.domain.errors import SecretsError
from src.core.result import Failure, Success
from src.infrastructure.secrets.env_adapter import EnvAdapter


@pytest.mark.unit
class TestEnvAdapterGetSecret:
    """Test EnvAdapter.get_secret() method."""

    def test_get_secret_success(self):
        """Test get_secret returns Success when env var exists."""
        with patch.dict(
            os.environ, {"DATABASE_URL": "postgresql://test:test@localhost:5432/test"}
        ):
            adapter = EnvAdapter()
            result = adapter.get_secret("database/url")

            assert isinstance(result, Success)
            assert result.value == "postgresql://test:test@localhost:5432/test"

    def test_get_secret_not_found(self):
        """Test get_secret returns Failure when env var does not exist."""
        with patch.dict(os.environ, {}, clear=True):
            adapter = EnvAdapter()
            result = adapter.get_secret("database/url")

            assert isinstance(result, Failure)
            assert isinstance(result.error, SecretsError)
            assert result.error.code == ErrorCode.SECRET_NOT_FOUND
            assert "DATABASE_URL" in result.error.message
            assert result.error.details["secret_path"] == "database/url"

    def test_get_secret_path_conversion(self):
        """Test secret path converts correctly to env var name."""
        test_cases = [
            ("database/url", "DATABASE_URL"),
            ("schwab/api_key", "SCHWAB_API_KEY"),
            ("schwab/api_secret", "SCHWAB_API_SECRET"),
            ("redis/url", "REDIS_URL"),
            ("encryption/key", "ENCRYPTION_KEY"),
        ]

        for secret_path, expected_env_var in test_cases:
            with patch.dict(os.environ, {expected_env_var: "test_value"}):
                adapter = EnvAdapter()
                result = adapter.get_secret(secret_path)

                assert isinstance(result, Success)
                assert result.value == "test_value"

    def test_get_secret_with_empty_string(self):
        """Test get_secret handles empty string as valid secret."""
        with patch.dict(os.environ, {"EMPTY_SECRET": ""}):
            adapter = EnvAdapter()
            result = adapter.get_secret("empty/secret")

            # Empty string is a valid secret value
            assert isinstance(result, Success)
            assert result.value == ""

    def test_get_secret_with_special_characters(self):
        """Test get_secret handles secrets with special characters."""
        secret_value = "p@ssw0rd!#$%^&*()_+-=[]{}|;:,.<>?"
        with patch.dict(os.environ, {"SPECIAL_SECRET": secret_value}):
            adapter = EnvAdapter()
            result = adapter.get_secret("special/secret")

            assert isinstance(result, Success)
            assert result.value == secret_value

    def test_get_secret_with_multiline_value(self):
        """Test get_secret handles multiline secrets (e.g., private keys)."""
        multiline_secret = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7VJT
-----END PRIVATE KEY-----"""
        with patch.dict(os.environ, {"MULTILINE_SECRET": multiline_secret}):
            adapter = EnvAdapter()
            result = adapter.get_secret("multiline/secret")

            assert isinstance(result, Success)
            assert result.value == multiline_secret


@pytest.mark.unit
class TestEnvAdapterGetSecretJson:
    """Test EnvAdapter.get_secret_json() method."""

    def test_get_secret_json_success(self):
        """Test get_secret_json returns parsed JSON dict."""
        json_secret = json.dumps({"key": "value", "number": "123"})
        with patch.dict(os.environ, {"CONFIG_JSON": json_secret}):
            adapter = EnvAdapter()
            result = adapter.get_secret_json("config/json")

            assert isinstance(result, Success)
            assert result.value == {"key": "value", "number": "123"}

    def test_get_secret_json_invalid_json(self):
        """Test get_secret_json returns Failure for invalid JSON."""
        with patch.dict(os.environ, {"INVALID_JSON": "not a json {]"}):
            adapter = EnvAdapter()
            result = adapter.get_secret_json("invalid/json")

            assert isinstance(result, Failure)
            assert isinstance(result.error, SecretsError)
            assert result.error.code == ErrorCode.SECRET_INVALID_JSON
            assert "invalid/json" in result.error.message

    def test_get_secret_json_not_found(self):
        """Test get_secret_json returns Failure when env var not found."""
        with patch.dict(os.environ, {}, clear=True):
            adapter = EnvAdapter()
            result = adapter.get_secret_json("missing/json")

            assert isinstance(result, Failure)
            assert isinstance(result.error, SecretsError)
            assert result.error.code == ErrorCode.SECRET_NOT_FOUND

    def test_get_secret_json_empty_object(self):
        """Test get_secret_json handles empty JSON object."""
        with patch.dict(os.environ, {"EMPTY_JSON": "{}"}):
            adapter = EnvAdapter()
            result = adapter.get_secret_json("empty/json")

            assert isinstance(result, Success)
            assert result.value == {}

    def test_get_secret_json_nested_object(self):
        """Test get_secret_json handles nested JSON structures."""
        nested_json = json.dumps(
            {
                "database": {"host": "localhost", "port": "5432"},
                "credentials": {"user": "admin", "password": "secret"},
            }
        )
        with patch.dict(os.environ, {"NESTED_JSON": nested_json}):
            adapter = EnvAdapter()
            result = adapter.get_secret_json("nested/json")

            assert isinstance(result, Success)
            assert result.value["database"]["host"] == "localhost"
            assert result.value["credentials"]["password"] == "secret"

    def test_get_secret_json_with_unicode(self):
        """Test get_secret_json handles unicode characters."""
        unicode_json = json.dumps({"message": "Hello 世界 🌍"})
        with patch.dict(os.environ, {"UNICODE_JSON": unicode_json}):
            adapter = EnvAdapter()
            result = adapter.get_secret_json("unicode/json")

            assert isinstance(result, Success)
            assert result.value["message"] == "Hello 世界 🌍"


@pytest.mark.unit
class TestEnvAdapterRefreshCache:
    """Test EnvAdapter.refresh_cache() method."""

    def test_refresh_cache_is_noop(self):
        """Test refresh_cache is a no-op (env vars always fresh)."""
        adapter = EnvAdapter()

        # Should not raise any errors
        adapter.refresh_cache()

        # Verify secrets still accessible after refresh
        with patch.dict(os.environ, {"TEST_SECRET": "value"}):
            result = adapter.get_secret("test/secret")
            assert isinstance(result, Success)
            assert result.value == "value"


@pytest.mark.unit
class TestEnvAdapterEdgeCases:
    """Test EnvAdapter edge cases and error conditions."""

    def test_adapter_initialization_succeeds(self):
        """Test EnvAdapter can be initialized without errors."""
        adapter = EnvAdapter()
        assert adapter is not None

    def test_multiple_adapters_independent(self):
        """Test multiple EnvAdapter instances are independent."""
        adapter1 = EnvAdapter()
        adapter2 = EnvAdapter()

        with patch.dict(os.environ, {"TEST_SECRET": "value1"}):
            result1 = adapter1.get_secret("test/secret")
            result2 = adapter2.get_secret("test/secret")

            assert result1.value == result2.value == "value1"

    def test_get_secret_with_numeric_value(self):
        """Test get_secret returns numeric values as strings."""
        with patch.dict(os.environ, {"PORT": "8000"}):
            adapter = EnvAdapter()
            result = adapter.get_secret("port")

            assert isinstance(result, Success)
            assert result.value == "8000"
            assert isinstance(result.value, str)

    def test_get_secret_path_with_multiple_slashes(self):
        """Test secret path with multiple slashes converts correctly."""
        with patch.dict(os.environ, {"AWS_SECRETS_MANAGER_KEY": "value"}):
            adapter = EnvAdapter()
            result = adapter.get_secret("aws/secrets/manager/key")

            assert isinstance(result, Success)
            assert result.value == "value"

    def test_get_secret_case_sensitivity(self):
        """Test env var names are uppercase regardless of input case."""
        with patch.dict(os.environ, {"DATABASE_URL": "value"}):
            adapter = EnvAdapter()

            # Lowercase input should still find DATABASE_URL
            result1 = adapter.get_secret("database/url")
            result2 = adapter.get_secret("DATABASE/URL")
            result3 = adapter.get_secret("DaTaBaSe/UrL")

            assert all(isinstance(r, Success) for r in [result1, result2, result3])
            assert result1.value == result2.value == result3.value == "value"
