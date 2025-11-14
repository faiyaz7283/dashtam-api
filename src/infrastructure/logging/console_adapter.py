"""Console logging adapter (development/testing).

Outputs structured logs to stdout using structlog.
- Development: human-readable console renderer with colors
- Testing/CI: JSON renderer for machine parsing

Implementation intentionally does NOT inherit from LoggerProtocol (PEP 544
structural subtyping). Any object with the same call signatures is compatible
with LoggerProtocol.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


class ConsoleAdapter:
    """Console logger for development and testing environments.

    Args:
        use_json (bool): JSON output when True (CI/testing), human-readable when False (dev).
    """

    def __init__(self, *, use_json: bool = False) -> None:
        """Initialize the console adapter.

        Args:
            use_json (bool): JSON output when True (CI/testing), human-readable when False (dev).
        """
        processors: list[structlog.types.Processor] = [
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
        ]

        if use_json:
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer(colors=True))

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
            cache_logger_on_first_use=True,
        )

        self._logger = structlog.get_logger()

    def debug(self, message: str, /, **context: Any) -> None:
        """Log a debug message.

        Args:
            message (str): Message text.
            **context: Structured key-value context.
        """
        self._logger.debug(message, **context)

    def info(self, message: str, /, **context: Any) -> None:
        """Log an info message.

        Args:
            message (str): Message text.
            **context: Structured key-value context.
        """
        self._logger.info(message, **context)

    def warning(self, message: str, /, **context: Any) -> None:
        """Log a warning message.

        Args:
            message (str): Message text.
            **context: Structured key-value context.
        """
        self._logger.warning(message, **context)

    def error(
        self, message: str, /, *, error: Exception | None = None, **context: Any
    ) -> None:
        """Log an error message with optional exception details.

        Args:
            message (str): Message text.
            error (Exception | None): Optional exception instance.
            **context: Structured key-value context.
        """
        if error is not None:
            context["error_type"] = type(error).__name__
            context["error_message"] = str(error)
        self._logger.error(message, **context)

    def critical(
        self, message: str, /, *, error: Exception | None = None, **context: Any
    ) -> None:
        """Log a critical message with optional exception details.

        Args:
            message (str): Message text.
            error (Exception | None): Optional exception instance.
            **context: Structured key-value context.
        """
        if error is not None:
            context["error_type"] = type(error).__name__
            context["error_message"] = str(error)
        self._logger.critical(message, **context)

    def bind(self, **context: Any) -> ConsoleAdapter:
        """Return new adapter with bound context.

        Args:
            **context: Context to bind to all subsequent logs.

        Returns:
            ConsoleAdapter: New adapter instance with bound context.
        """
        bound_adapter = ConsoleAdapter.__new__(ConsoleAdapter)
        bound_adapter._logger = self._logger.bind(**context)
        return bound_adapter

    def with_context(self, **context: Any) -> ConsoleAdapter:
        """Return new adapter with bound context (alias for bind).

        Args:
            **context: Context to bind to all subsequent logs.

        Returns:
            ConsoleAdapter: New adapter instance with bound context.
        """
        return self.bind(**context)
