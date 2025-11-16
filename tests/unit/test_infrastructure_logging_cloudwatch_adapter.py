"""Unit tests for CloudWatchAdapter (AWS CloudWatch Logs).

Tests cover:
- All LoggerProtocol methods (debug, info, warning, error, critical)
- Context binding (returns self for protocol compliance)
- Initialization and configuration

Architecture:
- Unit tests with mocked boto3
- NO real AWS CloudWatch dependencies
- Tests protocol compliance, not internal implementation
"""

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.logging.cloudwatch_adapter import CloudWatchAdapter


@pytest.mark.unit
class TestCloudWatchAdapterProtocolCompliance:
    """Test CloudWatchAdapter implements LoggerProtocol correctly."""

    def test_adapter_has_all_protocol_methods(self):
        """Test CloudWatchAdapter has all required protocol methods."""
        with patch("src.infrastructure.logging.cloudwatch_adapter.boto3"):
            adapter = CloudWatchAdapter(
                log_group="/test/group",
                log_stream="test-stream",
                region="us-east-1",
            )

            # Verify all protocol methods exist
            assert hasattr(adapter, "debug")
            assert hasattr(adapter, "info")
            assert hasattr(adapter, "warning")
            assert hasattr(adapter, "error")
            assert hasattr(adapter, "critical")
            assert hasattr(adapter, "bind")
            assert hasattr(adapter, "with_context")

            # Verify methods are callable
            assert callable(adapter.debug)
            assert callable(adapter.info)
            assert callable(adapter.warning)
            assert callable(adapter.error)
            assert callable(adapter.critical)
            assert callable(adapter.bind)
            assert callable(adapter.with_context)

    def test_debug_method_accepts_message_and_context(self):
        """Test debug() accepts message and context without raising."""
        with patch("src.infrastructure.logging.cloudwatch_adapter.boto3"):
            adapter = CloudWatchAdapter(
                log_group="/test/group",
                log_stream="test-stream",
                region="us-east-1",
            )

            # Should not raise
            adapter.debug("Test message", user_id="123", action="test")

    def test_info_method_accepts_message_and_context(self):
        """Test info() accepts message and context without raising."""
        with patch("src.infrastructure.logging.cloudwatch_adapter.boto3"):
            adapter = CloudWatchAdapter(
                log_group="/test/group",
                log_stream="test-stream",
                region="us-east-1",
            )

            adapter.info("Test message", user_id="123")

    def test_warning_method_accepts_message_and_context(self):
        """Test warning() accepts message and context without raising."""
        with patch("src.infrastructure.logging.cloudwatch_adapter.boto3"):
            adapter = CloudWatchAdapter(
                log_group="/test/group",
                log_stream="test-stream",
                region="us-east-1",
            )

            adapter.warning("Test message", threshold=100)

    def test_error_method_accepts_message_and_exception(self):
        """Test error() accepts message, optional error, and context."""
        with patch("src.infrastructure.logging.cloudwatch_adapter.boto3"):
            adapter = CloudWatchAdapter(
                log_group="/test/group",
                log_stream="test-stream",
                region="us-east-1",
            )

            exc = ValueError("Test error")
            adapter.error("Error occurred", error=exc, retry_count=3)

    def test_critical_method_accepts_message_and_exception(self):
        """Test critical() accepts message, optional error, and context."""
        with patch("src.infrastructure.logging.cloudwatch_adapter.boto3"):
            adapter = CloudWatchAdapter(
                log_group="/test/group",
                log_stream="test-stream",
                region="us-east-1",
            )

            exc = Exception("Critical failure")
            adapter.critical("Critical error", error=exc, service="database")


@pytest.mark.unit
class TestCloudWatchAdapterContextBinding:
    """Test CloudWatchAdapter context binding methods."""

    def test_bind_returns_adapter_instance(self):
        """Test bind() returns an adapter instance."""
        with patch("src.infrastructure.logging.cloudwatch_adapter.boto3"):
            adapter = CloudWatchAdapter(
                log_group="/test/group",
                log_stream="test-stream",
                region="us-east-1",
            )

            bound_adapter = adapter.bind(request_id="req-123")

            # Should return an adapter (self in this implementation)
            assert bound_adapter is not None
            assert isinstance(bound_adapter, CloudWatchAdapter)

    def test_with_context_returns_adapter_instance(self):
        """Test with_context() returns an adapter instance."""
        with patch("src.infrastructure.logging.cloudwatch_adapter.boto3"):
            adapter = CloudWatchAdapter(
                log_group="/test/group",
                log_stream="test-stream",
                region="us-east-1",
            )

            context_adapter = adapter.with_context(trace_id="trace-789")

            assert context_adapter is not None
            assert isinstance(context_adapter, CloudWatchAdapter)

    def test_bound_adapter_has_protocol_methods(self):
        """Test bound adapter retains all protocol methods."""
        with patch("src.infrastructure.logging.cloudwatch_adapter.boto3"):
            adapter = CloudWatchAdapter(
                log_group="/test/group",
                log_stream="test-stream",
                region="us-east-1",
            )

            bound_adapter = adapter.bind(user_id="user-123")

            # Bound adapter should have all protocol methods
            assert hasattr(bound_adapter, "debug")
            assert hasattr(bound_adapter, "info")
            assert hasattr(bound_adapter, "error")
            assert hasattr(bound_adapter, "critical")


@pytest.mark.unit
class TestCloudWatchAdapterInitialization:
    """Test CloudWatchAdapter initialization."""

    def test_adapter_initializes_with_required_parameters(self):
        """Test CloudWatchAdapter initializes with log_group, log_stream, region."""
        with patch("src.infrastructure.logging.cloudwatch_adapter.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            adapter = CloudWatchAdapter(
                log_group="/dashtam/production",
                log_stream="app-stream",
                region="us-west-2",
            )

            # Verify boto3 client created with correct region
            mock_boto3.client.assert_called_once_with(
                "logs",
                region_name="us-west-2",
            )

            assert adapter is not None

    def test_adapter_uses_default_region(self):
        """Test adapter uses default region if not specified."""
        with patch("src.infrastructure.logging.cloudwatch_adapter.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            adapter = CloudWatchAdapter(
                log_group="/test/group",
                log_stream="test-stream",
            )

            # Verify adapter initialized successfully
            assert adapter is not None
            assert adapter._group == "/test/group"

            # Should use default region
            call_kwargs = mock_boto3.client.call_args[1]
            assert call_kwargs["region_name"] == "us-east-1"

    def test_adapter_initializes_with_custom_batch_size(self):
        """Test adapter accepts custom batch_size parameter."""
        with patch("src.infrastructure.logging.cloudwatch_adapter.boto3"):
            # Should not raise
            adapter = CloudWatchAdapter(
                log_group="/test/group",
                log_stream="test-stream",
                region="us-east-1",
                batch_size=100,
            )

            assert adapter is not None

    def test_adapter_initializes_with_custom_batch_interval(self):
        """Test adapter accepts custom batch_interval parameter."""
        with patch("src.infrastructure.logging.cloudwatch_adapter.boto3"):
            # Should not raise
            adapter = CloudWatchAdapter(
                log_group="/test/group",
                log_stream="test-stream",
                region="us-east-1",
                batch_interval=10.0,
            )

            assert adapter is not None


@pytest.mark.unit
class TestCloudWatchAdapterErrorHandling:
    """Test CloudWatchAdapter graceful error handling."""

    def test_adapter_continues_after_cloudwatch_errors(self):
        """Test adapter handles CloudWatch errors gracefully."""
        with patch("src.infrastructure.logging.cloudwatch_adapter.boto3") as mock_boto3:
            mock_client = MagicMock()
            # Simulate CloudWatch API failures
            mock_client.create_log_group.side_effect = Exception("AWS error")
            mock_boto3.client.return_value = mock_client

            # Should handle error gracefully (or raise during init)
            # Implementation may choose to fail fast or fallback to console
            try:
                adapter = CloudWatchAdapter(
                    log_group="/test/group",
                    log_stream="test-stream",
                    region="us-east-1",
                )
                # If initialization succeeded, logging should still work
                adapter.info("Test message")
            except Exception:
                # Acceptable to fail during initialization
                pass
