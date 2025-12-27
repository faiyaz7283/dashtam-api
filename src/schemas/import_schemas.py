"""Import schemas for file upload API.

Request and response schemas for file import endpoints.

Reference:
    - docs/architecture/api-design-patterns.md
"""

from uuid import UUID

from pydantic import BaseModel, Field

from src.application.commands.handlers.import_from_file_handler import ImportResult


class ImportResponse(BaseModel):
    """Response schema for file import.

    Attributes:
        connection_id: Provider connection ID.
        accounts_created: Number of new accounts created.
        accounts_updated: Number of existing accounts updated.
        transactions_created: Number of new transactions imported.
        transactions_skipped: Number of duplicate transactions skipped.
        message: Human-readable summary.
    """

    connection_id: UUID = Field(description="Provider connection ID")
    accounts_created: int = Field(description="Number of new accounts created")
    accounts_updated: int = Field(description="Number of existing accounts updated")
    transactions_created: int = Field(description="Number of new transactions imported")
    transactions_skipped: int = Field(
        description="Number of duplicate transactions skipped"
    )
    message: str = Field(description="Human-readable summary")

    @classmethod
    def from_result(cls, result: ImportResult) -> "ImportResponse":
        """Create response from ImportResult.

        Args:
            result: Handler result.

        Returns:
            ImportResponse instance.
        """
        return cls(
            connection_id=result.connection_id,
            accounts_created=result.accounts_created,
            accounts_updated=result.accounts_updated,
            transactions_created=result.transactions_created,
            transactions_skipped=result.transactions_skipped,
            message=result.message,
        )

    model_config = {
        "json_schema_extra": {
            "example": {
                "connection_id": "01234567-89ab-cdef-0123-456789abcdef",
                "accounts_created": 1,
                "accounts_updated": 0,
                "transactions_created": 25,
                "transactions_skipped": 0,
                "message": "Imported from Chase_Activity.QFX: 1 accounts created, 0 updated, 25 transactions imported, 0 skipped",
            }
        }
    }


class SupportedFormatsResponse(BaseModel):
    """Response schema for supported file formats.

    Attributes:
        formats: List of supported file format objects.
    """

    formats: list["FileFormatInfo"] = Field(description="List of supported formats")

    model_config = {
        "json_schema_extra": {
            "example": {
                "formats": [
                    {
                        "format": "qfx",
                        "name": "Quicken Financial Exchange",
                        "extensions": [".qfx"],
                        "provider_slugs": ["chase_file"],
                    },
                    {
                        "format": "ofx",
                        "name": "Open Financial Exchange",
                        "extensions": [".ofx"],
                        "provider_slugs": ["chase_file"],
                    },
                ]
            }
        }
    }


class FileFormatInfo(BaseModel):
    """Information about a supported file format.

    Attributes:
        format: Format identifier.
        name: Human-readable format name.
        extensions: File extensions for this format.
        provider_slugs: Providers that support this format.
    """

    format: str = Field(description="Format identifier")
    name: str = Field(description="Human-readable format name")
    extensions: list[str] = Field(description="File extensions")
    provider_slugs: list[str] = Field(description="Providers supporting this format")


# Update SupportedFormatsResponse to reference FileFormatInfo
SupportedFormatsResponse.model_rebuild()
