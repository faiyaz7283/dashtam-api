"""Unit tests for get_logger() container function.

Tests cover:
- Logger adapter selection based on ENVIRONMENT
- Singleton pattern (same instance returned)
- Protocol compliance
- Environment-specific configuration

Architecture:
- Unit tests with mocked settings and adapters
- Tests centralized dependency injection pattern
"""

from unittest.mock import patch, MagicMock

import pytest

from src.core.container import get_logger
from src.domain.protocols.logger_protocol import LoggerProtocol


@pytest.mark.unit
class TestGetLoggerContainer:
    """Test get_logger() container function."""

    def test_get_logger_returns_console_adapter_in_development(self):
        """Test get_logger() returns ConsoleAdapter in development environment."""
        with patch("src.core.container.infrastructure.settings") as mock_settings:
            mock_settings.environment = "development"

            # Clear cache to force new call
            get_logger.cache_clear()

            with patch(
                "src.infrastructure.logging.console_adapter.ConsoleAdapter"
            ) as mock_console:
                mock_adapter = MagicMock()
                mock_console.return_value = mock_adapter

                logger = get_logger()

                # Should create ConsoleAdapter
                mock_console.assert_called_once()
                assert logger == mock_adapter

    def test_get_logger_returns_console_adapter_in_testing(self):
        """Test get_logger() returns ConsoleAdapter in testing environment."""
        with patch("src.core.container.infrastructure.settings") as mock_settings:
            mock_settings.environment = "testing"

            get_logger.cache_clear()

            with patch(
                "src.infrastructure.logging.console_adapter.ConsoleAdapter"
            ) as mock_console:
                mock_adapter = MagicMock()
                mock_console.return_value = mock_adapter

                logger = get_logger()

                mock_console.assert_called_once()
                assert logger == mock_adapter

    def test_get_logger_returns_cloudwatch_adapter_in_production(self):
        """Test get_logger() returns CloudWatchAdapter in production environment."""
        with patch("src.core.container.infrastructure.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.aws_region = "us-east-1"

            get_logger.cache_clear()

            with patch(
                "src.infrastructure.logging.cloudwatch_adapter.CloudWatchAdapter"
            ) as mock_cloudwatch:
                mock_adapter = MagicMock()
                mock_cloudwatch.return_value = mock_adapter

                logger = get_logger()

                # CloudWatchAdapter is called with log_group, log_stream, region
                # (dynamically generated from hostname and date)
                assert mock_cloudwatch.call_count == 1
                call_kwargs = mock_cloudwatch.call_args[1]
                assert call_kwargs["region"] == "us-east-1"
                assert "/dashtam/production/app" in call_kwargs["log_group"]
                assert logger == mock_adapter

    def test_get_logger_uses_singleton_pattern(self):
        """Test get_logger() returns same instance on multiple calls."""
        with patch("src.core.container.infrastructure.settings") as mock_settings:
            mock_settings.environment = "development"

            get_logger.cache_clear()

            with patch(
                "src.infrastructure.logging.console_adapter.ConsoleAdapter"
            ) as mock_console:
                mock_adapter = MagicMock()
                mock_console.return_value = mock_adapter

                # Call multiple times
                logger1 = get_logger()
                logger2 = get_logger()
                logger3 = get_logger()

                # Should create adapter only once
                mock_console.assert_called_once()

                # All references should be the same instance
                assert logger1 is logger2
                assert logger2 is logger3

    def test_get_logger_returns_protocol_compliant_adapter(self):
        """Test get_logger() returns LoggerProtocol-compliant adapter."""
        with patch("src.core.container.infrastructure.settings") as mock_settings:
            mock_settings.environment = "development"

            get_logger.cache_clear()

            with patch(
                "src.infrastructure.logging.console_adapter.ConsoleAdapter"
            ) as mock_console:
                # Create mock adapter with protocol methods
                mock_adapter = MagicMock(spec=LoggerProtocol)
                mock_console.return_value = mock_adapter

                logger = get_logger()

                # Verify protocol methods exist
                assert hasattr(logger, "debug")
                assert hasattr(logger, "info")
                assert hasattr(logger, "warning")
                assert hasattr(logger, "error")
                assert hasattr(logger, "critical")
                assert hasattr(logger, "bind")
                assert hasattr(logger, "with_context")


@pytest.mark.unit
class TestGetLoggerEdgeCases:
    """Test get_logger() edge cases and error conditions."""

    def test_get_logger_with_unknown_environment_uses_console(self):
        """Test get_logger() defaults to ConsoleAdapter for unknown environment."""
        with patch("src.core.container.infrastructure.settings") as mock_settings:
            mock_settings.environment = "unknown_env"

            get_logger.cache_clear()

            with patch(
                "src.infrastructure.logging.console_adapter.ConsoleAdapter"
            ) as mock_console:
                mock_adapter = MagicMock()
                mock_console.return_value = mock_adapter

                logger = get_logger()

                # Should fall back to ConsoleAdapter
                mock_console.assert_called_once()
                assert logger == mock_adapter

    def test_get_logger_cache_can_be_cleared(self):
        """Test get_logger() cache can be cleared and new instance created."""
        with patch("src.core.container.infrastructure.settings") as mock_settings:
            mock_settings.environment = "development"

            get_logger.cache_clear()

            with patch(
                "src.infrastructure.logging.console_adapter.ConsoleAdapter"
            ) as mock_console:
                mock_adapter1 = MagicMock()
                mock_adapter2 = MagicMock()
                mock_console.side_effect = [mock_adapter1, mock_adapter2]

                # First call
                logger1 = get_logger()
                assert logger1 == mock_adapter1

                # Clear cache
                get_logger.cache_clear()

                # Second call should create new instance
                logger2 = get_logger()
                assert logger2 == mock_adapter2

                # Should have called ConsoleAdapter twice
                assert mock_console.call_count == 2


@pytest.mark.unit
class TestGetLoggerEnvironmentSpecific:
    """Test get_logger() with environment-specific configurations."""

    def test_get_logger_ci_environment_uses_console(self):
        """Test get_logger() uses ConsoleAdapter in CI environment."""
        with patch("src.core.container.infrastructure.settings") as mock_settings:
            mock_settings.environment = "ci"

            get_logger.cache_clear()

            with patch(
                "src.infrastructure.logging.console_adapter.ConsoleAdapter"
            ) as mock_console:
                mock_adapter = MagicMock()
                mock_console.return_value = mock_adapter

                logger = get_logger()

                mock_console.assert_called_once()
                assert logger == mock_adapter

    def test_get_logger_production_uses_correct_aws_config(self):
        """Test get_logger() uses correct AWS configuration in production."""
        with patch("src.core.container.infrastructure.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.aws_region = "ap-southeast-1"

            get_logger.cache_clear()

            with patch(
                "src.infrastructure.logging.cloudwatch_adapter.CloudWatchAdapter"
            ) as mock_cloudwatch:
                mock_adapter = MagicMock()
                mock_cloudwatch.return_value = mock_adapter

                logger = get_logger()

                # Verify correct adapter returned
                assert logger == mock_adapter

                # Verify correct AWS region passed
                assert mock_cloudwatch.call_count == 1
                call_kwargs = mock_cloudwatch.call_args[1]
                assert call_kwargs["region"] == "ap-southeast-1"
