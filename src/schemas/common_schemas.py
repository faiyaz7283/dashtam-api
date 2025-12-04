"""Common schemas used across multiple API endpoints.

Provides reusable schema components for pagination, date ranges,
and standard response wrappers.

Reference:
    - docs/architecture/api-design-patterns.md
"""

from datetime import date

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Pagination query parameters.

    Attributes:
        page: Page number (1-indexed).
        page_size: Number of items per page.
    """

    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate SQL offset from page number.

        Returns:
            Offset for database query.
        """
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Return page size as limit.

        Returns:
            Limit for database query.
        """
        return self.page_size


class PaginatedMeta(BaseModel):
    """Pagination metadata for list responses.

    Attributes:
        page: Current page number.
        page_size: Items per page.
        total_count: Total items available.
        total_pages: Total number of pages.
    """

    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_count: int = Field(..., description="Total items available")
    total_pages: int = Field(..., description="Total number of pages")

    @classmethod
    def from_pagination(
        cls, page: int, page_size: int, total_count: int
    ) -> "PaginatedMeta":
        """Create pagination metadata from parameters.

        Args:
            page: Current page number.
            page_size: Items per page.
            total_count: Total items available.

        Returns:
            PaginatedMeta instance.
        """
        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            page=page,
            page_size=page_size,
            total_count=total_count,
            total_pages=total_pages,
        )


class DateRangeParams(BaseModel):
    """Date range query parameters.

    Attributes:
        start_date: Start of date range (inclusive).
        end_date: End of date range (inclusive).
    """

    start_date: date | None = Field(None, description="Start date (inclusive)")
    end_date: date | None = Field(None, description="End date (inclusive)")


class SyncResponse(BaseModel):
    """Response for sync operations.

    Attributes:
        created: Number of new records created.
        updated: Number of existing records updated.
        unchanged: Number of records unchanged.
        errors: Number of records that failed to sync.
        message: Human-readable summary.
    """

    created: int = Field(..., description="Records created")
    updated: int = Field(..., description="Records updated")
    unchanged: int = Field(..., description="Records unchanged")
    errors: int = Field(0, description="Records with sync errors")
    message: str = Field(..., description="Summary message")
