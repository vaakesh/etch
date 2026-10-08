DEV_COMPOSE := docker compose -f docker-compose-dev.yml -f docker-compose-otel.yml
TEST_COMPOSE := docker compose -f docker-compose-test.yml

.PHONY: dev-up dev-rebuild dev-down test-frontend test-e2e test-api test-all test-prepare test-down certs prod-deploy

dev-up:
	uv run --no-project python setup.py check dev
	$(DEV_COMPOSE) up -d
	$(DEV_COMPOSE) run --rm -T api uv run --no-sync alembic upgrade head

dev-rebuild:
	uv run --no-project python setup.py check dev
	$(DEV_COMPOSE) up --build -d
	$(DEV_COMPOSE) run --rm -T api uv run --no-sync alembic upgrade head

dev-down:
	$(DEV_COMPOSE) down

test-frontend:
	npm --prefix frontend run format:check
	npm --prefix frontend run typecheck
	npm --prefix frontend run lint
	npm --prefix frontend run test
	npm --prefix frontend run build

test-e2e:
	npm --prefix frontend run typecheck:e2e
	npm --prefix frontend run test:e2e:mocked
	npm --prefix frontend run test:e2e:visual
	$(MAKE) test-prepare
	$(TEST_COMPOSE) up -d --build --wait --wait-timeout 180 api frontend
	PLAYWRIGHT_INTEGRATION_BASE_URL=http://localhost:$$($(TEST_COMPOSE) port frontend 5173 | cut -d: -f2) \
		npm --prefix frontend run test:e2e:integration

test-api: test-prepare
	$(TEST_COMPOSE) run --rm -T --no-deps api uv run --no-sync pytest -o log_cli=false --show-capture=no

test-all:
	$(MAKE) test-frontend
	$(MAKE) test-e2e
	$(MAKE) test-api

test-prepare: test-down
	uv run --no-project python setup.py check test
	$(TEST_COMPOSE) build api
	$(TEST_COMPOSE) up -d --wait --wait-timeout 120 postgres redis
	$(TEST_COMPOSE) run --rm -T --no-deps api uv run --no-sync alembic upgrade head

test-down:
	$(TEST_COMPOSE) down --volumes --remove-orphans

certs:
	uv run --no-project python setup.py certs

prod-deploy:
	bash scripts/deploy-prod.sh
