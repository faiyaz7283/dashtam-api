# Modern Documentation Implementation Guide

**Implementing MkDocs + Material Theme for Dashtam Project:**

**Last Updated:** 2025-10-11  
**Status:** Implementation Ready  
**Priority:** P3 (Enhancement)  
**Estimated Effort:** 3-4 days

---

## 📖 Table of Contents

- [Overview](#overview)
- [Why MkDocs + Material?](#why-mkdocs--material)
- [Prerequisites](#prerequisites)
- [Implementation Phases](#implementation-phases)
  - [Phase 1: MkDocs Setup](#phase-1-mkdocs-setup)
  - [Phase 2: Material Theme Configuration](#phase-2-material-theme-configuration)
  - [Phase 3: API Documentation Auto-Generation](#phase-3-api-documentation-auto-generation)
  - [Phase 4: Diagrams & Visuals](#phase-4-diagrams--visuals)
  - [Phase 5: GitHub Actions CI/CD](#phase-5-github-actions-cicd)
  - [Phase 6: Documentation Organization](#phase-6-documentation-organization)
- [Testing & Verification](#testing--verification)
- [Maintenance](#maintenance)
- [References](#references)

---

## Overview

This guide provides step-by-step instructions for implementing a modern, automated documentation system for the Dashtam project using MkDocs with the Material theme. The system will:

- **Auto-generate API documentation** from Google-style docstrings
- **Provide beautiful, searchable documentation** with dark mode support
- **Integrate with CI/CD** for automatic builds and deployment
- **Support diagrams and visuals** with Mermaid.js
- **Deploy to GitHub Pages** for free, public hosting

**Benefits:**

- ✅ Professional documentation site matching modern standards
- ✅ Automatic API reference generation from source code
- ✅ Single source of truth (code docstrings → docs)
- ✅ Version control for documentation (treated as code)
- ✅ Fast, searchable, mobile-responsive interface
- ✅ Zero hosting costs (GitHub Pages)

---

## Why MkDocs + Material?

### Comparison with Alternatives

| Tool | Pros | Cons | Best For |
|------|------|------|----------|
| **MkDocs + Material** ✅ | Lightweight, beautiful UI, easy setup, strong plugins | Limited PDF export | Hybrid user/API docs |
| Sphinx + ReadTheDocs | Rich cross-references, multiple formats | Complex setup, steeper learning curve | Deep Python API reference |
| Docusaurus | Modern UI, versioning, multilingual | Node.js dependency, heavier | Large-scale docs |
| GitHub Pages (plain) | Simple, built-in | No search, limited styling | Simple static sites |

**Why We Chose MkDocs + Material:**

1. **Perfect fit for Python projects** with FastAPI
2. **Simple Markdown** - Easy to write and maintain
3. **Material theme** - Professional, modern design
4. **mkdocstrings plugin** - Auto-generates docs from Google-style docstrings
5. **Fast builds** - Seconds, not minutes
6. **Docker-friendly** - Fits our containerized workflow
7. **GitHub Actions** - Easy CI/CD integration

---

## Prerequisites

Before starting implementation, ensure you have:

- ✅ Docker and Docker Compose installed
- ✅ Python 3.13+ with UV package manager
- ✅ Git with `development` branch protection enabled
- ✅ GitHub repository with Actions enabled
- ✅ Existing `docs/` directory with Markdown files
- ✅ Google-style docstrings in `src/` codebase

**Familiarity with:**

- Markdown syntax
- YAML configuration
- Docker basics
- Git workflow

---

## Implementation Phases

### Phase 1: MkDocs Setup

**Goal:** Install MkDocs and create basic configuration

#### Step 1.1: Add Dependencies

Add MkDocs and plugins to `pyproject.toml`:

```toml
[project.optional-dependencies]
docs = [
    "mkdocs>=1.5.3",
    "mkdocs-material>=9.5.0",
    "mkdocstrings[python]>=0.24.0",
    "mkdocs-mermaid2-plugin>=1.1.1",
    "mkdocs-awesome-pages-plugin>=2.9.2",
]
```

Install dependencies in development container:

```bash
# From host machine
docker compose -f compose/docker-compose.dev.yml exec app uv add --group docs \
    mkdocs \
    mkdocs-material \
    'mkdocstrings[python]' \
    mkdocs-mermaid2-plugin \
    mkdocs-awesome-pages-plugin
```

#### Step 1.2: Initialize MkDocs

Create basic MkDocs configuration:

```bash
# Create mkdocs.yml in project root
docker compose -f compose/docker-compose.dev.yml exec app uv run mkdocs new .
```

This creates:

- `mkdocs.yml` - Main configuration file
- `docs/index.md` - Homepage (we already have docs/)

#### Step 1.3: Basic Configuration

Create/update `mkdocs.yml` in project root:

```yaml
# mkdocs.yml
site_name: Dashtam Documentation
site_description: Financial data aggregation platform with secure OAuth integration
site_author: Dashtam Development Team
site_url: https://faiyazhaider.github.io/Dashtam  # Update with your URL

repo_name: faiyazhaider/Dashtam
repo_url: https://github.com/faiyazhaider/Dashtam
edit_uri: edit/development/docs/

# Copyright notice
copyright: Copyright &copy; 2025 Dashtam Development Team

# Theme configuration (basic)
theme:
  name: material
  language: en

# Navigation structure (basic)
nav:
  - Home: index.md
  - Getting Started:
      - Setup: setup/installation.md
      - Configuration: setup/configuration.md
  - Development:
      - Architecture: development/architecture/overview.md
      - Testing: development/testing/guide.md
  - API Reference:
      - Endpoints: api/endpoints.md
```

#### Step 1.4: Test Basic Setup

Build and serve documentation locally:

```bash
# Build documentation
docker compose -f compose/docker-compose.dev.yml exec app uv run mkdocs build

# Serve documentation (development server)
docker compose -f compose/docker-compose.dev.yml exec app uv run mkdocs serve --dev-addr 0.0.0.0:8080

# Open in browser: http://localhost:8080
```

**Verify:**

- ✅ Documentation builds without errors
- ✅ Can navigate to http://localhost:8080
- ✅ Basic theme renders correctly
- ✅ Existing Markdown files load

---

### Phase 2: Material Theme Configuration

**Goal:** Configure Material theme with professional design and features

#### Step 2.1: Complete Theme Configuration

Update `mkdocs.yml` with full Material theme settings:

```yaml
theme:
  name: material
  language: en
  
  # Color scheme
  palette:
    # Light mode
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    
    # Dark mode
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  
  # Typography
  font:
    text: Roboto
    code: Roboto Mono
  
  # Features
  features:
    - navigation.instant        # Fast page loads
    - navigation.tracking       # URL updates as you scroll
    - navigation.tabs           # Top-level navigation tabs
    - navigation.tabs.sticky    # Sticky navigation tabs
    - navigation.sections       # Group sections in sidebar
    - navigation.expand         # Expand sections by default
    - navigation.top            # Back to top button
    - search.suggest            # Search suggestions
    - search.highlight          # Highlight search results
    - search.share              # Share search results
    - content.code.copy         # Copy code button
    - content.code.annotate     # Code annotations
    - toc.follow                # TOC follows scroll
  
  # Logo and favicon
  icon:
    repo: fontawesome/brands/github
    logo: material/currency-usd  # Financial platform icon
  
  # Favicon (create in docs/assets/)
  favicon: assets/favicon.png

# Extra CSS/JS (optional customization)
extra_css:
  - assets/stylesheets/extra.css

extra_javascript:
  - assets/javascripts/extra.js
```

#### Step 2.2: Configure Extra Features

Add footer, analytics, and social links:

```yaml
# Extra features
extra:
  # Social links
  social:
    - icon: fontawesome/brands/github
      link: https://github.com/faiyazhaider/Dashtam
    - icon: fontawesome/brands/python
      link: https://www.python.org
  
  # Version dropdown (for multi-version docs in future)
  version:
    provider: mike
    default: latest
  
  # Analytics (optional - add your tracking ID)
  analytics:
    provider: google
    property: G-XXXXXXXXXX  # Replace with your GA4 ID
    feedback:
      title: Was this page helpful?
      ratings:
        - icon: material/emoticon-happy-outline
          name: This page was helpful
          data: 1
          note: >-
            Thanks for your feedback!
        - icon: material/emoticon-sad-outline
          name: This page could be improved
          data: 0
          note: >-
            Thanks for your feedback! Help us improve by
            <a href="https://github.com/faiyazhaider/Dashtam/issues/new">
            opening an issue</a>.
```

#### Step 2.3: Configure Markdown Extensions

Enable advanced Markdown features:

```yaml
markdown_extensions:
  # Python Markdown extensions
  - abbr                      # Abbreviations
  - admonition                # Callout boxes
  - attr_list                 # Add HTML attributes to elements
  - def_list                  # Definition lists
  - footnotes                 # Footnotes
  - md_in_html                # Markdown in HTML
  - tables                    # Tables
  - toc:                      # Table of contents
      permalink: true
      toc_depth: 3
  
  # PyMdown Extensions
  - pymdownx.arithmatex:      # Math formulas
      generic: true
  - pymdownx.betterem:        # Better emphasis
      smart_enable: all
  - pymdownx.caret            # Superscript (^text^)
  - pymdownx.mark             # Highlight (==text==)
  - pymdownx.tilde            # Subscript (~text~)
  - pymdownx.critic           # Track changes
  - pymdownx.details          # Collapsible admonitions
  - pymdownx.emoji:           # Emoji support
      emoji_index: !!python/name:material.extensions.emoji.twemoji
      emoji_generator: !!python/name:material.extensions.emoji.to_svg
  - pymdownx.highlight:       # Code highlighting
      anchor_linenums: true
      line_spans: __span
      pygments_lang_class: true
  - pymdownx.inlinehilite     # Inline code highlighting
  - pymdownx.keys             # Keyboard keys
  - pymdownx.magiclink:       # Auto-link URLs
      repo_url_shorthand: true
      user: faiyazhaider
      repo: Dashtam
  - pymdownx.smartsymbols     # Smart symbols
  - pymdownx.superfences:     # Code blocks and diagrams
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - pymdownx.tabbed:          # Tabbed content
      alternate_style: true
  - pymdownx.tasklist:        # Task lists
      custom_checkbox: true
  - pymdownx.snippets         # Include file snippets
```

#### Step 2.4: Test Enhanced Theme

Rebuild and verify enhancements:

```bash
docker compose -f compose/docker-compose.dev.yml exec app uv run mkdocs serve --dev-addr 0.0.0.0:8080
```

**Verify:**

- ✅ Dark/light mode toggle works
- ✅ Search is functional
- ✅ Navigation tabs display correctly
- ✅ Code blocks have copy button
- ✅ Admonitions render properly

---

### Phase 3: API Documentation Auto-Generation

**Goal:** Auto-generate API reference from Python docstrings

#### Step 3.1: Configure mkdocstrings Plugin

Add plugin configuration to `mkdocs.yml`:

```yaml
plugins:
  - search                    # Built-in search
  - awesome-pages             # Auto-generate navigation from folder structure
  
  # mkdocstrings - Auto-generate API docs from docstrings
  - mkdocstrings:
      enabled: !ENV [ENABLE_MKDOCSTRINGS, true]
      default_handler: python
      handlers:
        python:
          options:
            # Docstring style (Google-style for Dashtam)
            docstring_style: google
            docstring_section_style: table
            
            # What to show
            show_root_heading: true
            show_root_full_path: true
            show_symbol_type_heading: true
            show_symbol_type_toc: true
            show_source: true
            show_bases: true
            show_submodules: true
            
            # Member options
            members_order: source
            filters:
              - "!^_"           # Exclude private members
              - "^__init__$"    # But include __init__
            
            # Signatures
            show_signature: true
            show_signature_annotations: true
            signature_crossrefs: true
            separate_signature: true
            line_length: 80
            
            # Headings
            heading_level: 2
            
            # Inheritance
            inherited_members: false
            
            # Type hints
            annotations_path: brief
            
            # Merge __init__ docstring into class docstring
            merge_init_into_class: true
            
            # Python path resolution
            paths: [src]
```

#### Step 3.2: Create API Reference Pages

Create `docs/api/reference.md` to auto-generate API docs:

```markdown
# API Reference

Auto-generated API documentation from source code docstrings.

## Authentication

::: src.services.auth_service.AuthService
    options:
      show_root_heading: true
      show_source: true

::: src.services.jwt_service.JWTService
    options:
      show_root_heading: true
      show_source: true

::: src.services.password_service.PasswordService
    options:
      show_root_heading: true
      show_source: true

## Models

::: src.models.user.User
    options:
      show_root_heading: true
      show_source: true
      members:
        - __init__

::: src.models.provider.Provider
    options:
      show_root_heading: true
      show_source: true

## API Endpoints

::: src.api.v1.auth
    options:
      show_root_heading: true
      show_source: true
      filters:
        - "!^_"
        - "^router$"

::: src.api.v1.providers
    options:
      show_root_heading: true
      show_source: true
```

Create `docs/api/endpoints.md` for endpoint listing:

```markdown
# API Endpoints

Complete list of REST API endpoints organized by domain.

## Authentication Endpoints

**Base Path:** `/api/v1/auth`

### User Registration

::: src.api.v1.auth.register
    options:
      heading_level: 4

### Login

::: src.api.v1.auth.login
    options:
      heading_level: 4

### Token Refresh

::: src.api.v1.auth.refresh_token
    options:
      heading_level: 4

---

## Provider Endpoints

**Base Path:** `/api/v1/providers`

### List Providers

::: src.api.v1.providers.list_providers
    options:
      heading_level: 4

### Create Provider

::: src.api.v1.providers.create_provider
    options:
      heading_level: 4
```

#### Step 3.3: Test API Documentation Generation

Build and verify API docs:

```bash
docker compose -f compose/docker-compose.dev.yml exec app uv run mkdocs build
docker compose -f compose/docker-compose.dev.yml exec app uv run mkdocs serve --dev-addr 0.0.0.0:8080
```

**Verify:**

- ✅ API reference pages render correctly
- ✅ Docstrings are properly formatted (Google-style)
- ✅ Type hints display correctly
- ✅ Source links work
- ✅ Cross-references between classes work

---

### Phase 4: Diagrams & Visuals

**Goal:** Add architecture diagrams and visual documentation

#### Step 4.1: Configure Mermaid Plugin

Add Mermaid configuration to `mkdocs.yml`:

```yaml
plugins:
  # ... existing plugins ...
  
  # Mermaid diagrams
  - mermaid2:
      version: 10.6.1
```

#### Step 4.2: Create Architecture Diagrams

Create `docs/development/architecture/diagrams.md`:

```markdown
    
    # Architecture Diagrams

    Visual documentation of Dashtam's system architecture.

    ## System Overview

    ```mermaid
    graph TD
        A[Client] -->|HTTPS| B(FastAPI Backend)
        B -->|Async| C{PostgreSQL}
        B -->|Cache| D{Redis}
        B -->|OAuth| E[Financial Providers]
        B -->|Email| F[AWS SES]
        
        C -->|User Data| G[Users Table]
        C -->|Auth Data| H[Refresh Tokens]
        C -->|Provider Data| I[Providers Table]
        
        style B fill:#4051b5
        style C fill:#336791
        style D fill:#dc382d
    ```

    ## Authentication Flow

    ```mermaid
    sequenceDiagram
        participant C as Client
        participant API as FastAPI
        participant Auth as AuthService
        participant DB as PostgreSQL
        participant Email as EmailService
        
        C->>API: POST /auth/register
        API->>Auth: register_user()
        Auth->>DB: Create user (email_verified=False)
        Auth->>Email: Send verification email
        Email-->>C: Verification email
        
        C->>API: POST /auth/verify-email
        API->>Auth: verify_email(token)
        Auth->>DB: Update user (email_verified=True)
        Auth-->>C: Email verified
        
        C->>API: POST /auth/login
        API->>Auth: login(email, password)
        Auth->>DB: Validate credentials
        Auth-->>C: Access token + Refresh token
    ```

    ## Database Schema

    ```mermaid
    erDiagram
        USERS ||--o{ PROVIDERS : owns
        USERS ||--o{ REFRESH_TOKENS : has
        USERS ||--o{ EMAIL_VERIFICATION_TOKENS : has
        USERS ||--o{ PASSWORD_RESET_TOKENS : has
        PROVIDERS ||--|| OAUTH_TOKENS : stores
        PROVIDERS ||--o{ AUDIT_LOGS : generates
        
        USERS {
            uuid id PK
            string email UK
            string password_hash
            boolean email_verified
            int failed_login_attempts
            timestamptz locked_until
            timestamptz created_at
            timestamptz updated_at
            timestamptz deleted_at
        }
        
        REFRESH_TOKENS {
            uuid id PK
            uuid user_id FK
            string token_hash
            string device_info
            string ip_address
            boolean revoked
            timestamptz expires_at
            timestamptz created_at
        }
        
        PROVIDERS {
            uuid id PK
            uuid user_id FK
            string name
            string provider_type
            boolean connected
            timestamptz connected_at
            timestamptz created_at
        }
    ```
```

#### Step 4.3: Add Component Diagrams

Create diagrams for key components in their respective docs.

**Example - Token Rotation Flow** (`docs/development/guides/token-rotation.md`):

```markdown


    ## Token Rotation Process

    ```mermaid
    flowchart TD
        A[Client Request] --> B{Check Access Token}
        B -->|Expired| C[Use Refresh Token]
        B -->|Valid| D[Process Request]
        
        C --> E{Validate Refresh Token}
        E -->|Invalid/Expired| F[Reject 401]
        E -->|Valid| G[Generate New Tokens]
        
        G --> H[Revoke Old Refresh Token]
        H --> I[Hash New Refresh Token]
        I --> J[Store in Database]
        J --> K[Return Tokens to Client]
        
        K --> L{Client Updates?}
        L -->|Yes| M[Success]
        L -->|No| N[Potential Token Theft]
        
        style G fill:#4caf50
        style H fill:#ff9800
        style N fill:#f44336
    ```

```

#### Step 4.4: Test Diagrams

Rebuild and verify diagrams render:

```bash
docker compose -f compose/docker-compose.dev.yml exec app uv run mkdocs build
docker compose -f compose/docker-compose.dev.yml exec app uv run mkdocs serve --dev-addr 0.0.0.0:8080
```

**Verify:**

- ✅ Mermaid diagrams render correctly
- ✅ Diagrams are interactive (zoom, pan)
- ✅ Diagram syntax is correct
- ✅ Diagrams match architecture

---

### Phase 5: GitHub Actions CI/CD

**Goal:** Automate documentation builds and deployment

#### Step 5.1: Create Documentation Workflow

Create `.github/workflows/docs.yml`:

```yaml
name: Deploy Documentation

on:
  push:
    branches:
      - main
      - development  # Deploy docs from development too
    paths:
      - 'docs/**'
      - 'src/**'  # Rebuild on code changes (docstrings)
      - 'mkdocs.yml'
      - '.github/workflows/docs.yml'
  
  # Manual trigger
  workflow_dispatch:

permissions:
  contents: write  # Needed for gh-pages deployment

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for git info plugin
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      
      - name: Install UV
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.cargo/bin" >> $GITHUB_PATH
      
      - name: Install dependencies
        run: |
          uv pip install --system \
            mkdocs \
            mkdocs-material \
            'mkdocstrings[python]' \
            mkdocs-mermaid2-plugin \
            mkdocs-awesome-pages-plugin
      
      - name: Build documentation
        run: mkdocs build --strict
      
      - name: Deploy to GitHub Pages
        if: github.ref == 'refs/heads/main'
        run: mkdocs gh-deploy --force --clean --verbose
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

#### Step 5.2: Update Makefile

Add documentation commands to `Makefile`:

```makefile
# Documentation commands
.PHONY: docs-build docs-serve docs-deploy docs-clean

docs-build:  ## Build documentation site
  @echo "Building documentation..."
  docker compose -f compose/docker-compose.dev.yml exec app uv run mkdocs build

docs-serve:  ## Serve documentation locally (http://localhost:8080)
  @echo "Serving documentation at http://localhost:8080"
  docker compose -f compose/docker-compose.dev.yml exec app uv run mkdocs serve --dev-addr 0.0.0.0:8080

docs-deploy:  ## Deploy documentation to GitHub Pages
  @echo "Deploying documentation to GitHub Pages..."
  docker compose -f compose/docker-compose.dev.yml exec app uv run mkdocs gh-deploy --force

docs-clean:  ## Clean built documentation
  @echo "Cleaning documentation build..."
  rm -rf site/
```

#### Step 5.3: Configure GitHub Pages

1. **Enable GitHub Pages** in repository settings:
   - Go to: Settings → Pages
   - Source: Deploy from branch
   - Branch: `gh-pages` (auto-created by mkdocs gh-deploy)
   - Folder: `/ (root)`

2. **Add GITHUB_TOKEN permissions** (if workflow fails):
   - Settings → Actions → General
   - Workflow permissions: Read and write permissions

3. **Verify deployment URL:**
   - Should be: `https://faiyazhaider.github.io/Dashtam/`

#### Step 5.4: Test CI/CD Pipeline

Commit and push changes to trigger workflow:

```bash
git add mkdocs.yml .github/workflows/docs.yml Makefile
git commit -m "docs: add MkDocs CI/CD pipeline"
git push origin development
```

**Verify:**

- ✅ GitHub Actions workflow runs successfully
- ✅ Documentation builds without errors
- ✅ GitHub Pages site is live
- ✅ All pages accessible
- ✅ Search works on deployed site

---

### Phase 6: Documentation Organization

**Goal:** Migrate and organize existing documentation

#### Step 6.1: Update Navigation Structure

Update `mkdocs.yml` navigation with complete hierarchy:

```yaml
nav:
  - Home: index.md
  
  - Getting Started:
      - Overview: README.md
      - Installation: setup/installation.md
      - Configuration: setup/configuration.md
      - Quick Start: setup/quick-start.md
  
  - User Guide:
      - Authentication: guides/authentication.md
      - API Usage: guides/api-usage.md
      - Troubleshooting: guides/troubleshooting.md
  
  - API Reference:
      - Endpoints: api/endpoints.md
      - Models: api/models.md
      - Services: api/services.md
      - Complete Reference: api/reference.md
  
  - Development:
      - Architecture:
          - Overview: development/architecture/overview.md
          - JWT Authentication: development/architecture/jwt-authentication.md
          - RESTful API Design: development/architecture/restful-api-design.md
          - Diagrams: development/architecture/diagrams.md
      
      - Infrastructure:
          - Docker Setup: development/infrastructure/docker-setup.md
          - CI/CD Pipeline: development/infrastructure/ci-cd.md
          - Database Migrations: development/infrastructure/database-migrations.md
      
      - Testing:
          - Strategy: development/testing/strategy.md
          - Guide: development/testing/guide.md
          - Best Practices: development/testing/best-practices.md
      
      - Guides:
          - Git Workflow: development/guides/git-workflow.md
          - Docstring Standards: development/guides/docstring-standards.md
          - Token Rotation: development/guides/token-rotation.md
          - UV Package Management: development/guides/uv-package-management.md
  
  - Contributing:
      - How to Contribute: CONTRIBUTING.md
      - Code of Conduct: CODE_OF_CONDUCT.md
```

#### Step 6.2: Create Missing Index Pages

Create index pages for each major section.

**Example - `docs/development/index.md`:**

```markdown
# Developer Documentation

Welcome to the Dashtam developer documentation. This section contains everything you need to know to work on the Dashtam codebase.

## Quick Links

- [Architecture Overview](architecture/overview.md) - System design and patterns
- [Testing Guide](testing/guide.md) - How to write and run tests
- [Docker Setup](infrastructure/docker-setup.md) - Container configuration
- [Git Workflow](guides/git-workflow.md) - Branch strategy and conventions

## Getting Started

1. **Clone the repository** and set up your development environment
2. **Read the architecture overview** to understand system design
3. **Review coding standards** in [Docstring Standards](guides/docstring-standards.md)
4. **Run the test suite** following the [Testing Guide](testing/guide.md)
5. **Make your changes** following the [Git Workflow](guides/git-workflow.md)

## Key Documentation

### Architecture
Learn about Dashtam's design patterns, security model, and component interactions.

### Testing
Comprehensive testing strategy with unit, integration, and smoke tests.

### Infrastructure
Docker, CI/CD, database migrations, and deployment configuration.

### Guides
Step-by-step guides for common development tasks and workflows.
```

#### Step 6.3: Add Cross-References

Add navigation links between related documents.

**Example - In architecture docs:**

```markdown
## Related Documentation

- [RESTful API Design](restful-api-design.md) - API design principles
- [JWT Authentication](jwt-authentication.md) - Authentication implementation
- [Database Migrations](../infrastructure/database-migrations.md) - Schema evolution
- [Testing Strategy](../testing/strategy.md) - How we test the architecture

## See Also

- [JWT Quick Reference](../guides/jwt-auth-quick-reference.md)
- [Token Rotation Guide](../guides/token-rotation.md)
```

#### Step 6.4: Update Main README

Update `docs/index.md` (homepage):

```markdown
# Welcome to Dashtam Documentation

**Secure financial data aggregation platform with OAuth integration**

Dashtam connects to multiple financial institutions through OAuth2, providing a unified API for accessing accounts, transactions, and financial data. Built with FastAPI, PostgreSQL, Redis, and Docker.

## Quick Navigation

<div class="grid cards" markdown>

- :material-rocket-launch: **[Getting Started](setup/installation.md)**
  
  Installation, configuration, and quick start guide

- :material-book-open-variant: **[API Reference](api/endpoints.md)**
  
  Complete API endpoint documentation

- :material-code-braces: **[Development Guide](development/)**
  
  Architecture, testing, and contribution guidelines

- :material-help-circle: **[Troubleshooting](guides/troubleshooting.md)**
  
  Common issues and solutions

</div>

## Key Features

- ✅ **JWT Authentication** - Secure user authentication with refresh token rotation
- ✅ **OAuth2 Integration** - Connect to financial providers (Schwab, Plaid, etc.)
- ✅ **RESTful API** - 10/10 REST compliance score
- ✅ **Production Ready** - 295 tests, 76% coverage, comprehensive security
- ✅ **Modern Stack** - FastAPI, PostgreSQL, Redis, Docker

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | FastAPI 0.110+ | Async API framework |
| **Database** | PostgreSQL 17.6 | Relational data store |
| **Cache** | Redis 8.2 | Session management |
| **Auth** | JWT + Bcrypt | Secure authentication |
| **Container** | Docker + Compose | Development environment |
| **Testing** | Pytest | Comprehensive test suite |

## Quick Links

- [GitHub Repository](https://github.com/faiyazhaider/Dashtam)
- [API Documentation](/api/endpoints)
- [Development Setup](/development/infrastructure/docker-setup)
- [Testing Guide](/development/testing/guide)

## Getting Help

- **Issues:** [GitHub Issues](https://github.com/faiyazhaider/Dashtam/issues)
- **Discussions:** [GitHub Discussions](https://github.com/faiyazhaider/Dashtam/discussions)
- **Documentation:** This site!
```

---

## Testing & Verification

### Local Testing Checklist

Before deploying to GitHub Pages, verify locally:

- [ ] All pages build without errors: `make docs-build`
- [ ] Navigation structure is correct
- [ ] Search finds content accurately
- [ ] Dark/light mode toggle works
- [ ] API reference generates from docstrings
- [ ] Mermaid diagrams render correctly
- [ ] Code blocks have syntax highlighting
- [ ] Copy-to-clipboard works on code blocks
- [ ] Internal links work (no 404s)
- [ ] External links open in new tabs
- [ ] Mobile responsive design works
- [ ] Back-to-top button appears

### CI/CD Verification

- [ ] GitHub Actions workflow passes
- [ ] Documentation deploys to GitHub Pages
- [ ] Deployed site matches local build
- [ ] All assets (images, CSS, JS) load
- [ ] HTTPS works on GitHub Pages
- [ ] Custom domain works (if configured)

### Content Verification

- [ ] All existing docs migrated
- [ ] No broken links
- [ ] All code examples work
- [ ] Docstrings render correctly
- [ ] Diagrams are accurate
- [ ] Navigation is intuitive
- [ ] Index pages are complete

---

## Maintenance

### Regular Tasks

**Periodically:**

- Review and update outdated documentation
- Check for broken links
- Update screenshots if UI changed
- Review analytics (if enabled) for popular pages

**Per Release:**

- Update version numbers
- Document new features
- Update API reference
- Add release notes

**As Needed:**

- Fix reported documentation issues
- Add new guides for common questions
- Improve search keywords
- Enhance diagrams

### Updating Documentation

**Edit Existing Pages:**

```bash
# 1. Edit Markdown files in docs/
vim docs/development/guides/my-guide.md

# 2. Test locally
make docs-serve

# 3. Commit and push
git add docs/
git commit -m "docs: update guide for new feature"
git push origin development
```

**Add New API Documentation:**

```bash
# 1. Add Google-style docstrings to code
# 2. Update docs/api/reference.md with new module
# 3. Test generation
make docs-build

# 4. Verify output
make docs-serve
```

**Add New Diagrams:**

```bash
# 1. Add Mermaid syntax to Markdown file
# 2. Verify rendering locally
# 3. Commit changes
```

### Troubleshooting

**Build Errors:**

```bash
# Clear cache and rebuild
make docs-clean
make docs-build

# Check for syntax errors in mkdocs.yml
uv run mkdocs build --strict --verbose
```

**Plugin Issues:**

```bash
# Reinstall dependencies
uv add --group docs mkdocs mkdocs-material 'mkdocstrings[python]'

# Check plugin versions
uv pip list | grep mkdocs
```

**Deployment Failures:**

```bash
# Check GitHub Actions logs
# Verify GITHUB_TOKEN permissions
# Ensure gh-pages branch exists
```

---

## References

### Official Documentation

- [MkDocs](https://www.mkdocs.org/) - Static site generator
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) - Theme documentation
- [mkdocstrings](https://mkdocstrings.github.io/) - API doc generation
- [Mermaid.js](https://mermaid.js.org/) - Diagram syntax

### Project Documentation

- [Docstring Standards](docstring-standards.md) - Google-style docstring guide
- [Documentation Research](../../research/documentation_guide_research.md) - Research notes
- WARP.md - Project rules and context

### Related Guides

- [Git Workflow](git-workflow.md) - Contributing documentation changes
- [Testing Guide](../testing/guide.md) - Testing documentation examples
- [Docker Setup](../infrastructure/docker-setup.md) - Running docs in Docker

---

**Last Updated:** 2025-10-11  
**Maintained By:** Development Team  
**Status:** Ready for implementation  
**Priority:** P3 (Enhancement)  
**Estimated Effort:** 3-4 days
