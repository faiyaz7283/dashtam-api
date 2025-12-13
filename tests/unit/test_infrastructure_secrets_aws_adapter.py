"""Unit tests for AWSAdapter (AWS Secrets Manager).

Tests cover:
- get_secret() success and failure cases
- get_secret_json() with valid/invalid JSON
- In-memory caching behavior
- refresh_cache() functionality
- Error handling (not found, access denied)
- AWS SDK integration with moto mock

Architecture:
- Unit tests with moto mocking AWS Secrets Manager
- NO real AWS dependencies
- Tests protocol compliance and caching
"""

import json

import boto3
import pytest
from moto import mock_aws

from src.core.enums import ErrorCode
from src.domain.errors import SecretsError
from src.core.result import Failure, Success
from src.infrastructure.secrets.aws_adapter import AWSAdapter


@pytest.mark.unit
class TestAWSAdapterInitialization:
    """Test AWSAdapter initialization."""

    @mock_aws
    def test_adapter_initialization_succeeds(self):
        """Test AWSAdapter initializes with boto3 client."""
        adapter = AWSAdapter(environment="production", region="us-east-1")

        assert adapter is not None
        assert adapter.environment == "production"
        assert adapter.client is not None
        assert adapter._cache == {}

    @mock_aws
    def test_adapter_with_different_regions(self):
        """Test AWSAdapter can be initialized with different regions."""
        regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]

        for region in regions:
            adapter = AWSAdapter(environment="staging", region=region)
            assert adapter.client.meta.region_name == region

    @mock_aws
    def test_adapter_with_different_environments(self):
        """Test AWSAdapter accepts different environment names."""
        environments = ["development", "staging", "production", "testing"]

        for env in environments:
            adapter = AWSAdapter(environment=env)
            assert adapter.environment == env


@pytest.mark.unit
class TestAWSAdapterGetSecret:
    """Test AWSAdapter.get_secret() method."""

    @mock_aws
    def test_get_secret_success(self):
        """Test get_secret returns Success when secret exists in AWS."""
        # Setup: Create secret in mocked AWS
        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret_id = "/dashtam/production/database/url"
        secret_value = "postgresql://prod:pass@localhost:5432/prod"
        client.create_secret(Name=secret_id, SecretString=secret_value)

        # Test
        adapter = AWSAdapter(environment="production")
        result = adapter.get_secret("database/url")

        assert isinstance(result, Success)
        assert result.value == secret_value

    @mock_aws
    def test_get_secret_not_found(self):
        """Test get_secret returns Failure when secret doesn't exist."""
        adapter = AWSAdapter(environment="production")
        result = adapter.get_secret("nonexistent/secret")

        assert isinstance(result, Failure)
        assert isinstance(result.error, SecretsError)
        assert result.error.code == ErrorCode.SECRET_NOT_FOUND
        assert "/dashtam/production/nonexistent/secret" in result.error.message

    @mock_aws
    def test_get_secret_builds_correct_path(self):
        """Test get_secret builds correct AWS secret path."""
        client = boto3.client("secretsmanager", region_name="us-east-1")

        # Create secrets with different paths
        test_cases = [
            ("production", "database/url", "/dashtam/production/database/url"),
            ("staging", "schwab/api_key", "/dashtam/staging/schwab/api_key"),
            (
                "production",
                "redis/password",
                "/dashtam/production/redis/password",
            ),
        ]

        for environment, secret_path, expected_secret_id in test_cases:
            client.create_secret(Name=expected_secret_id, SecretString="test_value")

            adapter = AWSAdapter(environment=environment)
            result = adapter.get_secret(secret_path)

            assert isinstance(result, Success)
            assert result.value == "test_value"

    @mock_aws
    def test_get_secret_with_special_characters(self):
        """Test get_secret handles secrets with special characters."""
        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret_id = "/dashtam/production/special/chars"
        secret_value = "p@ssw0rd!#$%^&*()_+-=[]{}|;:,.<>?"
        client.create_secret(Name=secret_id, SecretString=secret_value)

        adapter = AWSAdapter(environment="production")
        result = adapter.get_secret("special/chars")

        assert isinstance(result, Success)
        assert result.value == secret_value

    @mock_aws
    def test_get_secret_with_multiline_value(self):
        """Test get_secret handles multiline secrets (e.g., private keys)."""
        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret_id = "/dashtam/production/ssh/private_key"
        multiline_secret = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7VJT
-----END PRIVATE KEY-----"""
        client.create_secret(Name=secret_id, SecretString=multiline_secret)

        adapter = AWSAdapter(environment="production")
        result = adapter.get_secret("ssh/private_key")

        assert isinstance(result, Success)
        assert result.value == multiline_secret


@pytest.mark.unit
class TestAWSAdapterCaching:
    """Test AWSAdapter caching behavior."""

    @mock_aws
    def test_get_secret_caches_value(self):
        """Test get_secret caches value in memory."""
        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret_id = "/dashtam/production/database/url"
        client.create_secret(Name=secret_id, SecretString="cached_value")

        adapter = AWSAdapter(environment="production")

        # First call - fetches from AWS
        result1 = adapter.get_secret("database/url")
        assert isinstance(result1, Success)
        assert secret_id in adapter._cache
        assert adapter._cache[secret_id] == "cached_value"

        # Second call - should use cache
        result2 = adapter.get_secret("database/url")
        assert isinstance(result2, Success)
        assert result2.value == "cached_value"

    @mock_aws
    def test_get_secret_returns_cached_value_without_aws_call(self):
        """Test cached secret returned without hitting AWS."""
        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret_id = "/dashtam/production/test/secret"
        client.create_secret(Name=secret_id, SecretString="original")

        adapter = AWSAdapter(environment="production")

        # First call
        result1 = adapter.get_secret("test/secret")
        assert result1.value == "original"

        # Manually update cache (simulating what would happen with rotation)
        adapter._cache[secret_id] = "updated_in_cache"

        # Second call should return cached value
        result2 = adapter.get_secret("test/secret")
        assert result2.value == "updated_in_cache"

    @mock_aws
    def test_refresh_cache_clears_all_cached_secrets(self):
        """Test refresh_cache clears all cached secrets."""
        client = boto3.client("secretsmanager", region_name="us-east-1")
        client.create_secret(Name="/dashtam/production/secret1", SecretString="value1")
        client.create_secret(Name="/dashtam/production/secret2", SecretString="value2")

        adapter = AWSAdapter(environment="production")

        # Cache multiple secrets
        adapter.get_secret("secret1")
        adapter.get_secret("secret2")
        assert len(adapter._cache) == 2

        # Clear cache
        adapter.refresh_cache()
        assert len(adapter._cache) == 0
        assert adapter._cache == {}

    @mock_aws
    def test_get_secret_after_refresh_fetches_fresh_value(self):
        """Test get_secret fetches fresh value from AWS after cache refresh."""
        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret_id = "/dashtam/production/rotating/secret"
        client.create_secret(Name=secret_id, SecretString="old_value")

        adapter = AWSAdapter(environment="production")

        # First call - caches old value
        result1 = adapter.get_secret("rotating/secret")
        assert result1.value == "old_value"

        # Simulate secret rotation in AWS
        client.put_secret_value(SecretId=secret_id, SecretString="new_value")

        # Without refresh, still returns cached value
        result2 = adapter.get_secret("rotating/secret")
        assert result2.value == "old_value"

        # After refresh, fetches new value
        adapter.refresh_cache()
        result3 = adapter.get_secret("rotating/secret")
        assert result3.value == "new_value"

    @mock_aws
    def test_multiple_adapters_have_independent_caches(self):
        """Test multiple AWSAdapter instances have independent caches."""
        client = boto3.client("secretsmanager", region_name="us-east-1")
        client.create_secret(
            Name="/dashtam/production/shared/secret", SecretString="value"
        )

        adapter1 = AWSAdapter(environment="production")
        adapter2 = AWSAdapter(environment="production")

        # Cache in adapter1
        adapter1.get_secret("shared/secret")
        assert len(adapter1._cache) == 1
        assert len(adapter2._cache) == 0

        # Cache in adapter2
        adapter2.get_secret("shared/secret")
        assert len(adapter2._cache) == 1

        # Clear adapter1 cache doesn't affect adapter2
        adapter1.refresh_cache()
        assert len(adapter1._cache) == 0
        assert len(adapter2._cache) == 1


@pytest.mark.unit
class TestAWSAdapterGetSecretJson:
    """Test AWSAdapter.get_secret_json() method."""

    @mock_aws
    def test_get_secret_json_success(self):
        """Test get_secret_json returns parsed JSON dict."""
        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret_id = "/dashtam/production/app/config"
        json_secret = json.dumps({"key": "value", "number": "123"})
        client.create_secret(Name=secret_id, SecretString=json_secret)

        adapter = AWSAdapter(environment="production")
        result = adapter.get_secret_json("app/config")

        assert isinstance(result, Success)
        assert result.value == {"key": "value", "number": "123"}

    @mock_aws
    def test_get_secret_json_invalid_json(self):
        """Test get_secret_json returns Failure for invalid JSON."""
        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret_id = "/dashtam/production/invalid/json"
        client.create_secret(Name=secret_id, SecretString="not a json {]")

        adapter = AWSAdapter(environment="production")
        result = adapter.get_secret_json("invalid/json")

        assert isinstance(result, Failure)
        assert isinstance(result.error, SecretsError)
        assert result.error.code == ErrorCode.SECRET_INVALID_JSON
        assert "invalid/json" in result.error.message

    @mock_aws
    def test_get_secret_json_not_found(self):
        """Test get_secret_json returns Failure when secret not found."""
        adapter = AWSAdapter(environment="production")
        result = adapter.get_secret_json("missing/json")

        assert isinstance(result, Failure)
        assert isinstance(result.error, SecretsError)
        assert result.error.code == ErrorCode.SECRET_NOT_FOUND

    @mock_aws
    def test_get_secret_json_empty_object(self):
        """Test get_secret_json handles empty JSON object."""
        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret_id = "/dashtam/production/empty/json"
        client.create_secret(Name=secret_id, SecretString="{}")

        adapter = AWSAdapter(environment="production")
        result = adapter.get_secret_json("empty/json")

        assert isinstance(result, Success)
        assert result.value == {}

    @mock_aws
    def test_get_secret_json_nested_object(self):
        """Test get_secret_json handles nested JSON structures."""
        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret_id = "/dashtam/production/nested/config"
        nested_json = json.dumps(
            {
                "database": {"host": "localhost", "port": "5432"},
                "credentials": {"user": "admin", "password": "secret"},
            }
        )
        client.create_secret(Name=secret_id, SecretString=nested_json)

        adapter = AWSAdapter(environment="production")
        result = adapter.get_secret_json("nested/config")

        assert isinstance(result, Success)
        assert result.value["database"]["host"] == "localhost"
        assert result.value["credentials"]["password"] == "secret"

    @mock_aws
    def test_get_secret_json_caches_parsed_value(self):
        """Test get_secret_json caches the original string (not parsed dict)."""
        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret_id = "/dashtam/production/cached/json"
        json_secret = json.dumps({"key": "value"})
        client.create_secret(Name=secret_id, SecretString=json_secret)

        adapter = AWSAdapter(environment="production")

        # First call
        result1 = adapter.get_secret_json("cached/json")
        assert isinstance(result1, Success)

        # Check cache contains string (not dict)
        assert secret_id in adapter._cache
        assert isinstance(adapter._cache[secret_id], str)
        assert adapter._cache[secret_id] == json_secret

        # Second call uses cache and parses again
        result2 = adapter.get_secret_json("cached/json")
        assert isinstance(result2, Success)
        assert result2.value == {"key": "value"}


@pytest.mark.unit
class TestAWSAdapterErrorHandling:
    """Test AWSAdapter error handling."""

    @mock_aws
    def test_get_secret_handles_resource_not_found_exception(self):
        """Test get_secret properly handles ResourceNotFoundException."""
        adapter = AWSAdapter(environment="production")
        result = adapter.get_secret("nonexistent/path")

        assert isinstance(result, Failure)
        assert result.error.code == ErrorCode.SECRET_NOT_FOUND

    @mock_aws
    def test_adapter_works_across_different_environments(self):
        """Test adapter correctly segregates secrets by environment."""
        client = boto3.client("secretsmanager", region_name="us-east-1")

        # Create same secret in different environments
        client.create_secret(
            Name="/dashtam/production/shared/secret", SecretString="prod_value"
        )
        client.create_secret(
            Name="/dashtam/staging/shared/secret", SecretString="staging_value"
        )

        prod_adapter = AWSAdapter(environment="production")
        staging_adapter = AWSAdapter(environment="staging")

        prod_result = prod_adapter.get_secret("shared/secret")
        staging_result = staging_adapter.get_secret("shared/secret")

        assert prod_result.value == "prod_value"
        assert staging_result.value == "staging_value"
