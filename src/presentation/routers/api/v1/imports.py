"""Imports resource handlers.

Handler functions for file-based data imports.
Routes are registered via ROUTE_REGISTRY in routes/registry.py.

Handlers:
    import_from_file      - Import data from uploaded file
    list_supported_formats - List supported file formats

Reference:
    - docs/architecture/api-design-patterns.md
    - docs/guides/chase-file-import.md
"""

from typing import Annotated

from fastapi import Depends, File, Request, UploadFile, status
from fastapi.responses import JSONResponse

from src.application.commands.handlers.import_from_file_handler import (
    ImportFromFileHandler,
)
from src.application.commands.import_commands import ImportFromFile
from src.application.errors import ApplicationError, ApplicationErrorCode
from src.core.container import get_import_from_file_handler
from src.core.result import Failure
from src.presentation.routers.api.middleware.auth_dependencies import AuthenticatedUser
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id
from src.presentation.routers.api.v1.errors import ErrorResponseBuilder
from src.schemas.import_schemas import (
    FileFormatInfo,
    ImportResponse,
    SupportedFormatsResponse,
)


# =============================================================================
# Supported File Formats
# =============================================================================

SUPPORTED_FORMATS: list[FileFormatInfo] = [
    FileFormatInfo(
        format="qfx",
        name="Quicken Financial Exchange",
        extensions=[".qfx"],
        provider_slugs=["chase_file"],
    ),
    FileFormatInfo(
        format="ofx",
        name="Open Financial Exchange",
        extensions=[".ofx"],
        provider_slugs=["chase_file"],
    ),
]

# Map file extensions to format and provider
EXTENSION_MAP: dict[str, tuple[str, str]] = {
    ".qfx": ("qfx", "chase_file"),
    ".ofx": ("ofx", "chase_file"),
}


# =============================================================================
# Error Mapping
# =============================================================================


def _map_import_error(error: str) -> ApplicationError:
    """Map handler string error to ApplicationError.

    Args:
        error: Error string from handler.

    Returns:
        ApplicationError with appropriate code and message.
    """
    error_lower = error.lower()

    if "invalid" in error_lower or "unparseable" in error_lower:
        return ApplicationError(
            code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
            message=error,
        )
    if "no account" in error_lower:
        return ApplicationError(
            code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
            message=error,
        )
    if "not found" in error_lower:
        return ApplicationError(
            code=ApplicationErrorCode.NOT_FOUND,
            message=error,
        )

    return ApplicationError(
        code=ApplicationErrorCode.COMMAND_EXECUTION_FAILED,
        message=error,
    )


# =============================================================================
# Handlers
# =============================================================================


async def import_from_file(
    request: Request,
    current_user: AuthenticatedUser,
    file: Annotated[UploadFile, File(description="Financial data file (QFX, OFX)")],
    handler: ImportFromFileHandler = Depends(get_import_from_file_handler),
) -> ImportResponse | JSONResponse:
    """Import financial data from an uploaded file.

    POST /api/v1/imports → 201 Created

    Supported formats:
    - QFX (Quicken Financial Exchange) - Chase Bank
    - OFX (Open Financial Exchange) - Chase Bank

    The file format and provider are auto-detected from the file extension.

    Args:
        request: FastAPI request object.
        current_user: Authenticated user (from JWT).
        file: Uploaded file.
        handler: Import handler (injected).

    Returns:
        ImportResponse with import counts.
        JSONResponse with RFC 7807 error on failure.
    """
    # Get filename and extension
    filename = file.filename or "unknown"
    extension = ""
    if "." in filename:
        extension = "." + filename.rsplit(".", 1)[-1].lower()

    # Auto-detect format and provider from extension
    if extension not in EXTENSION_MAP:
        # 415 Unsupported Media Type - use JSONResponse directly
        # since ErrorResponseBuilder maps status from error code
        return JSONResponse(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            content={
                "type": f"/errors/{ApplicationErrorCode.COMMAND_VALIDATION_FAILED.value}",
                "title": "Unsupported Media Type",
                "status": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "detail": f"Unsupported file format: {extension}. Supported: {', '.join(EXTENSION_MAP.keys())}",
                "instance": str(request.url.path),
                "trace_id": get_trace_id() or "",
            },
        )

    file_format, provider_slug = EXTENSION_MAP[extension]

    # Read file content
    file_content = await file.read()

    if not file_content:
        return ErrorResponseBuilder.from_application_error(
            error=ApplicationError(
                code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
                message="Empty file",
            ),
            request=request,
            trace_id=get_trace_id() or "",
        )

    # Create and execute command
    command = ImportFromFile(
        user_id=current_user.user_id,
        provider_slug=provider_slug,
        file_content=file_content,
        file_format=file_format,
        file_name=filename,
    )

    result = await handler.handle(command)

    if isinstance(result, Failure):
        app_error = _map_import_error(result.error)
        return ErrorResponseBuilder.from_application_error(
            error=app_error,
            request=request,
            trace_id=get_trace_id() or "",
        )

    return ImportResponse.from_result(result.value)


async def list_supported_formats() -> SupportedFormatsResponse:
    """List supported file formats for import.

    GET /api/v1/imports/formats → 200 OK

    Returns:
        SupportedFormatsResponse with list of supported formats.
    """
    return SupportedFormatsResponse(formats=SUPPORTED_FORMATS)
