.PHONY: help dev-up dev-down dev-logs dev-shell dev-db-shell dev-redis-cli dev-restart dev-status dev-build dev-rebuild test-up test-down test-logs test-shell test-build test-rebuild test test-unit test-integration test-api test-smoke ci-test lint format lint-md lint-md-check lint-md-fix md-check docs-serve docs-build docs-stop migrate migrate-create migrate-down migrate-history migrate-current clean status-all ps check

# ==============================================================================
# HELP
# ==============================================================================

.DEFAULT_GOAL := help

help:
	@echo "🎯 Dashtam - Financial Data Aggregation Platform"
	@echo ""
	@echo "📋 Quick Start:"
	@echo "  1. Start Traefik:     cd ~/docker-services/traefik && make up"
	@echo "  2. Start dev:         make dev-up"
	@echo "  3. Run migrations:    make migrate"
	@echo "  4. View app:          https://dashtam.local"
	@echo ""
	@echo "🚀 Development (https://dashtam.local):"
	@echo "  make dev-up          - Start development environment"
	@echo "  make dev-down        - Stop development environment"
	@echo "  make dev-logs        - View development logs (follow)"
	@echo "  make dev-shell       - Shell into app container"
	@echo "  make dev-db-shell    - PostgreSQL shell"
	@echo "  make dev-redis-cli   - Redis CLI"
	@echo "  make dev-restart     - Restart development environment"
	@echo "  make dev-build       - Build development containers"
	@echo "  make dev-rebuild     - Rebuild containers (no cache)"
	@echo "  make dev-status      - Show service status"
	@echo ""
	@echo "🧪 Testing (https://test.dashtam.local):"
	@echo "  make test-up         - Start test environment"
	@echo "  make test-down       - Stop test environment"
	@echo "  make test-build      - Build test containers"
	@echo "  make test-rebuild    - Rebuild containers (no cache)"
	@echo "  make test            - Run all tests with coverage"
	@echo "  make test-unit       - Unit tests only"
	@echo "  make test-integration - Integration tests only"
	@echo "  make test-api        - API tests only"
	@echo "  make test-smoke      - Smoke tests (E2E)"
	@echo "  make test-logs       - View test logs"
	@echo "  make test-shell      - Shell into test container"
	@echo ""
	@echo "🤖 CI/CD:"
	@echo "  make ci-test         - Run CI test suite (GitHub Actions simulation)"
	@echo ""
	@echo "✨ Code Quality:"
	@echo "  make lint            - Run Python linters (ruff)"
	@echo "  make format          - Format Python code (ruff)"
	@echo "  make type-check      - Type check with mypy (strict)"
	@echo "  make lint-md FILE=path/to/file.md - Lint markdown (flexible)"
	@echo "  make lint-md-fix     - Fix markdown issues (with safety)"
	@echo ""
	@echo "📚 Documentation:"
	@echo "  make docs-serve      - Start MkDocs live preview"
	@echo "  make docs-build      - Build static docs (strict mode)"
	@echo "  make docs-stop       - Stop MkDocs server"
	@echo ""
	@echo "📦 Database:"
	@echo "  make migrate         - Apply pending migrations"
	@echo "  make migrate-create  - Create new migration"
	@echo "  make migrate-down    - Rollback last migration"
	@echo "  make migrate-history - Show migration history"
	@echo "  make migrate-current - Show current version"
	@echo ""
	@echo "🔧 Utilities:"
	@echo "  make check           - Verify Traefik is running"
	@echo "  make status-all      - Show all environment status"
	@echo "  make ps              - Show all Dashtam containers"
	@echo "  make clean           - Stop and clean ALL environments"
	@echo ""
	@echo "📖 Full docs: https://faiyaz7283.github.io/Dashtam/"

# ==============================================================================
# DEVELOPMENT ENVIRONMENT
# ==============================================================================

dev-up: _check-traefik _ensure-env-dev
	@echo "🚀 Starting DEVELOPMENT environment..."
	@docker compose -f compose/docker-compose.dev.yml up -d
	@echo ""
	@echo "✅ Development services started!"
	@echo ""
	@echo "🌐 Access:"
	@echo "   App:       https://dashtam.local"
	@echo "   API Docs:  https://dashtam.local/docs"
	@echo "   Dashboard: http://localhost:8080 (Traefik)"
	@echo ""
	@echo "🐘 Database:  localhost:5432"
	@echo "🔴 Redis:     localhost:6379"
	@echo ""
	@echo "📋 Commands:"
	@echo "   Logs:  make dev-logs"
	@echo "   Shell: make dev-shell"

dev-down:
	@echo "🛑 Stopping DEVELOPMENT environment..."
	@docker compose -f compose/docker-compose.dev.yml down
	@echo "✅ Development stopped"

dev-logs:
	@docker compose -f compose/docker-compose.dev.yml logs -f

dev-shell:
	@docker compose -f compose/docker-compose.dev.yml exec app /bin/bash

dev-db-shell:
	@docker compose -f compose/docker-compose.dev.yml exec postgres psql -U dashtam_user -d dashtam

dev-redis-cli:
	@docker compose -f compose/docker-compose.dev.yml exec redis redis-cli

dev-restart: dev-down dev-up

dev-status:
	@echo "📊 Development Status:"
	@docker compose -f compose/docker-compose.dev.yml ps

dev-build: _check-traefik _ensure-env-dev
	@echo "🔨 Building DEVELOPMENT containers..."
	@docker compose -f compose/docker-compose.dev.yml build
	@echo "✅ Development containers built"

dev-rebuild: _check-traefik _ensure-env-dev
	@echo "🔨 Rebuilding DEVELOPMENT containers (no cache)..."
	@docker compose -f compose/docker-compose.dev.yml build --no-cache
	@echo "✅ Development containers rebuilt"

# ==============================================================================
# TEST ENVIRONMENT
# ==============================================================================

test-up: _check-traefik _ensure-env-test
	@echo "🧪 Starting TEST environment..."
	@docker compose -f compose/docker-compose.test.yml up -d
	@sleep 3
	@echo ""
	@echo "✅ Test services started!"
	@echo ""
	@echo "🌐 Access:"
	@echo "   App:  https://test.dashtam.local"
	@echo ""
	@echo "🐘 Database:  localhost:5433"
	@echo "🔴 Redis:     localhost:6380"
	@echo ""
	@echo "🧪 Run tests: make test"

test-down:
	@echo "🛑 Stopping TEST environment..."
	@docker compose -f compose/docker-compose.test.yml down
	@echo "✅ Test stopped"

test-logs:
	@docker compose -f compose/docker-compose.test.yml logs -f

test-shell:
	@docker compose -f compose/docker-compose.test.yml exec app /bin/bash

test-build: _check-traefik _ensure-env-test
	@echo "🔨 Building TEST containers..."
	@docker compose -f compose/docker-compose.test.yml build
	@echo "✅ Test containers built"

test-rebuild: _check-traefik _ensure-env-test
	@echo "🔨 Rebuilding TEST containers (no cache)..."
	@docker compose -f compose/docker-compose.test.yml build --no-cache
	@echo "✅ Test containers rebuilt"

# ==============================================================================
# TESTING
# ==============================================================================

test:
	@echo "🧪 Running all tests with coverage..."
	@docker compose -f compose/docker-compose.test.yml ps -q app > /dev/null 2>&1 || make test-up
	@docker compose -f compose/docker-compose.test.yml exec -T app uv run pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

test-unit:
	@echo "🧪 Running unit tests..."
	@docker compose -f compose/docker-compose.test.yml ps -q app > /dev/null 2>&1 || make test-up
	@docker compose -f compose/docker-compose.test.yml exec -T app uv run pytest tests/unit/ -v

test-integration:
	@echo "🧪 Running integration tests..."
	@docker compose -f compose/docker-compose.test.yml ps -q app > /dev/null 2>&1 || make test-up
	@docker compose -f compose/docker-compose.test.yml exec -T app uv run pytest tests/integration/ -v

test-api:
	@echo "🧪 Running API tests..."
	@docker compose -f compose/docker-compose.test.yml ps -q app > /dev/null 2>&1 || make test-up
	@docker compose -f compose/docker-compose.test.yml exec -T app uv run pytest tests/api/ -v

test-smoke:
	@echo "🔥 Running smoke tests (E2E)..."
	@docker compose -f compose/docker-compose.test.yml ps -q app > /dev/null 2>&1 || make test-up
	@docker compose -f compose/docker-compose.test.yml exec -T app uv run pytest tests/smoke/ -v

# ==============================================================================
# CI/CD
# ==============================================================================

ci-test: _ensure-env-ci
	@echo "🤖 Running CI test suite..."
	@docker compose -f compose/docker-compose.ci.yml up --build --abort-on-container-exit --exit-code-from app
	@docker compose -f compose/docker-compose.ci.yml down -v
	@echo "✅ CI tests completed"

# ==============================================================================
# CODE QUALITY
# ==============================================================================

lint: dev-up
	@echo "🔍 Running linters..."
	@docker compose -f compose/docker-compose.dev.yml exec app uv run ruff check src/ tests/

format: dev-up
	@echo "✨ Formatting code..."
	@docker compose -f compose/docker-compose.dev.yml exec app uv run ruff format src/ tests/
	@docker compose -f compose/docker-compose.dev.yml exec app uv run ruff check --fix src/ tests/

type-check: dev-up
	@echo "🔍 Running type checks with mypy..."
	@docker compose -f compose/docker-compose.dev.yml exec -w /app app uv run mypy src

# ==============================================================================
# MARKDOWN LINTING
# ==============================================================================
# 
# Professional markdown linting with flexible targeting and safety controls.
# 
# Commands:
#   lint-md      - Check markdown files (non-destructive, CI-friendly)
#   lint-md-fix  - Fix markdown issues with safety controls
# 
# Targeting Options (apply to both commands):
#   (none)                          - All markdown files in project
#   FILE=path/to/file.md            - Single file
#   FILES="file1.md file2.md"       - Multiple specific files
#   DIR=docs/guides                 - Entire directory
#   DIRS="docs tests"               - Multiple directories
#   PATTERN="docs/**/*.md"          - Custom glob pattern
#   PATHS="README.md docs/"         - Mixed files and directories
# 
# Safety Options (lint-md-fix only):
#   DRY_RUN=1                       - Preview changes without applying
#   DIFF=1                          - Generate patch file for manual review
# 
# Examples:
#   make lint-md                              # Check all files
#   make lint-md FILE=README.md               # Check single file
#   make lint-md DIR=docs/guides              # Check directory
#   make lint-md-fix DRY_RUN=1                # Preview all fixes
#   make lint-md-fix FILE=README.md           # Fix single file (prompt)
#   make lint-md-fix DIR=docs DIFF=1          # Generate patch for docs/
# 
# ==============================================================================

# Configuration
MARKDOWN_LINT_IMAGE := node:24-alpine
MARKDOWN_LINT_CMD := npx markdownlint-cli2
MARKDOWN_BASE_PATTERN := '**/*.md'
# Note: Ignore patterns are configured in .markdownlint-cli2.jsonc

# ----------------------------------------------------------------------------
# Helper: Build lint target from parameters
# ----------------------------------------------------------------------------
define build_lint_target
	$(eval LINT_TARGET := )
	$(eval TARGET_DESC := )
	
	$(if $(FILE),\
		$(eval LINT_TARGET := '$(FILE)')\
		$(eval TARGET_DESC := $(FILE)))
	
	$(if $(FILES),\
		$(eval LINT_TARGET := $(FILES))\
		$(eval TARGET_DESC := $(FILES)))
	
	$(if $(DIR),\
		$(eval LINT_TARGET := '$(DIR)/**/*.md')\
		$(eval TARGET_DESC := $(DIR)/))
	
	$(if $(DIRS),\
		$(eval LINT_TARGET := $(foreach dir,$(DIRS),'$(dir)/**/*.md'))\
		$(eval TARGET_DESC := $(DIRS)))
	
	$(if $(PATTERN),\
		$(eval LINT_TARGET := '$(PATTERN)')\
		$(eval TARGET_DESC := $(PATTERN)))
	
	$(if $(PATHS),\
		$(eval LINT_TARGET := $(PATHS))\
		$(eval TARGET_DESC := $(PATHS)))
	
	$(if $(LINT_TARGET),,\
		$(eval LINT_TARGET := $(MARKDOWN_BASE_PATTERN))\
		$(eval TARGET_DESC := all markdown files))
endef

# ----------------------------------------------------------------------------
# Command: lint-md
# ----------------------------------------------------------------------------
lint-md:
	@$(call build_lint_target)
	@echo "🔍 Linting: $(TARGET_DESC)"
	@docker run --rm \
		-v $(PWD):/workspace:ro \
		-w /workspace \
		$(MARKDOWN_LINT_IMAGE) \
		sh -c "$(MARKDOWN_LINT_CMD) $(LINT_TARGET) || exit 1"
	@echo "✅ Markdown linting complete!"

# CI-friendly alias (identical to lint-md)
lint-md-check: lint-md

# ----------------------------------------------------------------------------
# Command: lint-md-fix
# ----------------------------------------------------------------------------
lint-md-fix:
	@$(call build_lint_target)
	@$(call _lint_md_fix_execute)

# ----------------------------------------------------------------------------
# Helper: Execute lint-md-fix based on mode
# ----------------------------------------------------------------------------
define _lint_md_fix_execute
	@if [ "$(DRY_RUN)" = "1" ]; then \
		$(call _lint_md_fix_dry_run); \
	elif [ "$(DIFF)" = "1" ]; then \
		$(call _lint_md_fix_diff); \
	else \
		$(call _lint_md_fix_apply); \
	fi
endef

# ----------------------------------------------------------------------------
# Helper: Dry-run mode (preview changes)
# ----------------------------------------------------------------------------
define _lint_md_fix_dry_run
	echo "🔍 DRY RUN: Previewing changes for $(TARGET_DESC)..."; \
	echo "   (no files will be modified)"; \
	echo ""; \
	docker run --rm \
		-v $(PWD):/workspace:ro \
		-w /workspace \
		$(MARKDOWN_LINT_IMAGE) \
		sh -c "$(MARKDOWN_LINT_CMD) --fix --dry-run $(LINT_TARGET) 2>&1 \
			| grep -E '(would fix|Error|Warning)' \
			|| echo '   ✅ No fixable issues found'"; \
	echo ""; \
	echo "💡 To apply fixes, run without DRY_RUN:"; \
	echo "   make lint-md-fix $(if $(FILE),FILE=$(FILE))$(if $(DIR),DIR=$(DIR))$(if $(PATTERN),PATTERN=$(PATTERN))"
endef

# ----------------------------------------------------------------------------
# Helper: DIFF mode (generate patch file)
# ----------------------------------------------------------------------------
define _lint_md_fix_diff
	echo "📝 Generating diff patch for $(TARGET_DESC)..."; \
	echo ""; \
	timestamp=$$(date +%Y%m%d_%H%M%S); \
	patch_file="markdown-lint-fix_$$timestamp.patch"; \
	echo "📄 Patch file: $$patch_file"; \
	echo ""; \
	docker run --rm \
		-v $(PWD):/workspace \
		-w /workspace \
		$(MARKDOWN_LINT_IMAGE) \
		sh -c "git diff > /tmp/before.patch && \
			$(MARKDOWN_LINT_CMD) --fix $(LINT_TARGET) && \
			git diff > /workspace/$$patch_file && \
			git checkout -- . && \
			cat /workspace/$$patch_file"; \
	echo ""; \
	echo "✅ Patch generated: $$patch_file"; \
	echo ""; \
	echo "📖 Next steps:"; \
	echo "   1. Review patch: cat $$patch_file"; \
	echo "   2. Apply patch:  git apply $$patch_file"; \
	echo "   3. Verify:       make lint-md"; \
	echo "   4. Commit:       git add . && git commit -m 'docs: fix markdown linting'"
endef

# ----------------------------------------------------------------------------
# Helper: Apply mode (fix with confirmation)
# ----------------------------------------------------------------------------
define _lint_md_fix_apply
	echo "⚠️  WARNING: This will modify markdown files!"; \
	echo ""; \
	echo "   Target: $(TARGET_DESC)"; \
	echo ""; \
	echo "   Changes will be applied immediately."; \
	echo "   Review changes with 'git diff' after running."; \
	echo ""; \
	echo "💡 Tip: Use DRY_RUN=1 to preview, or DIFF=1 to generate patch"; \
	echo "   Example: make lint-md-fix $(if $(FILE),FILE=$(FILE))$(if $(DIR),DIR=$(DIR)) DRY_RUN=1"; \
	echo ""; \
	read -p "Continue with fix? (yes/no): " confirm; \
	if [ "$$confirm" != "yes" ]; then \
		echo "❌ Operation cancelled"; \
		exit 1; \
	fi; \
	echo ""; \
	echo "🔧 Fixing markdown files: $(TARGET_DESC)..."; \
	docker run --rm \
		-v $(PWD):/workspace \
		-w /workspace \
		$(MARKDOWN_LINT_IMAGE) \
		$(MARKDOWN_LINT_CMD) --fix $(LINT_TARGET); \
	echo ""; \
	echo "✅ Auto-fix complete!"; \
	echo ""; \
	echo "📖 Next steps:"; \
	echo "   1. Review changes:  git diff"; \
	echo "   2. Verify linting:  make lint-md"; \
	echo "   3. Commit changes:  git add . && git commit -m 'docs: fix markdown linting'"; \
	echo "   4. Rollback if needed: git checkout -- ."
endef

# Convenience alias
md-check: lint-md

# ==============================================================================
# DOCUMENTATION
# ==============================================================================

docs-serve:
	@echo "📚 Starting MkDocs live preview..."
	@docker compose -f compose/docker-compose.dev.yml ps -q app > /dev/null 2>&1 || make dev-up
	@docker compose -f compose/docker-compose.dev.yml exec -d app sh -c "cd /app && uv run mkdocs serve --dev-addr=0.0.0.0:8001"
	@sleep 2
	@echo ""
	@echo "✅ MkDocs server started!"
	@echo "📖 Docs: http://localhost:8001/Dashtam/"
	@echo "🛑 Stop: make docs-stop"

docs-build:
	@echo "🏗️  Building documentation (strict mode)..."
	@docker compose -f compose/docker-compose.dev.yml ps -q app > /dev/null 2>&1 || make dev-up
	@docker compose -f compose/docker-compose.dev.yml exec app uv run mkdocs build --strict
	@echo "✅ Documentation built to site/"

docs-stop:
	@echo "🛑 Stopping MkDocs server..."
	@docker compose -f compose/docker-compose.dev.yml restart app
	@echo "✅ MkDocs stopped"

# ==============================================================================
# DATABASE MIGRATIONS
# ==============================================================================

migrate:
	@echo "📊 Applying migrations..."
	@docker compose -f compose/docker-compose.dev.yml ps -q app > /dev/null 2>&1 || make dev-up
	@docker compose -f compose/docker-compose.dev.yml exec app uv run alembic upgrade head
	@echo "✅ Migrations applied"

migrate-create:
	@echo "📝 Creating migration..."
	@docker compose -f compose/docker-compose.dev.yml ps -q app > /dev/null 2>&1 || make dev-up
	@if [ -z "$(MSG)" ]; then \
		echo "❌ Error: MSG parameter required"; \
		echo "Usage: make migrate-create MSG=\"your migration message\""; \
		exit 1; \
	fi
	@docker compose -f compose/docker-compose.dev.yml exec app uv run alembic revision --autogenerate -m "$(MSG)"
	@echo "✅ Migration created (review before applying!)"

migrate-down:
	@echo "⚠️  Rolling back last migration..."
	@docker compose -f compose/docker-compose.dev.yml ps -q app > /dev/null 2>&1 || make dev-up
	@read -p "Confirm rollback? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker compose -f compose/docker-compose.dev.yml exec app uv run alembic downgrade -1; \
		echo "✅ Migration rolled back"; \
	else \
		echo "❌ Cancelled"; \
	fi

migrate-history:
	@echo "📜 Migration history:"
	@docker compose -f compose/docker-compose.dev.yml ps -q app > /dev/null 2>&1 || make dev-up
	@docker compose -f compose/docker-compose.dev.yml exec app uv run alembic history --verbose

migrate-current:
	@echo "🔍 Current migration:"
	@docker compose -f compose/docker-compose.dev.yml ps -q app > /dev/null 2>&1 || make dev-up
	@docker compose -f compose/docker-compose.dev.yml exec app uv run alembic current --verbose

# ==============================================================================
# UTILITIES
# ==============================================================================

check:
	@echo "🔍 Checking setup..."
	@echo ""
	@echo "Docker:"
	@docker --version
	@docker compose version
	@echo ""
	@echo "Traefik:"
	@$(MAKE) _check-traefik-verbose
	@echo ""
	@echo "✅ All checks passed!"

status-all:
	@echo "=============== Development ==============="
	@docker compose -f compose/docker-compose.dev.yml ps 2>/dev/null || echo "Not running"
	@echo ""
	@echo "================== Test ==================="
	@docker compose -f compose/docker-compose.test.yml ps 2>/dev/null || echo "Not running"
	@echo ""
	@echo "================ Traefik =================="
	@docker ps --filter "name=traefik" --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || echo "Not running"

ps:
	@echo "📊 Dashtam Containers:"
	@docker ps -a --filter "name=dashtam" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

clean:
	@echo "⚠️  DESTRUCTIVE: This will DELETE all data!"
	@echo ""
	@read -p "Type 'DELETE ALL DATA' to confirm: " confirm; \
	if [ "$$confirm" != "DELETE ALL DATA" ]; then \
		echo "❌ Cancelled"; \
		exit 1; \
	fi
	@echo ""
	@echo "🧹 Cleaning all environments..."
	@docker compose -f compose/docker-compose.dev.yml down -v --remove-orphans 2>/dev/null || true
	@docker compose -f compose/docker-compose.test.yml down -v --remove-orphans 2>/dev/null || true
	@docker compose -f compose/docker-compose.ci.yml down -v --remove-orphans 2>/dev/null || true
	@echo "✅ Cleanup complete"

# ==============================================================================
# INTERNAL HELPERS
# ==============================================================================

# Check if Traefik is running
_check-traefik:
	@docker ps | grep -q traefik || { \
		echo "❌ Traefik not running!"; \
		echo ""; \
		echo "Start Traefik:"; \
		echo "  cd ~/docker-services/traefik && make up"; \
		echo ""; \
		exit 1; \
	}

# Check Traefik with verbose output
_check-traefik-verbose:
	@if docker ps | grep -q traefik; then \
		echo "✅ Traefik is running"; \
		docker ps --filter "name=traefik" --format "   {{.Names}}: {{.Status}}"; \
	else \
		echo "❌ Traefik not running"; \
		echo "   Start: cd ~/docker-services/traefik && make up"; \
	fi

# Ensure .env.dev exists (idempotent copy from example)
_ensure-env-dev:
	@if [ ! -f env/.env.dev ]; then \
		echo "📋 Creating env/.env.dev from example..."; \
		cp env/.env.dev.example env/.env.dev; \
		echo "✅ Created env/.env.dev"; \
		echo "⚠️  Update with your secrets before first run!"; \
	fi

# Ensure .env.test exists (idempotent copy from example)
_ensure-env-test:
	@if [ ! -f env/.env.test ]; then \
		echo "📋 Creating env/.env.test from example..."; \
		cp env/.env.test.example env/.env.test; \
		echo "✅ Created env/.env.test"; \
	fi

# Ensure .env.ci exists (idempotent copy from example)
_ensure-env-ci:
	@if [ ! -f env/.env.ci ]; then \
		echo "📋 Creating env/.env.ci from example..."; \
		cp env/.env.ci.example env/.env.ci; \
		echo "✅ Created env/.env.ci"; \
	fi
