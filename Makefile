.PHONY: help dev-up dev-down dev-build dev-rebuild dev-logs dev-shell dev-db-shell dev-redis-cli dev-restart dev-status test-up test-down test-build test-rebuild test-restart test-status test-logs test-shell test-db-shell test-redis-cli test test-unit test-integration test-coverage test-file test-clean ci-test ci-build ci-clean lint format migrate migration certs keys setup clean auth-schwab check ps status-all git-status git-sync git-feature git-fix git-finish git-pr git-release-start git-release-finish git-hotfix-start git-hotfix-finish git-cleanup git-branch-protection

# Default target - show help
help:
	@echo "🎯 Dashtam - Financial Data Aggregation Platform"
	@echo ""
	@echo "Available commands:"
	@echo ""
	@echo "🚀 Development Environment (port 8000):"
	@echo "  make dev-up         - Start development environment"
	@echo "  make dev-down       - Stop development environment"
	@echo "  make dev-build      - Build development images"
	@echo "  make dev-rebuild    - Rebuild from scratch (no cache)"
	@echo "  make dev-logs       - Show development logs"
	@echo "  make dev-shell      - Shell in dev app container"
	@echo "  make dev-db-shell   - PostgreSQL shell (dev)"
	@echo "  make dev-redis-cli  - Redis CLI (dev)"
	@echo "  make dev-restart    - Restart development environment"
	@echo "  make dev-status     - Show development service status"
	@echo ""
	@echo "🧪 Test Environment (port 8001):"
	@echo "  make test-up        - Start test environment"
	@echo "  make test-down      - Stop test environment"
	@echo "  make test-build     - Build test images"
	@echo "  make test-rebuild   - Rebuild from scratch (no cache)"
	@echo "  make test-restart   - Restart test environment"
	@echo "  make test-status    - Show test service status"
	@echo "  make test-logs      - Show test logs"
	@echo "  make test-shell     - Shell in test app container"
	@echo "  make test-db-shell  - PostgreSQL shell (test)"
	@echo "  make test-redis-cli - Redis CLI (test)"
	@echo ""
	@echo "🔐 Provider Auth (uses dev environment):"
	@echo "  make auth-schwab    - Start Schwab OAuth flow"
	@echo "🔬 Testing Commands:"
	@echo "  make test           - Run all tests with coverage"
	@echo "  make test-unit      - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-coverage  - Run tests with HTML coverage report"
	@echo "  make test-file      - Run a specific test file"
	@echo "  make test-clean     - Clean test environment"
	@echo ""
	@echo "🤖 CI/CD Commands:"
	@echo "  make ci-test        - Run CI test suite (like GitHub Actions)"
	@echo "  make ci-build       - Build CI images"
	@echo "  make ci-clean       - Clean CI environment"
	@echo ""
	@echo "✨ Code Quality (uses dev environment):"
	@echo "  make lint           - Run linters"
	@echo "  make format         - Format code"
	@echo ""
	@echo "📦 Database (uses dev environment):"
	@echo "  make migrate        - Run database migrations"
	@echo "  make migration      - Create new migration"
	@echo ""
	@echo "🔧 Setup & Global Utilities:"
	@echo "  make setup          - Initial setup (certs, keys)"
	@echo "  make certs          - Generate SSL certificates"
	@echo "  make keys           - Generate secure application keys"
	@echo "  make clean          - Clean ALL environments"
	@echo "  make status-all     - Show status of all environments"
	@echo "  make ps             - Show all Dashtam containers"
	@echo ""
	@echo "🔐 Provider Auth:"
	@echo "  make auth-schwab - Start Schwab OAuth flow"
	@echo ""
	@echo "🌳 Git Flow Commands:"
	@echo "  make git-status          - Show current Git status"
	@echo "  make git-sync            - Sync with remote development branch"
	@echo "  make git-feature         - Create new feature branch"
	@echo "  make git-fix             - Create new fix branch"
	@echo "  make git-finish          - Finish current branch (push & create PR)"
	@echo "  make git-pr              - Create pull request with template"
	@echo "  make git-release-start   - Start new release"
	@echo "  make git-release-finish  - Finish release"
	@echo "  make git-hotfix-start    - Start emergency hotfix"
	@echo "  make git-hotfix-finish   - Finish hotfix"
	@echo "  make git-cleanup         - Clean up merged branches"
	@echo "  make git-branch-protection - Set up branch protection"

# ============================================================================
# DEVELOPMENT ENVIRONMENT COMMANDS
# ============================================================================

# Start development environment
dev-up:
	@echo "🚀 Starting DEVELOPMENT environment..."
	@docker compose -f docker-compose.dev.yml --env-file .env.dev up -d
	@echo "✅ Development services started!"
	@echo ""
	@echo "📡 Main App:  https://localhost:8000"
	@echo "📡 API Docs:  https://localhost:8000/docs"
	@echo "📡 Callback:  https://127.0.0.1:8182"
	@echo "🐘 PostgreSQL: localhost:5432"
	@echo "🔴 Redis:      localhost:6379"
	@echo ""
	@echo "📋 View logs: make dev-logs"
	@echo "🐚 Open shell: make dev-shell"

# Stop development environment
dev-down:
	@echo "🛑 Stopping DEVELOPMENT environment..."
	@docker compose -f docker-compose.dev.yml down
	@echo "✅ Development environment stopped"

# Build development images
dev-build:
	@echo "🏗️  Building DEVELOPMENT images..."
	@docker compose -f docker-compose.dev.yml --env-file .env.dev build
	@echo "✅ Development images built"

# Rebuild development images from scratch (no cache)
dev-rebuild:
	@echo "🔄 Rebuilding DEVELOPMENT images from scratch..."
	@echo "  → Removing problematic .env directory (if exists)..."
	@if [ -d ".env" ]; then rm -rf .env && echo "    ✓ Removed .env directory"; fi
	@echo "  → Stopping containers..."
	@docker compose -f docker-compose.dev.yml down 2>/dev/null || true
	@echo "  → Removing old images..."
	@docker rmi dashtam-dev-app dashtam-dev-callback dashtam-app dashtam-callback 2>/dev/null || true
	@echo "  → Building with --no-cache..."
	@docker compose -f docker-compose.dev.yml --env-file .env.dev build --no-cache
	@echo "✅ Development images rebuilt from scratch"

# Show development logs (follow mode)
dev-logs:
	@docker compose -f docker-compose.dev.yml logs -f

# Show specific dev service logs
dev-logs-%:
	@docker compose -f docker-compose.dev.yml logs -f $*

# Restart development environment
dev-restart: dev-down dev-up

# Show development service status
dev-status:
	@echo "📊 Development Environment Status:"
	@docker compose -f docker-compose.dev.yml ps

# Open shell in dev app container
dev-shell:
	@docker compose -f docker-compose.dev.yml exec app /bin/bash

# Open PostgreSQL shell (dev)
dev-db-shell:
	@docker compose -f docker-compose.dev.yml exec postgres psql -U dashtam_user -d dashtam

# Open Redis CLI (dev)
dev-redis-cli:
	@docker compose -f docker-compose.dev.yml exec redis redis-cli

# ============================================================================
# TEST ENVIRONMENT COMMANDS
# ============================================================================

# Start test environment
test-up:
	@echo "🧪 Starting TEST environment..."
	@docker compose -f docker-compose.test.yml --env-file .env.test up -d
	@echo "⏳ Waiting for services to be healthy..."
	@sleep 5
	@echo "✅ Test services started!"
	@echo ""
	@echo "📡 Test App:  http://localhost:8001"
	@echo "📡 Callback:  http://127.0.0.1:8183"
	@echo "🐘 PostgreSQL: localhost:5433"
	@echo "🔴 Redis:      localhost:6380"
	@echo ""
	@echo "🚀 Initializing test database..."
	@docker compose -f docker-compose.test.yml exec -T app uv run python src/core/init_test_db.py
	@echo "✅ Test environment ready!"
	@echo ""
	@echo "🧪 Run tests: make test"
	@echo "🐚 Open shell: make test-shell"

# Stop test environment
test-down:
	@echo "🛑 Stopping TEST environment..."
	@docker compose -f docker-compose.test.yml down
	@echo "✅ Test environment stopped"

# Restart test environment
test-restart: test-down test-up

# Show test service status
test-status:
	@echo "📊 Test Environment Status:"
	@docker compose -f docker-compose.test.yml ps

# Build test images
test-build:
	@echo "🏗️  Building TEST images..."
	@docker compose -f docker-compose.test.yml --env-file .env.test build
	@echo "✅ Test images built"

# Rebuild test images from scratch (no cache)
test-rebuild:
	@echo "🔄 Rebuilding TEST images from scratch..."
	@echo "  → Removing problematic .env directory (if exists)..."
	@if [ -d ".env" ]; then rm -rf .env && echo "    ✓ Removed .env directory"; fi
	@echo "  → Stopping containers..."
	@docker compose -f docker-compose.test.yml down 2>/dev/null || true
	@echo "  → Removing old images..."
	@docker rmi dashtam-test-app dashtam-test-callback dashtam-app dashtam-callback 2>/dev/null || true
	@echo "  → Building with --no-cache..."
	@docker compose -f docker-compose.test.yml --env-file .env.test build --no-cache
	@echo "✅ Test images rebuilt from scratch"

# Show test logs (follow mode)
test-logs:
	@docker compose -f docker-compose.test.yml logs -f

# Show specific test service logs
test-logs-%:
	@docker compose -f docker-compose.test.yml logs -f $*

# Open shell in test app container
test-shell:
	@docker compose -f docker-compose.test.yml exec app /bin/bash

# Open PostgreSQL shell (test)
test-db-shell:
	@docker compose -f docker-compose.test.yml exec postgres psql -U dashtam_test_user -d dashtam_test

# Open Redis CLI (test)
test-redis-cli:
	@docker compose -f docker-compose.test.yml exec redis redis-cli

# ============================================================================
# Makefile for Dashtam - Financial Dashboard Aggregator
# ============================================================================

.DEFAULT_GOAL := help

# Include workflow commands (CI debugging and common sequences)
-include Makefile.workflows
certs:
	@echo "🔐 Generating SSL certificates..."
	@bash scripts/generate-certs.sh
	@echo "✅ SSL certificates generated in certs/"

# Generate secure keys
keys:
	@echo "🔑 Generating secure application keys..."
	@bash scripts/generate-keys.sh
	@echo "✅ Secure keys generated"

# Initial setup - run this first!
setup: certs keys
	@echo ""
	@echo "🎯 Initial setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy .env.dev.example to .env.dev (if not exists)"
	@echo "  2. Add your Schwab OAuth credentials to .env.dev"
	@echo "  3. Run: make dev-build"
	@echo "  4. Run: make dev-up"
	@echo ""
	@echo "Your services will be available at:"
	@echo "  • Main App: https://localhost:8000"
	@echo "  • API Docs: https://localhost:8000/docs"
	@echo "  • Callback: https://127.0.0.1:8182"

# Clean up everything (both dev and test)
clean:
	@echo "🧹 Cleaning up ALL environments..."
	@echo "  → Stopping and removing dev containers..."
	@docker compose -f docker-compose.dev.yml down -v --remove-orphans 2>/dev/null || true
	@echo "  → Stopping and removing test containers..."
	@docker compose -f docker-compose.test.yml down -v --remove-orphans 2>/dev/null || true
	@echo "  → Removing Docker images..."
	@docker rmi dashtam-dev-app dashtam-dev-callback 2>/dev/null || true
	@docker rmi dashtam-test-app dashtam-test-callback 2>/dev/null || true
	@docker rmi dashtam-app dashtam-callback 2>/dev/null || true
	@echo "  → Removing problematic .env directory (if exists)..."
	@if [ -d ".env" ]; then rm -rf .env && echo "    ✓ Removed .env directory"; fi
	@echo "  → Pruning Docker build cache..."
	@docker builder prune -f 2>/dev/null || true
	@echo "✅ Cleanup complete!"

# ============================================================================
# TESTING COMMANDS
# ============================================================================

# Run all tests with coverage (auto-starts test env if needed)
test:
	@echo "🧪 Running all tests with coverage..."
	@docker compose -f docker-compose.test.yml ps -q app > /dev/null 2>&1 || make test-up
	@docker compose -f docker-compose.test.yml exec -T app uv run pytest tests/ -v --cov=src --cov-report=term-missing

# Run unit tests only
test-unit:
	@echo "🧪 Running unit tests..."
	@docker compose -f docker-compose.test.yml ps -q app > /dev/null 2>&1 || make test-up
	@docker compose -f docker-compose.test.yml exec -T app uv run pytest tests/unit/ -v

# Run integration tests only
test-integration:
	@echo "🧪 Running integration tests..."
	@docker compose -f docker-compose.test.yml ps -q app > /dev/null 2>&1 || make test-up
	@docker compose -f docker-compose.test.yml exec -T app uv run pytest tests/integration/ -v

# Run tests with HTML coverage report
test-coverage:
	@echo "📊 Running tests with HTML coverage..."
	@docker compose -f docker-compose.test.yml ps -q app > /dev/null 2>&1 || make test-up
	@docker compose -f docker-compose.test.yml exec -T app uv run pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
	@echo "📋 Coverage report generated in htmlcov/index.html"

# Run specific test file
test-file:
	@echo "🧪 Running specific test file..."
	@docker compose -f docker-compose.test.yml ps -q app > /dev/null 2>&1 || make test-up
	@read -p "Enter test file path (e.g., tests/unit/test_encryption.py): " file; \
	docker compose -f docker-compose.test.yml exec -T app uv run pytest "$$file" -v

# Clean test environment (removes containers and ephemeral data)
test-clean:
	@echo "🧺 Cleaning test environment..."
	@docker compose -f docker-compose.test.yml down -v
	@echo "✅ Test environment cleaned!"

# ============================================================================
# CODE QUALITY COMMANDS
# ============================================================================

# Run linters (uses dev environment)
lint:
	@echo "🔍 Running linters..."
	@docker compose -f docker-compose.dev.yml exec app uv run ruff check src/ tests/

# Format code (uses dev environment)
format:
	@echo "✨ Formatting code..."
	@docker compose -f docker-compose.dev.yml exec app uv run ruff format src/ tests/
	@docker compose -f docker-compose.dev.yml exec app uv run ruff check --fix src/ tests/

# ============================================================================
# DATABASE COMMANDS
# ============================================================================

# Database migrations (uses dev environment)
migrate:
	@echo "📊 Running database migrations..."
	@docker compose -f docker-compose.dev.yml exec app uv run alembic upgrade head

# Create new migration (uses dev environment)
migration:
	@echo "📝 Creating new migration..."
	@read -p "Enter migration message: " msg; \
	docker compose -f docker-compose.dev.yml exec app uv run alembic revision --autogenerate -m "$$msg"

# ============================================================================
# PROVIDER AUTH & UTILITIES
# ============================================================================

# Start Schwab OAuth flow (uses dev environment)
auth-schwab:
	@echo "🔐 Starting Schwab OAuth flow..."
	@echo ""
	@curl -sk https://localhost:8000/api/v1/auth/schwab/authorize | python3 -m json.tool
	@echo ""
	@echo "✅ Visit the URL above to authorize with Schwab"
	@echo "📡 The callback will be captured on https://127.0.0.1:8182"

# Check Docker setup
check:
	@echo "🔍 Checking Docker setup..."
	@docker --version
	@docker compose --version
	@echo ""
	@echo "✅ Docker setup looks good!"

# ============================================================================
# CI/CD COMMANDS
# ============================================================================

# Run CI test suite (simulates GitHub Actions locally)
ci-test:
	@echo "🤖 Running CI test suite..."
	@if [ ! -f .env.ci ]; then cp .env.ci.example .env.ci; fi
	@docker compose -f docker-compose.ci.yml up --build --abort-on-container-exit --exit-code-from app
	@echo "✅ CI tests completed"

# Build CI images
ci-build:
	@echo "🏗️  Building CI images..."
	@docker compose -f docker-compose.ci.yml build
	@echo "✅ CI images built"

# Clean CI environment
ci-clean:
	@echo "🧹 Cleaning CI environment..."
	@docker compose -f docker-compose.ci.yml down -v --remove-orphans
	@docker rmi dashtam-ci-app 2>/dev/null || true
	@echo "✅ CI environment cleaned"

# ============================================================================
# UTILITIES
# ============================================================================

# Show all running containers (dev + test)
ps:
	@echo "📊 All Dashtam Containers:"
	@docker ps -a --filter "name=dashtam" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Global status for all environments
status-all:
	@echo "================ Development ================"
	@docker compose -f docker-compose.dev.yml ps || true
	@echo "\n==================== Test ==================="
	@docker compose -f docker-compose.test.yml ps || true
	@echo "\n================ Docker (all) ==============="
	@docker ps -a --filter "name=dashtam" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# ============================================================================
# GIT FLOW COMMANDS
# ============================================================================

# Show current Git status with helpful context
git-status:
	@echo "🌳 Git Status:"
	@echo ""
	@echo "Current branch:"
	@git branch --show-current
	@echo ""
	@echo "Branch status:"
	@git status -sb
	@echo ""
	@echo "Recent commits:"
	@git log --oneline --graph --decorate -5
	@echo ""
	@echo "Uncommitted changes:"
	@git status -s

# Sync with remote development branch
git-sync:
	@echo "🔄 Syncing with remote development branch..."
	@git fetch origin
	@current_branch=$$(git branch --show-current); \
	if [ "$$current_branch" = "development" ]; then \
		git pull origin development; \
		echo "✅ Development branch synced"; \
	else \
		git rebase origin/development; \
		echo "✅ Rebased $$current_branch on development"; \
	fi

# Create new feature branch
git-feature:
	@echo "🚀 Creating new feature branch..."
	@read -p "Enter feature name (e.g., account-api): " feature; \
	git checkout development && \
	git pull origin development && \
	git checkout -b feature/$$feature && \
	echo "" && \
	echo "✅ Created and switched to feature/$$feature" && \
	echo "" && \
	echo "Next steps:" && \
	echo "  1. Make your changes" && \
	echo "  2. Commit: git commit -m 'feat: description'" && \
	echo "  3. Run: make git-finish"

# Create new fix branch
git-fix:
	@echo "🐛 Creating new fix branch..."
	@read -p "Enter fix description (e.g., token-refresh-error): " fix; \
	git checkout development && \
	git pull origin development && \
	git checkout -b fix/$$fix && \
	echo "" && \
	echo "✅ Created and switched to fix/$$fix" && \
	echo "" && \
	echo "Next steps:" && \
	echo "  1. Fix the bug" && \
	echo "  2. Add tests" && \
	echo "  3. Commit: git commit -m 'fix: description'" && \
	echo "  4. Run: make git-finish"

# Finish current branch (push and show PR creation info)
git-finish:
	@echo "🏁 Finishing current branch..."
	@current_branch=$$(git branch --show-current); \
	if [ "$$current_branch" = "development" ] || [ "$$current_branch" = "main" ]; then \
		echo "❌ Cannot finish protected branch $$current_branch"; \
		exit 1; \
	fi; \
	echo "" && \
	echo "Running tests before push..." && \
	make test && \
	make lint && \
	echo "" && \
	echo "✅ All tests passed!" && \
	echo "" && \
	echo "Pushing $$current_branch to remote..." && \
	git push -u origin $$current_branch && \
	echo "" && \
	echo "✅ Branch pushed successfully!" && \
	echo "" && \
	echo "📝 Create Pull Request:" && \
	echo "   https://github.com/faiyaz7283/Dashtam/compare/development...$$current_branch" && \
	echo "" && \
	echo "Or use: make git-pr"

# Create pull request with template
git-pr:
	@echo "📝 Creating Pull Request..."
	@echo ""
	@current_branch=$$(git branch --show-current); \
	if [ "$$current_branch" = "development" ] || [ "$$current_branch" = "main" ]; then \
		echo "❌ Cannot create PR from protected branch $$current_branch"; \
		exit 1; \
	fi; \
	echo "Current branch: $$current_branch" && \
	echo "" && \
	read -p "PR Title (or press Enter for default): " title; \
	if [ -z "$$title" ]; then \
		if echo "$$current_branch" | grep -q "^feature/"; then \
			default_title="feat: $${current_branch#feature/}"; \
		elif echo "$$current_branch" | grep -q "^fix/"; then \
			default_title="fix: $${current_branch#fix/}"; \
		else \
			default_title="$${current_branch}"; \
		fi; \
		title="$$default_title"; \
	fi; \
	echo "" && \
	echo "PR Title: $$title" && \
	echo "" && \
	read -p "Base branch (default: development): " base; \
	if [ -z "$$base" ]; then \
		base="development"; \
	fi; \
	echo "" && \
	echo "Creating PR: $$current_branch → $$base" && \
	echo "" && \
	pr_body="Description:\nPlease describe your changes here.\n\nType of Change:\n- [ ] New feature\n- [ ] Bug fix\n- [ ] Breaking change\n- [ ] Documentation\n\nTesting:\n- [ ] Unit tests pass\n- [ ] Integration tests pass\n- [ ] All tests pass\n- [ ] Linting passes\n\nChecklist:\n- [ ] Code follows style guidelines\n- [ ] Self-review completed\n- [ ] Tests added/updated\n- [ ] All tests passing\n\nRelated Issues:\nCloses \#\n\nAdditional Notes:\n[Add notes here]"; \
	gh pr create --base "$$base" --head "$$current_branch" --title "$$title" --body "$$pr_body" && \
	echo "" && \
	echo "✅ Pull Request created successfully!" && \
	echo "" && \
	echo "Remember to:" && \
	echo "  1. Edit the PR description with details" && \
	echo "  2. Wait for CI checks to pass" && \
	echo "  3. Request reviews" && \
	echo "  4. Address any feedback"

# Start new release
git-release-start:
	@echo "🎉 Starting new release..."
	@read -p "Enter version (e.g., 1.2.0): " version; \
	git checkout development && \
	git pull origin development && \
	git checkout -b release/v$$version && \
	echo "" && \
	echo "✅ Created release/v$$version" && \
	echo "" && \
	echo "Next steps:" && \
	echo "  1. Update version in pyproject.toml" && \
	echo "  2. Update CHANGELOG.md" && \
	echo "  3. Commit: git commit -m 'chore: bump version to $$version'" && \
	echo "  4. Run final tests: make test" && \
	echo "  5. Push: git push -u origin release/v$$version" && \
	echo "  6. Create PR to main" && \
	echo "  7. After merge, run: make git-release-finish VERSION=$$version"

# Finish release (tag and merge back)
git-release-finish:
	@echo "🎊 Finishing release..."
	@if [ -z "$(VERSION)" ]; then \
		echo "❌ Error: VERSION is required"; \
		echo "Usage: make git-release-finish VERSION=1.2.0"; \
		exit 1; \
	fi
	@echo "Checking out main..." && \
	git checkout main && \
	git pull origin main && \
	echo "" && \
	echo "Creating tag v$(VERSION)..." && \
	git tag -a v$(VERSION) -m "Release version $(VERSION)" && \
	git push origin v$(VERSION) && \
	echo "" && \
	echo "Merging back to development..." && \
	git checkout development && \
	git pull origin development && \
	git merge --no-ff main && \
	git push origin development && \
	echo "" && \
	echo "Cleaning up release branch..." && \
	git branch -d release/v$(VERSION) && \
	git push origin --delete release/v$(VERSION) && \
	echo "" && \
	echo "✅ Release v$(VERSION) complete!" && \
	echo "" && \
	echo "🚀 Deploy to production now!"

# Start emergency hotfix
git-hotfix-start:
	@echo "🚨 Starting emergency hotfix..."
	@read -p "Enter patch version (e.g., 1.1.1): " version; \
	git checkout main && \
	git pull origin main && \
	git checkout -b hotfix/v$$version && \
	echo "" && \
	echo "✅ Created hotfix/v$$version" && \
	echo "" && \
	echo "⚠️  HOTFIX MODE - Fix critical issue ONLY" && \
	echo "" && \
	echo "Next steps:" && \
	echo "  1. Fix the critical issue" && \
	echo "  2. Add tests" && \
	echo "  3. Commit: git commit -m 'fix(critical): description'" && \
	echo "  4. Update version and CHANGELOG" && \
	echo "  5. Run tests: make test" && \
	echo "  6. Push: git push -u origin hotfix/v$$version" && \
	echo "  7. Create URGENT PR to main" && \
	echo "  8. After merge, run: make git-hotfix-finish VERSION=$$version"

# Finish hotfix (tag and merge to development)
git-hotfix-finish:
	@echo "🔥 Finishing hotfix..."
	@if [ -z "$(VERSION)" ]; then \
		echo "❌ Error: VERSION is required"; \
		echo "Usage: make git-hotfix-finish VERSION=1.1.1"; \
		exit 1; \
	fi
	@echo "Checking out main..." && \
	git checkout main && \
	git pull origin main && \
	echo "" && \
	echo "Creating tag v$(VERSION)..." && \
	git tag -a v$(VERSION) -m "Hotfix v$(VERSION)" && \
	git push origin v$(VERSION) && \
	echo "" && \
	echo "Merging to development..." && \
	git checkout development && \
	git pull origin development && \
	git merge --no-ff main && \
	git push origin development && \
	echo "" && \
	echo "Cleaning up hotfix branch..." && \
	git branch -d hotfix/v$(VERSION) && \
	git push origin --delete hotfix/v$(VERSION) && \
	echo "" && \
	echo "✅ Hotfix v$(VERSION) complete!" && \
	echo "" && \
	echo "🚀 Deploy to production IMMEDIATELY!"

# Clean up merged branches
git-cleanup:
	@echo "🧹 Cleaning up merged branches..."
	@echo "" && \
	echo "Fetching from remote..." && \
	git fetch --prune && \
	echo "" && \
	echo "Merged branches (will be deleted):" && \
	git branch --merged development | grep -v "\*\|main\|development" | grep -E "feature/|fix/" || echo "  (none)" && \
	echo "" && \
	read -p "Delete these branches? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		git branch --merged development | grep -v "\*\|main\|development" | grep -E "feature/|fix/" | xargs -r git branch -d; \
		echo "✅ Local branches cleaned"; \
	else \
		echo "❌ Cancelled"; \
	fi

# Set up branch protection (requires gh CLI)
git-branch-protection:
	@echo "🔒 Setting up branch protection..."
	@echo "" && \
	echo "This requires GitHub CLI (gh) to be installed and authenticated." && \
	echo "" && \
	read -p "Continue? (y/N): " confirm; \
	if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
		echo "❌ Cancelled"; \
		exit 0; \
	fi && \
	echo "" && \
	echo "Protecting main branch..." && \
	gh api repos/faiyaz7283/Dashtam/branches/main/protection \
		--method PUT \
		--field required_status_checks[strict]=true \
		--field 'required_status_checks[contexts][]=Test Suite / Run Tests' \
		--field 'required_status_checks[contexts][]=Code Quality / lint' \
		--field required_pull_request_reviews[required_approving_review_count]=1 \
		--field required_pull_request_reviews[dismiss_stale_reviews]=true \
		--field enforce_admins=true \
		--field restrictions=null && \
	echo "✅ Main branch protected" && \
	echo "" && \
	echo "Protecting development branch..." && \
	gh api repos/faiyaz7283/Dashtam/branches/development/protection \
		--method PUT \
		--field required_status_checks[strict]=true \
		--field 'required_status_checks[contexts][]=Test Suite / Run Tests' \
		--field 'required_status_checks[contexts][]=Code Quality / lint' \
		--field required_pull_request_reviews[required_approving_review_count]=1 \
		--field required_pull_request_reviews[dismiss_stale_reviews]=true \
		--field enforce_admins=false \
		--field restrictions=null && \
	echo "✅ Development branch protected" && \
	echo "" && \
	echo "✅ Branch protection configured!" && \
	echo "" && \
	echo "Protected branches:" && \
	echo "  • main - Tests + 1 approval required (admins enforced)" && \
	echo "  • development - Tests + 1 approval required"
