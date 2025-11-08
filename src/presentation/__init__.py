"""Presentation layer - API endpoints and HTTP concerns.

This layer contains FastAPI routers and endpoint definitions. The presentation
layer is thin - it dispatches commands/queries to the application layer and
translates results to HTTP responses.

Structure:
- api/v1/: API version 1 endpoints (RESTful resources)

The presentation layer depends on the application layer (dispatches
commands/queries) but contains NO business logic.
"""
