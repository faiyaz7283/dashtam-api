"""Unit tests for ConsoleAdapter (structured console logging).

Tests cover:
- All LoggerProtocol methods (debug, info, warning, error, critical)
- Context binding and structured data
- Log level filtering
- Structured output format
- Edge cases (None values, empty contexts)

Architecture:
- Unit tests with mocked structlog
- NO real logging dependencies
- Tests protocol compliance
"""

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.logging.console_adapter import ConsoleAdapter


@pytest.mark.unit
class TestConsoleAdapterLogging:
    """Test ConsoleAdapter logging methods."""

    def test_debug_logs_message_with_context(self):
        """Test debug() logs message with structured context."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            
            adapter = ConsoleAdapter()
            adapter.debug("Debug message", user_id="123", action="test")
            
            mock_logger.debug.assert_called_once_with(
                "Debug message",
                user_id="123",
                action="test",
            )

    def test_info_logs_message_with_context(self):
        """Test info() logs message with structured context."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            
            adapter = ConsoleAdapter()
            adapter.info("Info message", request_id="abc-123", duration_ms=150)
            
            mock_logger.info.assert_called_once_with(
                "Info message",
                request_id="abc-123",
                duration_ms=150,
            )

    def test_warning_logs_message_with_context(self):
        """Test warning() logs message with structured context."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            
            adapter = ConsoleAdapter()
            adapter.warning("Warning message", threshold_exceeded=True, value=100)
            
            mock_logger.warning.assert_called_once_with(
                "Warning message",
                threshold_exceeded=True,
                value=100,
            )

    def test_error_logs_message_with_context(self):
        """Test error() logs message with structured context."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            
            adapter = ConsoleAdapter()
            adapter.error("Error occurred", error_code="E001", retry_count=3)
            
            mock_logger.error.assert_called_once_with(
                "Error occurred",
                error_code="E001",
                retry_count=3,
            )

    def test_critical_logs_message_with_context(self):
        """Test critical() logs message with structured context."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            
            adapter = ConsoleAdapter()
            adapter.critical("Critical failure", service="database", health="down")
            
            mock_logger.critical.assert_called_once_with(
                "Critical failure",
                service="database",
                health="down",
            )

    def test_logs_with_no_context(self):
        """Test logging with no additional context."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            
            adapter = ConsoleAdapter()
            adapter.info("Simple message")
            
            mock_logger.info.assert_called_once_with("Simple message")

    def test_logs_with_nested_dict_context(self):
        """Test logging with nested dictionary context."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            
            adapter = ConsoleAdapter()
            adapter.info(
                "Complex event",
                user={"id": "123", "email": "test@example.com"},
                metadata={"source": "api", "version": "1.0"},
            )
            
            mock_logger.info.assert_called_once_with(
                "Complex event",
                user={"id": "123", "email": "test@example.com"},
                metadata={"source": "api", "version": "1.0"},
            )

    def test_logs_with_none_values(self):
        """Test logging handles None values correctly."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            
            adapter = ConsoleAdapter()
            adapter.info("Message with None", user_id=None, optional_field=None)
            
            mock_logger.info.assert_called_once_with(
                "Message with None",
                user_id=None,
                optional_field=None,
            )


@pytest.mark.unit
class TestConsoleAdapterContextBinding:
    """Test ConsoleAdapter context binding methods."""

    def test_bind_returns_new_adapter_with_bound_context(self):
        """Test bind() returns new adapter with additional context."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_bound_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            mock_logger.bind.return_value = mock_bound_logger
            
            adapter = ConsoleAdapter()
            bound_adapter = adapter.bind(request_id="req-123", user_id="user-456")
            
            # Verify bind was called on underlying logger
            mock_logger.bind.assert_called_once_with(
                request_id="req-123",
                user_id="user-456",
            )
            
            # Verify new adapter has bound logger
            assert bound_adapter is not adapter
            assert bound_adapter._logger == mock_bound_logger

    def test_with_context_returns_new_adapter_with_bound_context(self):
        """Test with_context() returns new adapter (alias for bind)."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_bound_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            mock_logger.bind.return_value = mock_bound_logger
            
            adapter = ConsoleAdapter()
            context_adapter = adapter.with_context(trace_id="trace-789")
            
            mock_logger.bind.assert_called_once_with(trace_id="trace-789")
            assert context_adapter is not adapter
            assert context_adapter._logger == mock_bound_logger

    def test_bound_context_persists_across_logs(self):
        """Test bound context is included in all subsequent logs."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_bound_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            mock_logger.bind.return_value = mock_bound_logger
            
            adapter = ConsoleAdapter()
            bound_adapter = adapter.bind(request_id="req-123")
            
            # Log with bound adapter
            bound_adapter.info("First message", action="create")
            bound_adapter.info("Second message", action="update")
            
            # Both logs should use bound logger
            assert mock_bound_logger.info.call_count == 2
            mock_bound_logger.info.assert_any_call("First message", action="create")
            mock_bound_logger.info.assert_any_call("Second message", action="update")

    def test_bind_with_empty_context(self):
        """Test bind() with no context returns same behavior."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_bound_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            mock_logger.bind.return_value = mock_bound_logger
            
            adapter = ConsoleAdapter()
            bound_adapter = adapter.bind()
            
            # bind() called with no arguments
            mock_logger.bind.assert_called_once_with()
            assert bound_adapter is not adapter


@pytest.mark.unit
class TestConsoleAdapterInitialization:
    """Test ConsoleAdapter initialization and configuration."""

    def test_adapter_initializes_with_structlog(self):
        """Test ConsoleAdapter initializes structlog logger."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            
            adapter = ConsoleAdapter()
            
            mock_structlog.get_logger.assert_called_once()
            assert adapter._logger == mock_logger

    def test_multiple_adapters_get_independent_loggers(self):
        """Test multiple ConsoleAdapter instances are independent."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger1 = MagicMock()
            mock_logger2 = MagicMock()
            mock_structlog.get_logger.side_effect = [mock_logger1, mock_logger2]
            
            adapter1 = ConsoleAdapter()
            adapter2 = ConsoleAdapter()
            
            assert adapter1._logger == mock_logger1
            assert adapter2._logger == mock_logger2
            assert adapter1._logger is not adapter2._logger


@pytest.mark.unit
class TestConsoleAdapterEdgeCases:
    """Test ConsoleAdapter edge cases and error conditions."""

    def test_logs_with_special_characters_in_message(self):
        """Test logging handles special characters in message."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            
            adapter = ConsoleAdapter()
            special_message = "Error: \"Invalid\" \n\t chars & symbols"
            adapter.error(special_message, code="E001")
            
            mock_logger.error.assert_called_once_with(special_message, code="E001")

    def test_logs_with_unicode_characters(self):
        """Test logging handles unicode characters."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            
            adapter = ConsoleAdapter()
            adapter.info("Message with unicode: 世界 🌍", language="international")
            
            mock_logger.info.assert_called_once_with(
                "Message with unicode: 世界 🌍",
                language="international",
            )

    def test_logs_with_numeric_context_values(self):
        """Test logging handles numeric context values."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            
            adapter = ConsoleAdapter()
            adapter.info(
                "Metrics",
                count=100,
                percentage=95.5,
                is_active=True,
            )
            
            mock_logger.info.assert_called_once_with(
                "Metrics",
                count=100,
                percentage=95.5,
                is_active=True,
            )

    def test_logs_with_list_context_values(self):
        """Test logging handles list context values."""
        with patch("src.infrastructure.logging.console_adapter.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger
            
            adapter = ConsoleAdapter()
            adapter.info("Process items", items=["item1", "item2", "item3"], count=3)
            
            mock_logger.info.assert_called_once_with(
                "Process items",
                items=["item1", "item2", "item3"],
                count=3,
            )
