"""Domain protocols (ports) package.

This package contains protocol definitions that the domain layer needs.
Infrastructure adapters implement these protocols without inheritance.
"""

from src.domain.protocols.audit_protocol import AuditProtocol
from src.domain.protocols.cache import CacheEntry, CacheProtocol

__all__ = [
    "AuditProtocol",
    "CacheEntry",
    "CacheProtocol",
]
