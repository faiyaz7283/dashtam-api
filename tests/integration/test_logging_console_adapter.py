"""Integration tests for ConsoleAdapter with real structlog.

Tests cover:
- Real structured logging output
- Context binding with real logger
- Log format verification (JSON vs human-readable)
- All log levels with real structlog

Architecture:
- Integration tests with REAL structlog (not mocked)
- Tests actual logging behavior and output
- Fresh ConsoleAdapter instances per test (bypass singleton)
"""

import json
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from src.infrastructure.logging.console_adapter import ConsoleAdapter


@pytest.mark.integration
class TestConsoleAdapterIntegration:
    """Integration tests for ConsoleAdapter with real structlog."""

    def test_console_adapter_logs_to_stdout(self):
        """Test ConsoleAdapter writes to stdout."""
        # Capture stdout
        captured_output = StringIO()
        
        with patch.object(sys, 'stdout', captured_output):
            adapter = ConsoleAdapter(use_json=True)
            adapter.info("Test message", user_id="123")
        
        output = captured_output.getvalue()
        
        # Should have logged something
        assert len(output) > 0
        assert "Test message" in output

    def test_json_mode_produces_valid_json(self):
        """Test JSON mode produces parseable JSON output."""
        captured_output = StringIO()
        
        with patch.object(sys, 'stdout', captured_output):
            adapter = ConsoleAdapter(use_json=True)
            adapter.info("JSON test", key="value", count=42)
        
        output = captured_output.getvalue().strip()
        
        # Should be valid JSON
        log_data = json.loads(output)
        assert log_data["event"] == "JSON test"
        assert log_data["key"] == "value"
        assert log_data["count"] == 42

    def test_all_log_levels_work(self):
        """Test all log levels produce output."""
        captured_output = StringIO()
        
        with patch.object(sys, 'stdout', captured_output):
            adapter = ConsoleAdapter(use_json=True)
            
            adapter.debug("Debug message")
            adapter.info("Info message")
            adapter.warning("Warning message")
            adapter.error("Error message")
            adapter.critical("Critical message")
        
        output = captured_output.getvalue()
        
        # All levels should be in output (except debug which might be filtered)
        assert "Info message" in output
        assert "Warning message" in output
        assert "Error message" in output
        assert "Critical message" in output

    def test_error_with_exception_includes_error_details(self):
        """Test error() with exception includes error type and message."""
        captured_output = StringIO()
        
        with patch.object(sys, 'stdout', captured_output):
            adapter = ConsoleAdapter(use_json=True)
            
            try:
                raise ValueError("Test error")
            except ValueError as exc:
                adapter.error("Operation failed", error=exc)
        
        output = captured_output.getvalue()
        
        # Should include error details
        log_data = json.loads(output.strip())
        assert log_data["error_type"] == "ValueError"
        assert log_data["error_message"] == "Test error"

    def test_critical_with_exception_includes_error_details(self):
        """Test critical() with exception includes error type and message."""
        captured_output = StringIO()
        
        with patch.object(sys, 'stdout', captured_output):
            adapter = ConsoleAdapter(use_json=True)
            
            try:
                raise Exception("Critical failure")
            except Exception as exc:
                adapter.critical("System down", error=exc)
        
        output = captured_output.getvalue()
        
        log_data = json.loads(output.strip())
        assert log_data["error_type"] == "Exception"
        assert log_data["error_message"] == "Critical failure"

    def test_structured_context_preserved(self):
        """Test structured context is included in output."""
        captured_output = StringIO()
        
        with patch.object(sys, 'stdout', captured_output):
            adapter = ConsoleAdapter(use_json=True)
            
            adapter.info(
                "User action",
                user_id="user-123",
                action="login",
                ip_address="192.168.1.1",
                success=True,
            )
        
        output = captured_output.getvalue()
        log_data = json.loads(output.strip())
        
        # All context should be present
        assert log_data["user_id"] == "user-123"
        assert log_data["action"] == "login"
        assert log_data["ip_address"] == "192.168.1.1"
        assert log_data["success"] is True

    def test_bind_creates_logger_with_persistent_context(self):
        """Test bind() creates logger with context in all subsequent logs."""
        captured_output = StringIO()
        
        with patch.object(sys, 'stdout', captured_output):
            adapter = ConsoleAdapter(use_json=True)
            
            # Bind context
            bound_adapter = adapter.bind(request_id="req-123", user_id="user-456")
            
            # Log multiple messages
            bound_adapter.info("First action")
            bound_adapter.info("Second action")
        
        output = captured_output.getvalue()
        lines = output.strip().split('\n')
        
        # Both logs should have bound context
        log1 = json.loads(lines[0])
        log2 = json.loads(lines[1])
        
        assert log1["request_id"] == "req-123"
        assert log1["user_id"] == "user-456"
        assert log2["request_id"] == "req-123"
        assert log2["user_id"] == "user-456"

    def test_with_context_creates_logger_with_persistent_context(self):
        """Test with_context() works identically to bind()."""
        captured_output = StringIO()
        
        with patch.object(sys, 'stdout', captured_output):
            adapter = ConsoleAdapter(use_json=True)
            
            context_adapter = adapter.with_context(trace_id="trace-789")
            context_adapter.info("Test message")
        
        output = captured_output.getvalue()
        log_data = json.loads(output.strip())
        
        assert log_data["trace_id"] == "trace-789"

    def test_bound_context_does_not_affect_original_logger(self):
        """Test binding context creates new logger without affecting original."""
        captured_output = StringIO()
        
        with patch.object(sys, 'stdout', captured_output):
            adapter = ConsoleAdapter(use_json=True)
            
            # Create bound logger
            bound_adapter = adapter.bind(request_id="req-123")
            
            # Log with original logger
            adapter.info("Original message")
            
            # Log with bound logger  
            bound_adapter.info("Bound message")
        
        output = captured_output.getvalue()
        lines = output.strip().split('\n')
        
        # Original log should NOT have request_id
        log1 = json.loads(lines[0])
        assert "request_id" not in log1
        
        # Bound log should have request_id
        log2 = json.loads(lines[1])
        assert log2["request_id"] == "req-123"

    def test_nested_binding_accumulates_context(self):
        """Test binding context multiple times accumulates all context."""
        captured_output = StringIO()
        
        with patch.object(sys, 'stdout', captured_output):
            adapter = ConsoleAdapter(use_json=True)
            
            # First bind
            adapter1 = adapter.bind(request_id="req-123")
            
            # Second bind on top of first
            adapter2 = adapter1.bind(user_id="user-456")
            
            # Log with doubly-bound logger
            adapter2.info("Test message")
        
        output = captured_output.getvalue()
        log_data = json.loads(output.strip())
        
        # Should have both contexts
        assert log_data["request_id"] == "req-123"
        assert log_data["user_id"] == "user-456"

    def test_complex_nested_data_structures(self):
        """Test logging with complex nested data structures."""
        captured_output = StringIO()
        
        with patch.object(sys, 'stdout', captured_output):
            adapter = ConsoleAdapter(use_json=True)
            
            adapter.info(
                "Complex data",
                user={
                    "id": "123",
                    "email": "test@example.com",
                    "roles": ["admin", "user"],
                },
                metadata={
                    "source": "api",
                    "version": "1.0",
                },
            )
        
        output = captured_output.getvalue()
        log_data = json.loads(output.strip())
        
        # Complex structures should be preserved
        assert log_data["user"]["id"] == "123"
        assert log_data["user"]["roles"] == ["admin", "user"]
        assert log_data["metadata"]["source"] == "api"

    def test_multiple_adapters_are_independent(self):
        """Test multiple ConsoleAdapter instances are independent."""
        captured_output = StringIO()
        
        with patch.object(sys, 'stdout', captured_output):
            adapter1 = ConsoleAdapter(use_json=True)
            adapter2 = ConsoleAdapter(use_json=True)
            
            # Bind different context to each
            bound1 = adapter1.bind(logger="adapter1")
            bound2 = adapter2.bind(logger="adapter2")
            
            bound1.info("Message 1")
            bound2.info("Message 2")
        
        output = captured_output.getvalue()
        lines = output.strip().split('\n')
        
        log1 = json.loads(lines[0])
        log2 = json.loads(lines[1])
        
        # Each should have its own context
        assert log1["logger"] == "adapter1"
        assert log2["logger"] == "adapter2"
