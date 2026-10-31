RAG ?= 0
DEV_COMPOSE := docker compose -f docker-compose-dev.yml
OBS_COMPOSE := docker compose -f docker-compose-observability.yml
OBS_NETWORK := docker network inspect observability >/dev/null 2>&1 || docker network create observability

ifeq ($(RAG),1)
DEV_COMPOSE += -f docker-compose-rag.yml --env-file .env --env-file user-guide-rag/.env --profile rag
endif

TEST_COMPOSE := docker compose -f docker-compose-test.yml

.PHONY: dev-up dev-rebuild dev-down obs-up obs-down test-frontend test-e2e test-api test-setup test-all test-prepare test-down certs prod-deploy k8s-kind-up k8s-kind-deploy k8s-kind-down k8s-prod-addons k8s-prod-render k8s-prod-deploy

# телеметрия в dev включена, только если запущен локальный стек observability
dev-up dev-rebuild: export OTEL_SDK_DISABLED = $(if $(shell $(OBS_COMPOSE) ps -q --status running otel-collector 2>/dev/null),false,true)

dev-up:
	uv run --no-project python setup.py check dev
	$(OBS_NETWORK)
	$(DEV_COMPOSE) up -d
	$(DEV_COMPOSE) run --rm -T api uv run --no-sync alembic upgrade head

dev-rebuild:
	uv run --no-project python setup.py check dev
	$(OBS_NETWORK)
	$(DEV_COMPOSE) up --build -d
	$(DEV_COMPOSE) run --rm -T api uv run --no-sync alembic upgrade head

dev-down:
	$(DEV_COMPOSE) down

obs-up:
	uv run --no-project python setup.py check observability
	$(OBS_NETWORK)
	$(OBS_COMPOSE) up -d

obs-down:
	$(OBS_COMPOSE) down

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

test-setup:
	uv run --no-project python -m unittest tests.test_setup

test-all:
	$(MAKE) test-setup
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

# prod на общем сервере: системный caddy держит 80/443, etch слушает 127.0.0.1:caddy_proxy_port
prod-deploy:
	bash scripts/deploy-prod.sh

# kind: кластер из трех нод в контейнерах docker, для локальной разработки
k8s-kind-up:
	uv run --no-project python setup.py check dev
	bash scripts/k8s/kind-up.sh
	K8S_CONTEXT=kind-etch bash scripts/k8s/deploy.sh

k8s-kind-deploy:
	K8S_CONTEXT=kind-etch bash scripts/k8s/deploy.sh

k8s-kind-down:
	kind delete cluster --name etch

# prod: k3s на сервере, оверлей с let's encrypt и образами из ghcr.io; кластер задается при вызове:
# make k8s-prod-deploy K8S_CONTEXT=<контекст kubectl сервера>
# аддоны ставятся один раз на новый сервер и при смене их версий
k8s-prod-addons:
	bash scripts/k8s/addons.sh "$(K8S_CONTEXT)" k3s

k8s-prod-render:
	K8S_OVERLAY=prod bash scripts/k8s/deploy.sh render

k8s-prod-deploy:
	K8S_OVERLAY=prod bash scripts/k8s/deploy.sh
