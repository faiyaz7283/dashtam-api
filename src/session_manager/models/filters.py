"""Session query filters.

This module defines SessionFilters dataclass for filtering session queries.
This is NOT a database model - it's a structured way to pass filter options
to storage implementations.

Think of it as typed query parameters.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SessionFilters:
    """Filter options for listing sessions.

    This is a dataclass (NOT a database model) used to pass filter criteria
    to storage layer when querying sessions.

    Usage:
        ```python
        # In API endpoint
        filters = SessionFilters(
            active_only=True,
            device_type="mobile",
            created_after=datetime(2024, 1, 1)
        )

        # Pass to storage
        sessions = await storage.list_sessions(user_id="123", filters=filters)
        ```

    Attributes:
        active_only: Only return non-revoked, non-expired sessions
        device_type: Filter by device (e.g., "mobile", "desktop", "tablet")
        ip_address: Filter by IP address
        location: Filter by location (e.g., "US", "New York")
        created_after: Filter by creation date (inclusive)
        created_before: Filter by creation date (inclusive)
        is_trusted: Filter by trusted device status
    """

    active_only: bool = True
    device_type: Optional[str] = None
    ip_address: Optional[str] = None
    location: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    is_trusted: Optional[bool] = None
