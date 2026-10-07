up:
	uv run --no-project python setup.py check dev
	docker compose -f docker-compose-dev.yml -f docker-compose-otel.yml up -d
	docker compose -f docker-compose-dev.yml -f docker-compose-otel.yml run --rm -T api uv run --no-sync alembic upgrade head
rebuild:
	uv run --no-project python setup.py check dev
	docker compose -f docker-compose-dev.yml -f docker-compose-otel.yml up --build -d
	docker compose -f docker-compose-dev.yml -f docker-compose-otel.yml run --rm -T api uv run --no-sync alembic upgrade head
down:
	docker compose -f docker-compose-dev.yml -f docker-compose-otel.yml down

test:
	uv run --no-project python setup.py check test
	docker compose -f docker-compose-test.yml up --build -d
	docker compose -f docker-compose-test.yml run --rm -T api uv run --no-sync alembic upgrade head
	docker compose -f docker-compose-test.yml run --rm -T api uv run --no-sync pytest -o log_cli=false --show-capture=no

.PHONY: up rebuild down config test check certs prod-check prod-deploy prod-up prod-logs prod-ps prod-down

check:
	uv run --no-project python setup.py check dev

certs:
	uv run --no-project python setup.py certs

PROD_COMPOSE := docker compose -f docker-compose-prod.yml -f docker-compose-prod-observability.yml

prod-check:
	$(PROD_COMPOSE) config --quiet

prod-deploy: prod-check
	bash scripts/deploy-prod.sh

prod-up: prod-deploy

prod-logs:
	$(PROD_COMPOSE) logs -f --tail=100

prod-ps:
	$(PROD_COMPOSE) ps -a

prod-down:
	$(PROD_COMPOSE) down
