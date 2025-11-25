# Import Guidelines

This document defines the import conventions for the Dashtam codebase to ensure clean architecture boundaries and prevent circular imports.

---

## 1. Core Principle: Protocol-First Imports

All cross-layer dependencies should use **protocols** (interfaces), not concrete implementations.

```python
# ✅ CORRECT: Import protocol from domain
from src.domain.protocols.user_repository import UserRepository

# ❌ WRONG: Import concrete implementation
from src.infrastructure.persistence.repositories.user_repository import UserRepository
```

---

## 2. Layer-Specific Import Rules

### 2.1 Domain Layer (`src/domain/`)

**Imports**: NONE from other layers (domain is the core, depends on nothing)

**Allowed imports**:

- Standard library only
- Other domain modules (`domain.entities`, `domain.events`, `domain.protocols`)

```python
# ✅ CORRECT: Domain imports
from uuid import UUID
from datetime import datetime
from typing import Protocol
from src.domain.entities.user import User
from src.domain.events.auth_events import UserRegistrationSucceeded

# ❌ WRONG: Domain should NEVER import from other layers
from src.application.commands.register_user import RegisterUser  # NO!
from src.infrastructure.persistence.models.user import UserModel  # NO!
```

### 2.2 Application Layer (`src/application/`)

**Imports**: Domain layer ONLY (protocols, entities, events, errors)

**Allowed imports**:

- Standard library
- `src.domain.*` (protocols, entities, events, errors)
- Other application modules

```python
# ✅ CORRECT: Application imports
from src.domain.protocols.user_repository import UserRepository
from src.domain.protocols.password_hashing_protocol import PasswordHashingProtocol
from src.domain.entities.user import User
from src.domain.events.auth_events import UserRegistrationSucceeded
from src.domain.errors.authentication_error import AuthenticationError

# ❌ WRONG: Application should NEVER import from infrastructure
from src.infrastructure.persistence.repositories.user_repository import UserRepository  # NO!
from src.infrastructure.persistence.models.user import UserModel  # NO!
from src.infrastructure.auth.bcrypt_password_service import BcryptPasswordService  # NO!
```

### 2.3 Infrastructure Layer (`src/infrastructure/`)

**Imports**: Domain layer (implements protocols), external libraries

**Allowed imports**:

- Standard library
- `src.domain.protocols.*` (to implement)
- `src.domain.entities.*` (to convert to/from models)
- External libraries (SQLAlchemy, Redis, etc.)
- Other infrastructure modules

```python
# ✅ CORRECT: Infrastructure imports
from src.domain.protocols.user_repository import UserRepository  # Protocol to implement
from src.domain.entities.user import User  # Entity to convert
from sqlalchemy.ext.asyncio import AsyncSession  # External library
from src.infrastructure.persistence.models.user import UserModel  # Internal model

# ❌ WRONG: Infrastructure should NEVER import from application
from src.application.commands.handlers.register_user_handler import RegisterUserHandler  # NO!
```

### 2.4 Presentation Layer (`src/presentation/`)

**Imports**: Application layer (commands, queries), domain layer (entities for DTOs)

**Allowed imports**:

- Standard library
- `src.application.*` (commands, queries, handlers)
- `src.domain.entities.*` (for response schemas)
- `src.domain.errors.*` (for error handling)
- FastAPI dependencies (`src.core.container`)
- Pydantic schemas

```python
# ✅ CORRECT: Presentation imports
from src.application.commands.register_user import RegisterUser
from src.application.commands.handlers.register_user_handler import RegisterUserHandler
from src.domain.entities.user import User
from src.core.container import get_register_user_handler

# ❌ WRONG: Presentation should NEVER import infrastructure directly
from src.infrastructure.persistence.repositories.user_repository import UserRepository  # NO!
```

### 2.5 Container (`src/core/container.py`)

**Special case**: Container is the "Composition Root" and MUST import from infrastructure.

**Allowed imports**:

- All layers (this is where wiring happens)
- Infrastructure implementations
- Domain protocols

```python
# ✅ CORRECT: Container imports (composition root)
from src.domain.protocols.user_repository import UserRepository  # Protocol for type hint
from src.infrastructure.persistence.repositories.user_repository import UserRepository as UserRepositoryImpl  # Implementation
```

---

## 3. Re-export Rules

### 3.1 No Cross-Boundary Re-exports

Each `__init__.py` should only re-export items from its own module:

```python
# src/domain/protocols/__init__.py
# ✅ CORRECT: Re-export protocols only
from src.domain.protocols.user_repository import UserRepository
from src.domain.protocols.cache_protocol import CacheProtocol

# ❌ WRONG: Never re-export from other modules
from src.domain.events.auth_events import UserRegistrationSucceeded  # NO!
```

### 3.2 Module Boundaries

| Module | Re-exports |
| ------ | ---------- |
| `domain/protocols/` | Protocols only |
| `domain/entities/` | Entities only |
| `domain/events/` | Events only |
| `domain/errors/` | Errors only |
| `application/commands/` | Commands only |
| `application/queries/` | Queries only |

---

## 4. Protocol Naming Conventions

### 4.1 Repository Protocols

**Pattern**: `<Entity>Repository`

```python
# ✅ CORRECT
class UserRepository(Protocol): ...
class RefreshTokenRepository(Protocol): ...

# ❌ WRONG: Don't use I prefix (not Pythonic)
class IUserRepository(Protocol): ...  # NO!
class UserRepositoryInterface(Protocol): ...  # NO!
```

### 4.2 Service Protocols

**Pattern**: `<Feature>Protocol` or `<Feature>Service`

```python
# ✅ CORRECT
class PasswordHashingProtocol(Protocol): ...
class TokenGenerationProtocol(Protocol): ...
class CacheProtocol(Protocol): ...
```

---

## 5. Import Organization

### 5.1 Import Order

1. Standard library
2. Third-party packages
3. Domain layer (`src.domain.*`)
4. Application layer (`src.application.*`)
5. Infrastructure layer (`src.infrastructure.*`) - only in allowed contexts
6. Local imports

```python
# Example: Application layer handler
from dataclasses import dataclass  # 1. stdlib
from uuid import UUID

from result import Result, Ok, Err  # 2. third-party

from src.domain.protocols.user_repository import UserRepository  # 3. domain
from src.domain.entities.user import User
from src.domain.events.auth_events import UserRegistrationSucceeded

from src.application.commands.register_user import RegisterUser  # 4. application (local)
```

### 5.2 Absolute vs Relative Imports

**Always use absolute imports** from `src`:

```python
# ✅ CORRECT: Absolute imports
from src.domain.protocols.user_repository import UserRepository

# ❌ WRONG: Relative imports (harder to refactor)
from ..protocols.user_repository import UserRepository
```

---

## 6. Common Violations to Avoid

### 6.1 Application Importing Infrastructure Models

```python
# ❌ WRONG: Handler constructing infrastructure model
from src.infrastructure.persistence.models.user import UserModel

class RegisterUserHandler:
    async def handle(self, cmd: RegisterUser) -> Result:
        # BAD: Handler knows about database model
        user_model = UserModel(email=cmd.email, ...)
        await self.user_repo.save(user_model)
```

**Fix**: Handler should work with domain entities, repository handles conversion.

```python
# ✅ CORRECT: Handler uses domain entity
from src.domain.entities.user import User

class RegisterUserHandler:
    async def handle(self, cmd: RegisterUser) -> Result:
        # GOOD: Handler uses domain entity
        user = User(email=cmd.email, ...)
        await self.user_repo.save(user)  # Repo converts to model internally
```

### 6.2 Domain Importing External Libraries

```python
# ❌ WRONG: Domain depends on SQLAlchemy
from sqlalchemy import Column, String  # NO!

class User:
    id = Column(String, primary_key=True)  # NO!
```

**Fix**: Domain entities are pure Python dataclasses.

```python
# ✅ CORRECT: Domain entity is pure Python
@dataclass
class User:
    id: UUID
    email: str
```

---

## 7. Verification Commands

### Check for Infrastructure Imports in Application Layer

```bash
grep -r "from src.infrastructure" src/application/
# Should return NOTHING
```

### Check for Application Imports in Domain Layer

```bash
grep -r "from src.application" src/domain/
# Should return NOTHING
```

### Verify Import Test

```bash
docker compose exec app uv run python -c "from src.application.commands.handlers.register_user_handler import RegisterUserHandler; print('✅')"
```

---

**Created**: 2025-11-25 | **Last Updated**: 2025-11-25
