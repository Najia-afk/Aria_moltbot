# Makefile — Aria development shortcuts
# Usage: make test | make test-quick | make test-integration | make build | make up

COMPOSE = docker compose -f stacks/brain/docker-compose.yml
API_CONTAINER = aria-api

# ============================================================================
# Testing
# ============================================================================

.PHONY: test test-quick test-integration test-arch

test: ## Run all tests inside Docker
	$(COMPOSE) exec $(API_CONTAINER) pytest tests/ -v --tb=short

test-quick: ## Run unit + arch tests only (no network)
	pytest tests/test_architecture.py tests/test_imports.py -v --tb=short

test-integration: ## Run live integration tests (requires running stack)
	pytest tests/ -v --tb=short -m integration

test-arch: ## Run architecture compliance tests
	pytest tests/test_architecture.py -v --tb=short

test-coverage: ## Run tests with coverage report
	$(COMPOSE) exec $(API_CONTAINER) pytest tests/ --cov=src/api --cov-report=term-missing

# ============================================================================
# Docker
# ============================================================================

.PHONY: build up down logs restart

build: ## Build all containers
	$(COMPOSE) build

up: ## Start all services
	$(COMPOSE) up -d

down: ## Stop all services
	$(COMPOSE) down

logs: ## Tail logs
	$(COMPOSE) logs -f --tail=50

restart: ## Restart API container
	$(COMPOSE) restart $(API_CONTAINER)

# ============================================================================
# Development
# ============================================================================

.PHONY: lint format check

lint: ## Run linting
	ruff check aria_skills/ aria_agents/ aria_models/ src/

format: ## Auto-format code
	ruff format aria_skills/ aria_agents/ aria_models/ src/

check: lint test-quick ## Lint + quick tests

# ============================================================================
# Help
# ============================================================================

.DEFAULT_GOAL := help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
