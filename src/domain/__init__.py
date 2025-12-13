"""Domain layer - Pure business logic.

This layer contains the core business entities, value objects, protocols
(ports), and domain events. The domain layer has NO dependencies on any
framework or infrastructure - it is pure Python.

Structure:
- entities/: Domain entities (mutable, have identity)
- value_objects/: Value objects (immutable, no identity)
- protocols/: Domain protocols (repository interfaces, service interfaces)
- events/: Domain events (things that happened in the domain)

The domain layer defines WHAT the business does, not HOW it's implemented.
"""
