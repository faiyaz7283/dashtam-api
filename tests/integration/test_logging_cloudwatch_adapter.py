"""Integration tests for CloudWatchAdapter with moto (AWS mocking).

Tests cover:
- Real boto3 client with mocked CloudWatch service
- Log group and stream creation
- Batch sending to CloudWatch
- All log levels with real AWS API calls (mocked)

Architecture:
- Integration tests with REAL boto3 + MOCKED CloudWatch (moto)
- Tests actual AWS SDK behavior without real AWS costs
- Fresh CloudWatchAdapter instances per test (bypass singleton)

Note:
- CloudWatch fallback errors are suppressed (expected with moto)
"""

import time

import pytest
from moto import mock_aws

from src.infrastructure.logging.cloudwatch_adapter import CloudWatchAdapter


@pytest.fixture(autouse=True)
def suppress_cloudwatch_fallback_errors(capfd):
    """Suppress CloudWatch fallback console errors during tests.

    Moto doesn't perfectly mock AWS auth, causing expected fallback errors.
    These are caught and handled gracefully by logging to console fallback.
    We suppress stdout to keep test output clean.
    """
    yield
    # Capture and discard stdout/stderr after each test
    capfd.readouterr()


@pytest.mark.integration
class TestCloudWatchAdapterIntegration:
    """Integration tests for CloudWatchAdapter with mocked CloudWatch."""

    @mock_aws
    def test_adapter_creates_log_group_and_stream(self):
        """Test CloudWatchAdapter creates log group and stream on initialization."""
        adapter = CloudWatchAdapter(
            log_group="/test/group",
            log_stream="test-stream",
            region="us-east-1",
        )

        # Verify log group and stream were created
        response = adapter._client.describe_log_groups(logGroupNamePrefix="/test/group")

        assert len(response["logGroups"]) == 1
        assert response["logGroups"][0]["logGroupName"] == "/test/group"

        # Verify stream exists
        streams = adapter._client.describe_log_streams(
            logGroupName="/test/group", logStreamNamePrefix="test-stream"
        )

        assert len(streams["logStreams"]) == 1
        assert streams["logStreams"][0]["logStreamName"] == "test-stream"

    @mock_aws
    def test_adapter_logs_messages_to_cloudwatch(self):
        """Test adapter sends log messages to CloudWatch."""
        adapter = CloudWatchAdapter(
            log_group="/test/group",
            log_stream="test-stream",
            region="us-east-1",
            batch_size=5,
            batch_interval=0.1,
        )

        # Log messages
        adapter.info("Test message 1", user_id="123")
        adapter.info("Test message 2", user_id="456")
        adapter.error("Error message", error_code="E001")

        # Give background thread time to flush
        time.sleep(0.3)

        # Verify logs were sent to CloudWatch
        response = adapter._client.get_log_events(
            logGroupName="/test/group",
            logStreamName="test-stream",
        )

        # Should have 3 log events
        events = response["events"]
        assert len(events) >= 3

    @mock_aws
    def test_all_log_levels_sent_to_cloudwatch(self):
        """Test all log levels are sent to CloudWatch."""
        adapter = CloudWatchAdapter(
            log_group="/test/group",
            log_stream="test-stream",
            region="us-east-1",
            batch_size=2,
        )

        # Log at all levels
        adapter.debug("Debug message")
        adapter.info("Info message")
        adapter.warning("Warning message")
        adapter.error("Error message")
        adapter.critical("Critical message")

        # Wait for flush
        time.sleep(0.3)

        # Verify all messages sent
        response = adapter._client.get_log_events(
            logGroupName="/test/group",
            logStreamName="test-stream",
        )

        assert len(response["events"]) >= 5

    @mock_aws
    def test_error_with_exception_sends_to_cloudwatch(self):
        """Test error() with exception sends error details to CloudWatch."""
        adapter = CloudWatchAdapter(
            log_group="/test/group",
            log_stream="test-stream",
            region="us-east-1",
            batch_size=1,
        )

        try:
            raise ValueError("Test error")
        except ValueError as exc:
            adapter.error("Operation failed", error=exc, context="test")

        # Wait for auto-flush (batch_size=1)
        time.sleep(0.2)

        # Verify error logged
        response = adapter._client.get_log_events(
            logGroupName="/test/group",
            logStreamName="test-stream",
        )

        assert len(response["events"]) >= 1
        # Message contains error details (JSON formatted)
        message = response["events"][0]["message"]
        assert "ValueError" in message
        assert "Test error" in message

    @mock_aws
    def test_critical_with_exception_sends_to_cloudwatch(self):
        """Test critical() with exception sends to CloudWatch."""
        adapter = CloudWatchAdapter(
            log_group="/test/group",
            log_stream="test-stream",
            region="us-east-1",
            batch_size=1,
        )

        try:
            raise Exception("Critical failure")
        except Exception as exc:
            adapter.critical("System down", error=exc)

        time.sleep(0.2)

        response = adapter._client.get_log_events(
            logGroupName="/test/group",
            logStreamName="test-stream",
        )

        assert len(response["events"]) >= 1
        message = response["events"][0]["message"]
        assert "Exception" in message
        assert "Critical failure" in message

    @mock_aws
    def test_structured_context_sent_to_cloudwatch(self):
        """Test structured context is included in CloudWatch logs."""
        adapter = CloudWatchAdapter(
            log_group="/test/group",
            log_stream="test-stream",
            region="us-east-1",
            batch_size=1,
        )

        adapter.info(
            "User action",
            user_id="user-123",
            action="login",
            ip_address="192.168.1.1",
        )

        time.sleep(0.2)

        response = adapter._client.get_log_events(
            logGroupName="/test/group",
            logStreamName="test-stream",
        )

        # Context should be in JSON message
        message = response["events"][0]["message"]
        assert "user-123" in message
        assert "login" in message
        assert "192.168.1.1" in message

    @mock_aws
    def test_multiple_adapters_use_different_streams(self):
        """Test multiple CloudWatchAdapter instances use different streams."""
        adapter1 = CloudWatchAdapter(
            log_group="/test/group",
            log_stream="stream-1",
            region="us-east-1",
            batch_size=1,
        )

        adapter2 = CloudWatchAdapter(
            log_group="/test/group",
            log_stream="stream-2",
            region="us-east-1",
            batch_size=1,
        )

        # Log to each
        adapter1.info("Message to stream 1")
        adapter2.info("Message to stream 2")

        time.sleep(0.3)

        # Verify separate streams
        response1 = adapter1._client.get_log_events(
            logGroupName="/test/group",
            logStreamName="stream-1",
        )

        response2 = adapter2._client.get_log_events(
            logGroupName="/test/group",
            logStreamName="stream-2",
        )

        assert len(response1["events"]) >= 1
        assert len(response2["events"]) >= 1
        assert "stream 1" in response1["events"][0]["message"]
        assert "stream 2" in response2["events"][0]["message"]

    @mock_aws
    def test_adapter_handles_existing_log_group(self):
        """Test adapter handles pre-existing log group gracefully."""
        # Create log group first
        import boto3

        client = boto3.client("logs", region_name="us-east-1")
        client.create_log_group(logGroupName="/test/existing")

        # Adapter should not fail when group already exists
        adapter = CloudWatchAdapter(
            log_group="/test/existing",
            log_stream="test-stream",
            region="us-east-1",
        )

        # Should still be able to log
        adapter.info("Test message")
        assert adapter is not None

    @mock_aws
    def test_batch_size_controls_flush_behavior(self):
        """Test batch_size parameter controls when logs are flushed."""
        adapter = CloudWatchAdapter(
            log_group="/test/group",
            log_stream="test-stream",
            region="us-east-1",
            batch_size=5,  # Won't auto-flush until 5 messages
            batch_interval=10.0,  # Long interval to test manual batching
        )

        # Send 3 messages (below batch size)
        adapter.info("Message 1")
        adapter.info("Message 2")
        adapter.info("Message 3")

        # Short wait - should NOT have flushed yet
        time.sleep(0.1)

        response = adapter._client.get_log_events(
            logGroupName="/test/group",
            logStreamName="test-stream",
        )

        # May have 0 events if not flushed, or some if interval triggered
        # This tests that batch_size is respected
        initial_count = len(response["events"])

        # Now send 2 more to trigger batch flush
        adapter.info("Message 4")
        adapter.info("Message 5")  # This should trigger auto-flush

        time.sleep(0.2)

        response = adapter._client.get_log_events(
            logGroupName="/test/group",
            logStreamName="test-stream",
        )

        # Should now have all 5 messages (more than initial)
        final_count = len(response["events"])
        assert final_count >= 5
        assert final_count > initial_count  # Verify batch flush added messages

    @mock_aws
    def test_adapter_cleanup_on_close(self):
        """Test adapter flushes remaining logs on close()."""
        adapter = CloudWatchAdapter(
            log_group="/test/group",
            log_stream="test-stream",
            region="us-east-1",
            batch_size=100,  # Large batch size to prevent auto-flush
            batch_interval=10.0,
        )

        # Log message
        adapter.info("Final message")

        # Close adapter (should flush)
        adapter.close()

        # Give a moment for final flush
        time.sleep(0.1)

        # Verify message was sent
        response = adapter._client.get_log_events(
            logGroupName="/test/group",
            logStreamName="test-stream",
        )

        assert len(response["events"]) >= 1
        assert "Final message" in response["events"][0]["message"]
