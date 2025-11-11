# Dashtam Documentation

Welcome to the Dashtam documentation. Dashtam is a secure, modern financial data aggregation platform built with clean architecture principles.

## Quick Links

- [Database Architecture](architecture/database-architecture.md) - Database infrastructure design and setup
- [Directory Structure](architecture/directory-structure.md) - Project organization and structure

## Project Overview

**Core Architecture**:
- **Hexagonal Architecture**: Domain at center, infrastructure at edges
- **CQRS Pattern**: Commands (write) separated from Queries (read)
- **Domain-Driven Design**: Pragmatic DDD with domain events for critical workflows
- **Protocol-Based**: Structural typing with Python `Protocol` (not ABC)

**Technology Stack**:
- **Backend**: FastAPI (async), Python 3.13+
- **Database**: PostgreSQL 17+ with async SQLAlchemy
- **Cache**: Redis 8.2+ (async)
- **Package Manager**: UV 0.8.22+ (NOT pip)
- **Containers**: Docker Compose v2, Traefik reverse proxy

## Getting Started

Documentation is being built incrementally as we implement each feature from the roadmap.