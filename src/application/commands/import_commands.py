"""Import commands for file-based data imports.

Commands for importing financial data from downloaded files (QFX, OFX, CSV).
Unlike sync commands which pull from live APIs, these import from local files.

Architecture:
    - Commands are immutable value objects representing user intent
    - Handlers execute the import and return results
    - Creates provider connection + accounts + transactions in one operation

Reference:
    - docs/architecture/cqrs-pattern.md
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ImportFromFile:
    """Command to import financial data from a file.

    Creates a provider connection (if needed) and imports accounts/transactions
    from the uploaded file. Used for file-based providers like Chase QFX.

    Attributes:
        user_id: User importing the file.
        provider_slug: Provider identifier (e.g., "chase_file").
        file_content: Raw file bytes.
        file_format: File format ("qfx", "ofx", "csv").
        file_name: Original filename (for logging).

    Example:
        >>> command = ImportFromFile(
        ...     user_id=user.id,
        ...     provider_slug="chase_file",
        ...     file_content=uploaded_file.read(),
        ...     file_format="qfx",
        ...     file_name="Chase_Activity.QFX",
        ... )
    """

    user_id: UUID
    provider_slug: str
    file_content: bytes
    file_format: str
    file_name: str
