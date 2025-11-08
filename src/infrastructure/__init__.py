"""Infrastructure layer - Adapters and external integrations.

This layer contains implementations of domain protocols (ports):
- Database repositories
- External service clients (email, SMS)
- Financial provider integrations (Schwab, etc.)

Structure:
- persistence/: Database adapters (PostgreSQL repositories)
- external/: External service clients (email, cache, secrets)
- providers/: Financial provider integrations (OAuth, data sync)

The infrastructure layer depends on the domain layer (implements protocols)
but the domain layer does NOT depend on infrastructure.
"""
