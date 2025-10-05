# API Flows (Manual Testing)

This section provides end-to-end, HTTPS-first guides for manually testing real user flows against the development environment (TLS-enabled), mirroring production usage as closely as possible.

Goals
- Validate user-centric scenarios (not just single endpoints)
- Enable reproducible, copy-pasteable steps for reviewers and teammates
- Keep a consistent approach across flows and domains

Conventions
- HTTPS-first with curl -k (dev TLS uses self-signed certs)
- Organize by domain (auth, providers, etc.), not HTTP verb
- Each flow document includes:
  - Purpose and prerequisites
  - Step-by-step commands (curl)
  - Expected responses (focused snippets)
  - Cleanup (where applicable)
  - Troubleshooting
- Use shell variables for inputs and never inline secrets in docs

Quick start (dev, HTTPS)

```bash
# From repo root
make dev-up

# Environment variables for curl (dev TLS)
BASE_URL=https://localhost:8000
CALLBACK_URL=https://127.0.0.1:8182

# Example test credentials (adjust per flow)
TEST_EMAIL="tester+$(date +%s)@example.com"
TEST_PASSWORD="SecurePass123!"
```

Directory layout

```
docs/api-flows/
├── README.md                 # Overview and conventions
├── flow-template.md          # Reusable template for new flows
├── auth/
│   ├── registration.md       # Register a new user (HTTPS)
│   └── login.md              # Login + use tokens (HTTPS)
└── providers/
    └── provider-onboarding.md  # Create provider → authorize → callback → verify
```

How to add a new flow
- Copy flow-template.md into the appropriate subdirectory
- Keep commands minimal and idempotent where possible
- Prefer small JSON examples focusing on fields testers must validate
- Add a Troubleshooting section that references common SSL and auth pitfalls
