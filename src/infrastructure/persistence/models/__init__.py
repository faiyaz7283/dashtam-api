"""Database models for persistence layer.

This package contains SQLAlchemy/SQLModel database models that map to database
tables. These are infrastructure concerns and should not be imported by the
domain layer.

Models Organization:
    - audit.py: Audit trail model (immutable)
    - (future models here)

Note:
    Domain entities (dataclasses) live in src/domain/entities/
    Database models (SQLModel) live here in src/infrastructure/persistence/models/
    They are separate and mapped via repository layer.
"""
