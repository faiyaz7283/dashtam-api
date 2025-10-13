# Mermaid Diagram Guidelines

**CRITICAL RULE**: All diagrams in Dashtam documentation MUST use Mermaid syntax. This ensures consistency, version control compatibility, and seamless MkDocs integration.

---

## Table of Contents

- [Why Mermaid?](#why-mermaid)
- [Required Diagram Types](#required-diagram-types)
- [Best Practices](#best-practices)
- [Common Patterns](#common-patterns)
- [Syntax Reference](#syntax-reference)
- [Troubleshooting](#troubleshooting)
- [Quick Reference](#quick-reference)

---

## Why Mermaid?

**Advantages:**

- ✅ **Text-based** - Works with Git, easy to review in PRs
- ✅ **Version controlled** - Track changes over time
- ✅ **MkDocs compatible** - Renders automatically with mkdocs-mermaid2-plugin
- ✅ **No external tools** - No need for separate diagram applications
- ✅ **Consistent style** - Unified look across all documentation
- ✅ **Easy to update** - Edit text, not images

**Prohibited:**

- ❌ **Image files** (PNG, JPG, SVG uploads) - Not version-control friendly
- ❌ **External diagram tools** (draw.io, Lucidchart exports) - Creates maintenance burden
- ❌ **ASCII art** - Limited and hard to maintain

---

## Required Diagram Types

### 1. Directory Tree Structures → Use Mindmap

**When to use:**

- Showing project directory structure
- Displaying file organization
- Illustrating component hierarchy

**Syntax:**

```mermaid
mindmap
  root((Project))
    docs
      architecture
        overview.md
        jwt-authentication.md
      guides
        git-workflow.md
        docker-setup.md
      templates
        README.md
        general-template.md
    src
      api
        auth.py
        providers.py
      models
        user.py
        token.py
      services
        auth_service.py
```

**Example Output:**

```mermaid
mindmap
  root((Dashtam))
    docs/
      development/
      research/
      templates/
    src/
      api/
      models/
      services/
```

### 2. Directional Flows → Use Flowchart

**When to use:**

- Process flows
- Data flow diagrams
- Decision trees
- State machines

**Syntax:**

```mermaid
flowchart TD
    A[Start] --> B{Is authenticated?}
    B -->|Yes| C[Access granted]
    B -->|No| D[Redirect to login]
    D --> E[User logs in]
    E --> F{Valid credentials?}
    F -->|Yes| C
    F -->|No| G[Show error]
    G --> D
```

**Shapes Available:**

- `A[Rectangle]` - Process step
- `B{Diamond}` - Decision point
- `C([Rounded])` - Start/End
- `D[(Database)]` - Database
- `E((Circle))` - Connection point

**Directions:**

- `TD` or `TB` - Top to bottom (recommended for most flows)
- `LR` - Left to right (good for wide diagrams)
- `RL` - Right to left
- `BT` - Bottom to top

### 3. Relationships & Tables → Use ER Diagram

**When to use:**

- Database schema
- Entity relationships
- Data models
- Table structures

**Syntax:**

```mermaid
erDiagram
    USER ||--o{ TOKEN : has
    USER ||--o{ PROVIDER_CONNECTION : owns
    PROVIDER_CONNECTION ||--|| PROVIDER : references
    TOKEN ||--|| USER : belongs_to
    
    USER {
        uuid id PK
        string email UK
        string password_hash
        boolean is_verified
        timestamp created_at
    }
    
    TOKEN {
        uuid id PK
        uuid user_id FK
        string token_hash
        string token_type
        timestamp expires_at
    }
    
    PROVIDER_CONNECTION {
        uuid id PK
        uuid user_id FK
        uuid provider_id FK
        string encrypted_tokens
        timestamp connected_at
    }
```

**Relationship Types:**

- `||--||` - One to one
- `||--o{` - One to many
- `}o--o{` - Many to many
- `||--o|` - One to zero or one

### 4. Sequence Diagrams → Use Sequence

**When to use:**

- API request/response flows
- Authentication sequences
- Service interactions
- Time-based processes

**Syntax:**

```mermaid
sequenceDiagram
    participant U as User
    participant A as API
    participant D as Database
    participant E as EmailService
    
    U->>A: POST /auth/register
    A->>D: Check if email exists
    D-->>A: Email available
    A->>D: Create user
    D-->>A: User created
    A->>E: Send verification email
    E-->>A: Email queued
    A-->>U: 201 Created + token
    
    Note over U,E: User receives email
    U->>A: GET /auth/verify?token=xxx
    A->>D: Validate token
    D-->>A: Token valid
    A->>D: Mark user verified
    D-->>A: Updated
    A-->>U: 200 OK
```

### 5. State Diagrams → Use State Diagram

**When to use:**

- Object lifecycle
- Status transitions
- Workflow states

**Syntax:**

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> Active: Approve
    Draft --> Archived: Reject
    Active --> Archived: Deprecate
    Active --> Superseded: Replace
    Superseded --> Archived: Archive old
    Archived --> [*]
    
    note right of Active
        Primary state for
        current documentation
    end note
```

### 6. Gantt Charts → Use Gantt

**When to use:**

- Project timelines
- Implementation phases
- Sprint planning (avoid rigid day-based schedules per WARP.md)

**Syntax:**

```mermaid
gantt
    title Implementation Phases
    dateFormat YYYY-MM-DD
    
    section Phase 1
    Setup environment    :done, p1, 2025-10-01, 2d
    Configure CI/CD      :done, p2, after p1, 3d
    
    section Phase 2
    Core services        :active, p3, 2025-10-06, 5d
    API endpoints        :p4, after p3, 4d
    
    section Phase 3
    Testing              :p5, after p4, 3d
    Documentation        :p6, after p5, 2d
```

### 7. Class Diagrams → Use Class Diagram

**When to use:**

- OOP structure
- Class relationships
- Service architecture

**Syntax:**

```mermaid
classDiagram
    class User {
        +uuid id
        +string email
        +string password_hash
        +boolean is_verified
        +create()
        +verify_email()
        +reset_password()
    }
    
    class Token {
        +uuid id
        +uuid user_id
        +string token_hash
        +datetime expires_at
        +validate()
        +revoke()
    }
    
    class AuthService {
        +register(email, password)
        +login(email, password)
        +refresh_token(refresh_token)
        +logout(user_id)
    }
    
    User "1" --> "0..*" Token : has
    AuthService ..> User : uses
    AuthService ..> Token : manages
```

---

## Best Practices

### General Guidelines

1. **Always specify diagram type** - Start with diagram type declaration
2. **Use descriptive labels** - Clear, concise text
3. **Keep it simple** - Don't overcomplicate diagrams
4. **Consistent naming** - Use same naming convention across diagrams
5. **Add notes** - Explain complex parts

### Styling Guidelines

```mermaid
flowchart TD
    A[Normal Process] --> B{Decision Point}
    B -->|Yes| C[Success Path]
    B -->|No| D[Error Path]
    
    style C fill:#90EE90
    style D fill:#FFB6C1
    style B fill:#FFD700
```

**Color Coding:**

- Green (`#90EE90`) - Success paths
- Red/Pink (`#FFB6C1`) - Error paths
- Yellow (`#FFD700`) - Decision points
- Blue (`#87CEEB`) - External services

### Responsive Design

- **Keep width reasonable** - Aim for diagrams that fit in 800-1200px width
- **Use vertical layouts** - Top-to-bottom flows work better on mobile
- **Break complex diagrams** - Split into multiple smaller diagrams

---

## Common Patterns

### Pattern 1: Authentication Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API
    participant D as Database
    
    C->>A: POST /auth/login
    A->>D: Validate credentials
    D-->>A: User found
    A->>A: Generate JWT
    A-->>C: 200 OK + tokens
```

### Pattern 2: Directory Structure

```mermaid
mindmap
  root((Project Root))
    src
      api
      models
      services
    tests
      unit
      integration
    docs
      development
      templates
```

### Pattern 3: Decision Flow

```mermaid
flowchart TD
    Start([Start]) --> Check{Authenticated?}
    Check -->|Yes| Access[Grant Access]
    Check -->|No| Login[Redirect to Login]
    Access --> End([End])
    Login --> End
```

---

## Syntax Reference

### Node Shapes

| Shape | Syntax | Use Case |
|-------|--------|----------|
| Rectangle | `A[Text]` | Standard process |
| Rounded | `A(Text)` | Start/End points |
| Circle | `A((Text))` | Connection points |
| Diamond | `A{Text}` | Decision points |
| Hexagon | `A{{Text}}` | Preparation steps |
| Parallelogram | `A[/Text/]` | Input/Output |
| Cylinder | `A[(Text)]` | Database |

### Arrow Types

| Arrow | Syntax | Meaning |
|-------|--------|---------|
| Solid | `-->` | Flow direction |
| Dashed | `-.->` | Async/Optional |
| Thick | `==>` | Primary path |
| Dotted | `..>` | Dependency |

### Relationship Cardinality (ER Diagrams)

| Symbol | Meaning |
|--------|---------|
| `\|\|` | Exactly one |
| `o\|` | Zero or one |
| `}\|` | One or more |
| `}o` | Zero or more |

---

## Troubleshooting

### Issue 1: Diagram Not Rendering

**Cause:** Syntax error in Mermaid code

**Solution:**

- Validate syntax at [Mermaid Live Editor](https://mermaid.live/)
- Check for missing quotes, brackets, or semicolons
- Ensure proper diagram type declaration

### Issue 2: Diagram Too Wide

**Cause:** Too many nodes or long labels

**Solution:**

- Use vertical layout (`TD` instead of `LR`)
- Abbreviate long labels
- Split into multiple diagrams

### Issue 3: Special Characters Breaking Diagram

**Cause:** Unescaped special characters

**Solution:**

```mermaid
flowchart TD
    A["Use quotes for special chars: & < > #"]
    B["Or escape: &amp; &lt; &gt;"]
```

---

## MkDocs Integration

When MkDocs Material is implemented, Mermaid diagrams will:

1. **Auto-render** - No manual processing needed
2. **Dark mode support** - Diagrams adapt to theme
3. **Zoom capability** - Click to enlarge
4. **Export options** - Download as SVG/PNG

**Configuration (future):**

```yaml
# mkdocs.yml
plugins:
  - mermaid2:
      version: "10.6.0"
```

---

## Examples from Dashtam

### Example 1: OAuth Flow (from architecture docs)

```mermaid
sequenceDiagram
    participant U as User
    participant A as Dashtam API
    participant P as Provider (Schwab)
    participant C as Callback Server
    
    U->>A: POST /providers
    A-->>U: Provider created (id)
    U->>A: POST /providers/{id}/authorization
    A->>P: Redirect to OAuth page
    U->>P: Authorize app
    P->>C: Callback with code
    C->>A: Exchange code for tokens
    A->>A: Encrypt tokens
    A-->>U: 200 OK (connected)
```

### Example 2: Database Schema

```mermaid
erDiagram
    users ||--o{ tokens : has
    users ||--o{ provider_connections : owns
    providers ||--o{ provider_connections : referenced_by
    
    users {
        uuid id PK
        string email UK
        timestamp created_at
    }
    
    tokens {
        uuid id PK
        uuid user_id FK
        string token_type
        timestamp expires_at
    }
```

---

## Quick Reference

**Most Common Diagrams:**

1. **Flowchart** - `flowchart TD`
2. **Sequence** - `sequenceDiagram`
3. **ER Diagram** - `erDiagram`
4. **Mindmap** - `mindmap`

**Validation Tool:** [Mermaid Live Editor](https://mermaid.live/)

**Full Documentation:** [Mermaid Official Docs](https://mermaid.js.org/)

---

## Document Information

**Status:** Active
**Category:** Documentation Standards
**Created:** 2025-10-13
**Last Updated:** 2025-10-13
**Applies To:** All Dashtam documentation with diagrams
**Required:** Yes - All diagrams MUST use Mermaid syntax
