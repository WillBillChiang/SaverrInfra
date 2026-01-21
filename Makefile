# Saverr API Makefile
# Usage: make [target] [ENV=dev|staging|prod]

ENV ?= dev
PORT ?= 3000

.PHONY: help build deploy deploy-dev deploy-staging deploy-prod delete logs local sync validate clean

help:
	@echo "Saverr API - Available Commands"
	@echo "================================"
	@echo ""
	@echo "Development:"
	@echo "  make build          Build the SAM application"
	@echo "  make local          Start local API server"
	@echo "  make sync           Start SAM sync (hot reload)"
	@echo "  make validate       Validate CloudFormation template"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy         Deploy to ENV (default: dev)"
	@echo "  make deploy-dev     Deploy to development"
	@echo "  make deploy-staging Deploy to staging"
	@echo "  make deploy-prod    Deploy to production"
	@echo ""
	@echo "Management:"
	@echo "  make outputs        Show stack outputs"
	@echo "  make logs FUNC=xxx  View Lambda logs"
	@echo "  make delete         Delete stack (use with caution!)"
	@echo "  make clean          Clean build artifacts"
	@echo ""
	@echo "Variables:"
	@echo "  ENV=dev|staging|prod  Target environment (default: dev)"
	@echo "  PORT=3000             Local server port (default: 3000)"
	@echo "  FUNC=login            Function name for logs"
	@echo ""
	@echo "Examples:"
	@echo "  make deploy ENV=staging"
	@echo "  make logs ENV=prod FUNC=login"
	@echo "  make local PORT=8080"

# Build
build:
	@echo "Building for $(ENV)..."
	sam build --config-env $(ENV)

# Validate template
validate:
	sam validate --lint

# Deploy commands
deploy: build
	@echo "Deploying to $(ENV)..."
	./deploy.sh $(ENV)

deploy-dev:
	./deploy.sh dev

deploy-staging:
	./deploy.sh staging

deploy-prod:
	./deploy.sh prod

# Local development
local: build
	@echo "Starting local API on port $(PORT)..."
	sam local start-api --port $(PORT) --warm-containers EAGER

# SAM Sync (hot reload)
sync: build
	@echo "Starting SAM sync for $(ENV)..."
	sam sync --config-env $(ENV) --watch

# View stack outputs
outputs:
	./scripts/get-outputs.sh $(ENV)

# View logs
logs:
ifndef FUNC
	@echo "Usage: make logs ENV=$(ENV) FUNC=<function-name>"
	@echo ""
	@./scripts/view-logs.sh $(ENV)
else
	./scripts/view-logs.sh $(ENV) $(FUNC)
endif

# Delete stack
delete:
	@echo "WARNING: This will delete the $(ENV) stack!"
	./scripts/delete-stack.sh $(ENV)

# Update Plaid credentials
update-plaid:
ifndef CLIENT_ID
	@echo "Usage: make update-plaid ENV=$(ENV) CLIENT_ID=xxx SECRET=xxx"
else ifndef SECRET
	@echo "Usage: make update-plaid ENV=$(ENV) CLIENT_ID=xxx SECRET=xxx"
else
	./scripts/update-plaid-secret.sh $(ENV) $(CLIENT_ID) $(SECRET)
endif

# Clean build artifacts
clean:
	rm -rf .aws-sam
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned build artifacts"

# Test locally with Docker
test-local:
	@echo "Running local tests..."
	sam local invoke LoginFunction --event events/login.json

# Install dependencies
install:
	pip install -r lambdas/requirements.txt
	pip install pytest pytest-cov moto boto3

# Run unit tests
test:
	pytest tests/ -v --cov=lambdas --cov-report=html
