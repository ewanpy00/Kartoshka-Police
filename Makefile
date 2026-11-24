.DEFAULT_GOAL := help
.PHONY: help up up-stretch down logs ps migrate seed reset test eval refs retrain apk android

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

eval: ## Run the evaluation on data/eval/test.csv and holdout.csv
	./scripts/eval.sh

refs: ## Capture the brands' official pages and store their visual hashes (needs internet)
	docker compose exec -T worker python -m app.deep.visual refs

retrain: ## Retrain the URL model with officer decisions added as labels (A7)
	docker compose exec -T core python -m app.ai.url_model retrain /srv/data/train/phish.txt /srv/data/train/benign.txt

apk: ## Build the Gatekeeper debug APK in Docker (make apk host=<laptop IP> for Wi-Fi)
	./scripts/apk.sh $(host)

android: ## Build Gatekeeper natively and run it on the Android emulator (needs Android Studio's SDK)
	./scripts/android.sh run
