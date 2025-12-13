"""Unit tests for container secrets backend selection.

Tests cover:
- get_secrets() returns correct adapter based on SECRETS_BACKEND env var
- Backend selection logic (env, aws)
- Error handling for unsupported backends
- Environment-specific adapter configuration

Architecture:
- Unit tests with mocked environment variables
- Tests container backend selection logic
- NO real adapter instantiation (mocked imports)
"""

import os
from unittest.mock import Mock, patch

import pytest

from src.core.container import get_secrets


@pytest.mark.unit
class TestContainerSecretsBackendSelection:
    """Test container get_secrets() backend selection logic."""

    def test_get_secrets_returns_env_adapter_by_default(self):
        """Test get_secrets returns EnvAdapter when no SECRETS_BACKEND set."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear any previous cache
            get_secrets.cache_clear()

            with patch(
                "src.infrastructure.secrets.env_adapter.EnvAdapter"
            ) as mock_env_adapter_class:
                mock_adapter = Mock()
                mock_env_adapter_class.return_value = mock_adapter

                result = get_secrets()

                assert result is mock_adapter
                mock_env_adapter_class.assert_called_once()

    def test_get_secrets_returns_env_adapter_explicitly(self):
        """Test get_secrets returns EnvAdapter when SECRETS_BACKEND=env."""
        with patch.dict(os.environ, {"SECRETS_BACKEND": "env"}):
            get_secrets.cache_clear()

            with patch(
                "src.infrastructure.secrets.env_adapter.EnvAdapter"
            ) as mock_env_adapter_class:
                mock_adapter = Mock()
                mock_env_adapter_class.return_value = mock_adapter

                result = get_secrets()

                assert result is mock_adapter
                mock_env_adapter_class.assert_called_once()

    def test_get_secrets_returns_aws_adapter(self):
        """Test get_secrets returns AWSAdapter when SECRETS_BACKEND=aws."""
        with patch.dict(
            os.environ, {"SECRETS_BACKEND": "aws", "ENVIRONMENT": "production"}
        ):
            get_secrets.cache_clear()

            with patch(
                "src.infrastructure.secrets.aws_adapter.AWSAdapter"
            ) as mock_aws_adapter_class:
                mock_adapter = Mock()
                mock_aws_adapter_class.return_value = mock_adapter

                result = get_secrets()

                assert result is mock_adapter
                mock_aws_adapter_class.assert_called_once()

    def test_get_secrets_aws_adapter_uses_correct_region(self):
        """Test AWSAdapter initialized with correct region."""
        with patch.dict(
            os.environ,
            {
                "SECRETS_BACKEND": "aws",
                "ENVIRONMENT": "staging",
                "AWS_REGION": "us-west-2",
            },
        ):
            get_secrets.cache_clear()

            with patch(
                "src.infrastructure.secrets.aws_adapter.AWSAdapter"
            ) as mock_aws_adapter_class:
                mock_adapter = Mock()
                mock_aws_adapter_class.return_value = mock_adapter

                # Import settings to get environment
                from src.core.config import settings

                get_secrets()

                # Verify AWSAdapter called with correct parameters
                mock_aws_adapter_class.assert_called_once_with(
                    environment=settings.environment, region="us-west-2"
                )

    def test_get_secrets_aws_adapter_defaults_to_us_east_1(self):
        """Test AWSAdapter defaults to us-east-1 when AWS_REGION not set."""
        with patch.dict(
            os.environ, {"SECRETS_BACKEND": "aws", "ENVIRONMENT": "production"}
        ):
            get_secrets.cache_clear()

            with patch(
                "src.infrastructure.secrets.aws_adapter.AWSAdapter"
            ) as mock_aws_adapter_class:
                mock_adapter = Mock()
                mock_aws_adapter_class.return_value = mock_adapter

                from src.core.config import settings

                get_secrets()

                # Verify default region is us-east-1
                mock_aws_adapter_class.assert_called_once_with(
                    environment=settings.environment, region="us-east-1"
                )

    def test_get_secrets_raises_error_for_unsupported_backend(self):
        """Test get_secrets raises ValueError for unsupported backend."""
        with patch.dict(os.environ, {"SECRETS_BACKEND": "vault"}):
            get_secrets.cache_clear()

            with pytest.raises(ValueError) as exc_info:
                get_secrets()

            assert "Unsupported SECRETS_BACKEND: vault" in str(exc_info.value)
            assert "'env', 'aws'" in str(exc_info.value)

    def test_get_secrets_caches_adapter_instance(self):
        """Test get_secrets caches adapter instance (lru_cache)."""
        with patch.dict(os.environ, {"SECRETS_BACKEND": "env"}):
            get_secrets.cache_clear()

            with patch(
                "src.infrastructure.secrets.env_adapter.EnvAdapter"
            ) as mock_env_adapter_class:
                mock_adapter = Mock()
                mock_env_adapter_class.return_value = mock_adapter

                # First call
                result1 = get_secrets()
                assert result1 is mock_adapter

                # Second call should return cached instance
                result2 = get_secrets()
                assert result2 is result1

                # EnvAdapter should only be instantiated once
                assert mock_env_adapter_class.call_count == 1

    def test_get_secrets_different_backends_after_cache_clear(self):
        """Test get_secrets returns different adapter after cache clear."""
        # First call with env backend
        with patch.dict(os.environ, {"SECRETS_BACKEND": "env"}):
            get_secrets.cache_clear()

            with patch(
                "src.infrastructure.secrets.env_adapter.EnvAdapter"
            ) as mock_env_adapter_class:
                mock_env_adapter = Mock()
                mock_env_adapter_class.return_value = mock_env_adapter

                result_env = get_secrets()
                assert result_env is mock_env_adapter

        # Clear cache and switch to AWS backend
        get_secrets.cache_clear()

        with patch.dict(
            os.environ, {"SECRETS_BACKEND": "aws", "ENVIRONMENT": "production"}
        ):
            with patch(
                "src.infrastructure.secrets.aws_adapter.AWSAdapter"
            ) as mock_aws_adapter_class:
                mock_aws_adapter = Mock()
                mock_aws_adapter_class.return_value = mock_aws_adapter

                result_aws = get_secrets()
                assert result_aws is mock_aws_adapter
                assert result_aws is not result_env


@pytest.mark.unit
class TestContainerSecretsProtocolCompliance:
    """Test container returns adapters that satisfy SecretsProtocol."""

    def test_env_adapter_satisfies_protocol(self):
        """Test EnvAdapter from container satisfies SecretsProtocol."""
        with patch.dict(os.environ, {"SECRETS_BACKEND": "env"}):
            get_secrets.cache_clear()

            adapter = get_secrets()

            # Verify protocol methods exist
            assert hasattr(adapter, "get_secret")
            assert hasattr(adapter, "get_secret_json")
            assert hasattr(adapter, "refresh_cache")
            assert callable(adapter.get_secret)
            assert callable(adapter.get_secret_json)
            assert callable(adapter.refresh_cache)

    def test_aws_adapter_satisfies_protocol(self):
        """Test AWSAdapter from container satisfies SecretsProtocol."""
        with patch.dict(
            os.environ, {"SECRETS_BACKEND": "aws", "ENVIRONMENT": "production"}
        ):
            get_secrets.cache_clear()

            # Mock boto3 to avoid actual AWS dependency
            with patch("boto3.client"):
                adapter = get_secrets()

                # Verify protocol methods exist
                assert hasattr(adapter, "get_secret")
                assert hasattr(adapter, "get_secret_json")
                assert hasattr(adapter, "refresh_cache")
                assert callable(adapter.get_secret)
                assert callable(adapter.get_secret_json)
                assert callable(adapter.refresh_cache)
