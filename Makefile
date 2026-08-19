.DEFAULT_GOAL := help

# Everything runs inside Docker. `run --rm web` spins up a throwaway
# container (starting postgres via depends_on) for one-off commands.
DC := docker compose
RUN := $(DC) run --rm web
MANAGE := $(RUN) python manage.py

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
.PHONY: env
env: ## Create .env from .env.example if it does not exist
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

# ---------------------------------------------------------------------------
# Docker lifecycle
# ---------------------------------------------------------------------------
.PHONY: up
up: ## Build and start the full stack (web + postgres)
	$(DC) up --build

.PHONY: up-d
up-d: ## Start the full stack in the background
	$(DC) up --build -d

.PHONY: down
down: ## Stop and remove all containers
	$(DC) down

.PHONY: down-volumes
down-volumes: ## Stop containers and remove volumes (DESTROYS DB DATA)
	$(DC) down -v

.PHONY: build
build: ## Build the web image
	$(DC) build

.PHONY: db-up
db-up: ## Start only PostgreSQL in Docker
	$(DC) up -d postgres

.PHONY: db-down
db-down: ## Stop the PostgreSQL container
	$(DC) stop postgres

.PHONY: logs
logs: ## Tail Docker logs
	$(DC) logs -f

.PHONY: web-logs
web-logs: ## Tail the web (Django) container logs
	$(DC) logs -f web

# ---------------------------------------------------------------------------
# Django (executed inside the web container)
# ---------------------------------------------------------------------------
.PHONY: migrations
migrations: ## Create new database migrations
	$(MANAGE) makemigrations

.PHONY: migrate
migrate: ## Apply database migrations
	$(MANAGE) migrate

.PHONY: superuser
superuser: ## Create a superuser (Platform Admin)
	$(MANAGE) createsuperuser

.PHONY: check
check: ## Run Django system checks
	$(MANAGE) check

.PHONY: check-migrations
check-migrations: ## Fail if there are missing migrations
	$(MANAGE) makemigrations --check --dry-run

.PHONY: shell
shell: ## Open the Django shell
	$(MANAGE) shell

.PHONY: collectstatic
collectstatic: ## Collect static files
	$(MANAGE) collectstatic --noinput

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------
.PHONY: test
test: ## Run the test suite (verbose)
	$(MANAGE) test --verbosity=2 $(ARGS)

.PHONY: lint
lint: ## Run flake8
	$(RUN) flake8 .

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
.PHONY: clean
clean: ## Remove Python caches
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.py[co]" -delete
