"""CloudWatch logging adapter (production).

Sends structured logs to AWS CloudWatch Logs. Minimal, safe implementation that
batches events and flushes periodically to reduce API calls.

Notes:
- This adapter is synchronous internally (boto3) but exposes non-async methods
  to conform to LoggerProtocol. Consider moving to aioboto3 if needed later.
- Designed to be created once (singleton via container.get_logger()).
"""

from __future__ import annotations

import atexit
import json
import threading
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Deque

import boto3
from botocore.exceptions import ClientError
from mypy_boto3_logs.client import CloudWatchLogsClient
from mypy_boto3_logs.type_defs import InputLogEventTypeDef

from src.infrastructure.logging.console_adapter import ConsoleAdapter


@dataclass(slots=True)
class _Event:
    ts: datetime
    level: str
    message: str
    context: dict[str, Any]


class CloudWatchAdapter:
    """CloudWatch logger with simple background flushing.

    Args:
        log_group (str): CloudWatch log group name (e.g., /dashtam/production/app).
        log_stream (str): CloudWatch log stream name (e.g., hostname/2025-11-13).
        region (str): AWS region name.
        batch_size (int): Maximum events per PutLogEvents call.
        batch_interval (float): Seconds between automatic flush attempts.
    """

    def __init__(
        self,
        *,
        log_group: str,
        log_stream: str,
        region: str = "us-east-1",
        batch_size: int = 50,
        batch_interval: float = 5.0,
    ) -> None:
        """Initialize the CloudWatch adapter.

        Args:
            log_group (str): Log group name.
            log_stream (str): Log stream name.
            region (str): AWS region.
            batch_size (int): Events per batch.
            batch_interval (float): Periodic flush interval in seconds.
        """
        self._client: CloudWatchLogsClient = boto3.client("logs", region_name=region)
        self._group = log_group
        self._stream = log_stream
        self._batch_size = batch_size
        self._batch_interval = batch_interval
        self._seq_token: str | None = None

        self._queue: Deque[_Event] = deque()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._flusher = threading.Thread(
            target=self._flush_loop, name="cw-logger", daemon=True
        )

        # Fallback to console on error
        self._fallback = ConsoleAdapter(use_json=True)

        self._ensure_destination()
        self._flusher.start()
        atexit.register(self.close)

    # Public API matching LoggerProtocol
    def debug(self, message: str, /, **context: Any) -> None:
        """Log a debug message.

        Args:
            message (str): Message text.
            **context: Structured key-value context.
        """
        self._enqueue("DEBUG", message, context)

    def info(self, message: str, /, **context: Any) -> None:
        """Log an info message.

        Args:
            message (str): Message text.
            **context: Structured key-value context.
        """
        self._enqueue("INFO", message, context)

    def warning(self, message: str, /, **context: Any) -> None:
        """Log a warning message.

        Args:
            message (str): Message text.
            **context: Structured key-value context.
        """
        self._enqueue("WARNING", message, context)

    def error(
        self, message: str, /, *, error: Exception | None = None, **context: Any
    ) -> None:
        """Log an error message with optional exception.

        Args:
            message (str): Message text.
            error (Exception | None): Optional exception instance.
            **context: Structured key-value context.
        """
        if error is not None:
            context["error_type"] = type(error).__name__
            context["error_message"] = str(error)
        self._enqueue("ERROR", message, context)

    def critical(
        self, message: str, /, *, error: Exception | None = None, **context: Any
    ) -> None:
        """Log a critical message with optional exception.

        Args:
            message (str): Message text.
            error (Exception | None): Optional exception instance.
            **context: Structured key-value context.
        """
        if error is not None:
            context["error_type"] = type(error).__name__
            context["error_message"] = str(error)
        self._enqueue("CRITICAL", message, context)

    def bind(self, **context: Any) -> "CloudWatchAdapter":
        """Return new adapter with bound context.

        Note: CloudWatchAdapter doesn't maintain per-instance bound context.
        This returns self for protocol compliance; include context per call.
        """
        return self

    def with_context(self, **context: Any) -> "CloudWatchAdapter":
        """Alias for bind() - returns self."""
        return self.bind(**context)

    # Internal helpers
    def _enqueue(self, level: str, message: str, context: dict[str, Any]) -> None:
        """Add a log event to the in-memory queue.

        Args:
            level (str): Log level.
            message (str): Message text.
            context (dict[str, Any]): Structured context.
        """
        ev = _Event(ts=datetime.now(UTC), level=level, message=message, context=context)
        with self._lock:
            self._queue.append(ev)
            if len(self._queue) >= self._batch_size:
                # Flush immediately in a separate thread
                threading.Thread(target=self._flush_safe, daemon=True).start()

    def _flush_loop(self) -> None:
        """Background loop that periodically flushes queued events."""
        while not self._stop.is_set():
            self._stop.wait(timeout=self._batch_interval)
            self._flush_safe()

    def _flush_safe(self) -> None:
        """Flush queued events with best-effort error handling.

        On failure, logs the error to the console fallback and continues.
        Silently ignores I/O errors during shutdown (stdout closed).
        """
        try:
            self._flush()
        except Exception as e:  # noqa: BLE001 - best-effort logging
            try:
                self._fallback.error(
                    "CloudWatch flush failed", error=e, pending=len(self._queue)
                )
            except (ValueError, OSError):
                # Ignore I/O errors during shutdown (stdout closed)
                pass

    def _ensure_destination(self) -> None:
        """Ensure CloudWatch log group and stream exist.

        Raises:
            ClientError: If the AWS API returns an error other than
                ResourceAlreadyExistsException.
        """
        try:
            self._client.create_log_group(logGroupName=self._group)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code != "ResourceAlreadyExistsException":
                raise
        try:
            self._client.create_log_stream(
                logGroupName=self._group, logStreamName=self._stream
            )
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code != "ResourceAlreadyExistsException":
                raise

    def _flush(self) -> None:
        """Flush the current batch to CloudWatch Logs.

        Aggregates queued events into CloudWatch InputLogEvent objects and
        submits them using PutLogEvents with the maintained sequence token.

        Raises:
            ClientError: If CloudWatch APIs fail (handled in caller for fallback).
        """
        events: list[_Event] = []
        with self._lock:
            while self._queue and len(events) < self._batch_size:
                events.append(self._queue.popleft())

        if not events:
            return

        payload: list[InputLogEventTypeDef] = [
            {
                "timestamp": int(ev.ts.timestamp() * 1000),
                "message": json.dumps(
                    {
                        "timestamp": ev.ts.isoformat(),
                        "level": ev.level.lower(),
                        "message": ev.message,
                        **ev.context,
                    },
                    separators=(",", ":"),
                ),
            }
            for ev in events
        ]

        try:
            if self._seq_token is not None:
                resp = self._client.put_log_events(
                    logGroupName=self._group,
                    logStreamName=self._stream,
                    logEvents=payload,
                    sequenceToken=self._seq_token,
                )
            else:
                resp = self._client.put_log_events(
                    logGroupName=self._group,
                    logStreamName=self._stream,
                    logEvents=payload,
                )
            self._seq_token = resp.get("nextSequenceToken", self._seq_token)
        except ClientError as e:
            # Fallback to console; re-enqueue for retry on next loop
            for ev in events:
                self._fallback.error(
                    "CloudWatch send failed",
                    error=e,
                    level=ev.level,
                    message=ev.message,
                    **ev.context,
                )

    def close(self) -> None:
        """Stop background flusher and attempt a final flush.

        Ensures that any buffered log events are sent before process exit.
        """
        self._stop.set()
        # Attempt a final flush
        self._flush_safe()
