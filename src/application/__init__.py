"""Application layer - Use cases and orchestration.

This layer contains the application's use cases following the CQRS pattern:
- Commands: Write operations that change state
- Queries: Read operations that fetch data
- Event Handlers: React to domain events

Structure:
- commands/: Command dataclasses and handlers (write operations)
- queries/: Query dataclasses and handlers (read operations)
- events/: Event handler implementations (domain event reactions)

The application layer orchestrates domain logic but contains no business rules.
"""
