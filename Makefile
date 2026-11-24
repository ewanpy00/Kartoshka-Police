.DEFAULT_GOAL := help
.PHONY: help up up-stretch down logs ps migrate seed reset test eval

help: ## Show this help
	@awk -F ':.*## ' '/^[a-z-]+:.*## /{printf "  make %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Build and start the stack
	./scripts/up.sh

up-stretch: ## Start the stack plus AdGuard Home
	./scripts/up.sh stretch

down: ## Stop the stack
	./scripts/down.sh

logs: ## Follow logs (make logs s=core for one service)
	./scripts/logs.sh $(s)

ps: ## Show service status
	./scripts/ps.sh

migrate: ## Apply database migrations
	./scripts/migrate.sh

seed: ## Re-run the data seed
	./scripts/seed.sh

reset: ## Delete all containers and volumes (asks first)
	./scripts/reset.sh

test: ## Run every test suite
	./scripts/test.sh

eval: ## Run the evaluation on data/eval/sample.csv
	./scripts/eval.sh
