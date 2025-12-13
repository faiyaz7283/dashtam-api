"""LoggerProtocol definition for structured logging.

This protocol standardizes structured logging across the codebase while
remaining backend-agnostic. Implementations MUST ensure logs are structured
(key-value context) and safe (no secrets).

Log Levels (standard 5-level hierarchy):
    - DEBUG: Detailed diagnostic info (dev only)
    - INFO: Normal operational events
    - WARNING: Degraded service, approaching limits
    - ERROR: Operation failed, system continues
    - CRITICAL: System-wide failure, immediate attention

Context Binding:
    Use bind() or with_context() to create request-scoped loggers with
    permanent context (trace_id, user_id) automatically included in all logs.

Security:
    - NEVER log passwords, tokens, API keys, SSNs, credit card numbers
    - Sanitize user input (truncate, strip control characters)

Usage:
    from src.core.container import get_logger
    from src.domain.protocols.logger_protocol import LoggerProtocol

    # Basic logging
    logger: LoggerProtocol = get_logger()
    logger.info("User registered", user_id=str(user_id), trace_id=trace_id)

    # Request-scoped logging with bind()
    request_logger = logger.bind(trace_id=trace_id, user_id=str(user_id))
    request_logger.info("Request started")  # trace_id, user_id auto-included
"""

from __future__ import annotations

from typing import Any, Protocol


class LoggerProtocol(Protocol):
    """Protocol for structured logging adapters.

    All logging calls MUST be structured: message + key-value context.
    Supports 5 standard log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    and context binding for request-scoped logging.

    Implementations may enrich logs with timestamp, level, and trace correlation.
    """

    def debug(self, message: str, /, **context: Any) -> None:
        """Log a debug-level message.

        Args:
            message: Human-readable message (avoid f-strings; use context).
            **context: Structured key-value context fields.
        """
        ...

    def info(self, message: str, /, **context: Any) -> None:
        """Log an info-level message.

        Args:
            message: Human-readable message (avoid f-strings; use context).
            **context: Structured key-value context fields.
        """
        ...

    def warning(self, message: str, /, **context: Any) -> None:
        """Log a warning-level message.

        Args:
            message: Human-readable message (avoid f-strings; use context).
            **context: Structured key-value context fields.
        """
        ...

    def error(
        self, message: str, /, *, error: Exception | None = None, **context: Any
    ) -> None:
        """Log an error-level message with optional exception details.

        Args:
            message: Human-readable message (avoid f-strings; use context).
            error: Optional exception instance; implementation may include
                error_type and error_message fields.
            **context: Structured key-value context fields.
        """
        ...

    def critical(
        self, message: str, /, *, error: Exception | None = None, **context: Any
    ) -> None:
        """Log a critical-level message for catastrophic failures.

        Use CRITICAL for system-wide failures requiring immediate attention:
        - Complete service outages
        - Data corruption detected
        - Security breaches
        - Unrecoverable errors affecting all users

        Args:
            message: Human-readable message (avoid f-strings; use context).
            error: Optional exception instance; implementation may include
                error_type and error_message fields.
            **context: Structured key-value context fields.

        Note:
            CRITICAL logs typically trigger immediate alerts (PagerDuty, SMS).
            Use sparingly - only for events requiring immediate human intervention.
        """
        ...

    def bind(self, **context: Any) -> "LoggerProtocol":
        """Return new logger with permanently bound context.

        Bound context is automatically included in all subsequent log calls.
        Original logger instance remains unchanged (immutable pattern).

        Args:
            **context: Context to bind to all future logs.

        Returns:
            New logger instance with bound context.

        Example:
            # Bind request-scoped context once
            request_logger = logger.bind(
                trace_id=trace_id,
                user_id=str(user_id),
                request_path=request.url.path
            )

            # All logs automatically include bound context
            request_logger.info("Request started")
            request_logger.info("Validation passed")
            request_logger.error("Processing failed")
            # trace_id, user_id, request_path included automatically

        Use Cases:
            - Request-scoped logging (bind trace_id, user_id)
            - Handler-scoped logging (bind handler_name, operation)
            - Background job logging (bind job_id, batch_id)
        """
        ...

    def with_context(self, **context: Any) -> "LoggerProtocol":
        """Alias for bind() - return logger with bound context.

        Functionally identical to bind(), provided for semantic clarity
        in certain contexts.

        Args:
            **context: Context to bind to all future logs.

        Returns:
            New logger instance with bound context.

        Example:
            scoped_logger = logger.with_context(
                operation="batch_import",
                batch_id="abc-123"
            )
        """
        ...
