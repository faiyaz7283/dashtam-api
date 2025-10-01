.PHONY: help build up down logs clean status shell db-shell redis-cli restart dev prod certs keys setup test test-setup test-clean test-coverage test-file lint format

# Default target - show help
help:
	@echo "🎯 Dashtam - Financial Data Aggregation Platform"
	@echo ""
	@echo "Available commands:"
	@echo ""
	@echo "📦 Docker Commands:"
	@echo "  make up         - Start all services (builds if needed)"
	@echo "  make down       - Stop all services"
	@echo "  make build      - Build/rebuild Docker images"
	@echo "  make restart    - Restart all services"
	@echo "  make logs       - Show application logs"
	@echo "  make status     - Show service status"
	@echo "  make clean      - Clean up everything (containers, volumes, images)"
	@echo ""
	@echo "🔧 Development Commands:"
	@echo "  make dev        - Start in development mode with hot reload"
	@echo "  make prod       - Start in production mode"
	@echo "  make shell      - Open shell in app container"
	@echo "  make db-shell   - Open PostgreSQL shell"
	@echo "  make redis-cli  - Open Redis CLI"
	@echo "  make certs      - Generate SSL certificates"
	@echo "  make keys       - Generate secure application keys"
	@echo "  make setup      - Initial setup (certs, keys)"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  make test           - Run all tests with coverage"
	@echo "  make test-coverage  - Run tests with HTML coverage report"
	@echo "  make test-file      - Run a specific test file"
	@echo "  make test-PATTERN   - Run tests matching pattern"
	@echo "  make test-setup     - Setup test environment (databases, etc.)"
	@echo "  make test-clean     - Clean test environment"
	@echo ""
	@echo "✨ Code Quality:"
	@echo "  make lint           - Run linters"
	@echo "  make format         - Format code"
	@echo ""
	@echo "🔐 Provider Auth:"
	@echo "  make auth-schwab - Start Schwab OAuth flow"

# Start all services
up:
	@echo "🚀 Starting services..."
	@docker-compose up -d
	@echo "✅ Services started!"
	@echo ""
	@echo "📡 Main App:  https://localhost:8000"
	@echo "📡 Callback:  https://127.0.0.1:8182"
	@echo "🐘 PostgreSQL: localhost:5432"
	@echo "🔴 Redis:      localhost:6379"
	@echo ""
	@echo "📋 View logs: make logs"

# Stop all services
down:
	@echo "🛑 Stopping services..."
	@docker-compose down

# Build Docker images
build:
	@echo "🏗️  Building Docker images..."
	@docker-compose build

# Start in development mode
dev:
	@echo "🔧 Starting in development mode with hot reload..."
	@docker-compose up

# Start in production mode
prod:
	@echo "🚀 Starting in production mode..."
	@docker-compose -f docker-compose.yml up -d

# Show logs
logs:
	@docker-compose logs -f

# Show specific service logs
logs-%:
	@docker-compose logs -f $*

# Show service status
status:
	@docker-compose ps

# Clean up everything
clean:
	@echo "🧹 Cleaning up..."
	@docker-compose down -v --remove-orphans
	@docker rmi dashtam-app dashtam-callback 2>/dev/null || true
	@rm -rf certs/*.pem 2>/dev/null || true
	@echo "✅ Cleanup complete!"

# Restart services
restart: down up

# Open shell in app container
shell:
	@docker-compose exec app /bin/bash

# Open PostgreSQL shell
db-shell:
	@docker-compose exec postgres psql -U dashtam_user -d dashtam

# Open Redis CLI
redis-cli:
	@docker-compose exec redis redis-cli

# Generate SSL certificates
certs:
	@echo "🔐 Generating SSL certificates..."
	@bash scripts/generate-certs.sh

# Generate secure keys
keys:
	@echo "🔑 Generating secure application keys..."
	@bash scripts/generate-keys.sh

# Initial setup - run this first!
setup: certs keys
	@echo ""
	@echo "🎯 Initial setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Add your Schwab OAuth credentials to .env"
	@echo "  2. Run: make build"
	@echo "  3. Run: make up"
	@echo ""
	@echo "Your services will be available at:"
	@echo "  • Main App: https://localhost:8000"
	@echo "  • Callback: https://127.0.0.1:8182"

# Setup test environment
test-setup:
	@echo "🔧 Setting up test environment..."
	@echo "📦 Starting PostgreSQL with test configuration..."
	@docker-compose --env-file .env.test -f docker-compose.yml -f docker-compose.test.yml up -d postgres redis
	@echo "⏳ Waiting for PostgreSQL to be healthy..."
	@sleep 8
	@docker-compose --env-file .env.test -f docker-compose.yml -f docker-compose.test.yml exec postgres pg_isready -U dashtam_test_user || true
	@echo "📦 Starting app container with test environment..."
	@docker-compose --env-file .env.test -f docker-compose.yml -f docker-compose.test.yml up -d app
	@sleep 3
	@echo "🚀 Initializing test database schema..."
	@docker-compose --env-file .env.test -f docker-compose.yml -f docker-compose.test.yml exec -T app uv run python src/core/init_test_db.py
	@echo "✅ Test environment ready!"

# Run tests
test: test-setup
	@echo "🧪 Running tests..."
	@docker-compose --env-file .env.test -f docker-compose.yml -f docker-compose.test.yml exec -T app uv run pytest tests/ -v --cov=src --cov-report=term-missing

# Run unit tests only
test-unit: test-setup
	@echo "🧪 Running unit tests..."
	@docker-compose --env-file .env.test -f docker-compose.yml -f docker-compose.test.yml exec -T app uv run pytest tests/unit/ -v

# Run integration tests only
test-integration: test-setup
	@echo "🧪 Running integration tests..."
	@docker-compose --env-file .env.test -f docker-compose.yml -f docker-compose.test.yml exec -T app uv run pytest tests/integration/ -v

# Quick verification of core functionality
test-verify:
	@echo "🔍 Verifying core functionality..."
	@docker-compose exec app uv run python -c "from src.services.encryption import get_encryption_service; from src.core.config import get_settings; from src.core.database import get_engine; print('✅ Core services verified')"

# Run tests with specific pattern
test-%: test-setup
	@echo "🧪 Running tests matching: $*"
	@docker-compose --env-file .env.test -f docker-compose.yml -f docker-compose.test.yml exec -T app uv run pytest tests/ -v -k "$*"

# Run tests with coverage report
test-coverage: test-setup
	@echo "📊 Running tests with coverage..."
	@docker-compose --env-file .env.test -f docker-compose.yml -f docker-compose.test.yml exec -T app uv run pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
	@echo "📋 Coverage report generated in htmlcov/index.html"

# Run specific test file
test-file: test-setup
	@echo "🧪 Running specific test file..."
	@read -p "Enter test file path (e.g., tests/unit/test_encryption.py): " file; \
	docker-compose --env-file .env.test -f docker-compose.yml -f docker-compose.test.yml exec -T app uv run pytest "$$file" -v

# Clean test environment
test-clean:
	@echo "🧺 Cleaning test environment..."
	@docker-compose --env-file .env.test -f docker-compose.yml -f docker-compose.test.yml down -v
	@echo "✅ Test environment cleaned!"

# Run linters
lint:
	@echo "🔍 Running linters..."
	@docker-compose exec app uv run ruff check src/ tests/

# Format code
format:
	@echo "✨ Formatting code..."
	@docker-compose exec app uv run ruff format src/ tests/
	@docker-compose exec app uv run ruff check --fix src/ tests/

# Database migrations
migrate:
	@echo "📊 Running database migrations..."
	@docker-compose exec app uv run alembic upgrade head

# Create new migration
migration:
	@echo "📝 Creating new migration..."
	@read -p "Enter migration message: " msg; \
	docker-compose exec app uv run alembic revision --autogenerate -m "$$msg"

# Start Schwab OAuth flow
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
	@docker-compose --version
	@echo ""
	@echo "✅ Docker setup looks good!"