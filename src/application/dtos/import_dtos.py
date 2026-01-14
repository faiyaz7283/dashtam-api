"""Import DTOs (Data Transfer Objects).

Response/result dataclasses for import command handlers.
These carry import operation results from handlers back to the presentation layer.

DTOs:
    - ImportResult: Result from ImportFromFile command

Reference:
    - docs/architecture/cqrs.md (DTOs section)
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class ImportResult:
    """Result of file import operation.

    Attributes:
        connection_id: Provider connection ID (created or existing).
        accounts_created: Number of new accounts created.
        accounts_updated: Number of existing accounts updated.
        transactions_created: Number of new transactions imported.
        transactions_skipped: Number of duplicate transactions skipped.
        message: Human-readable summary.
    """

    connection_id: UUID
    accounts_created: int
    accounts_updated: int
    transactions_created: int
    transactions_skipped: int
    message: str
