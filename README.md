# Etch

Etch is a web app for learning vocabulary with flashcards: build decks of word pairs, share them publicly, save other people's decks, and practice in typed-answer training sessions with progress and daily activity tracking.

Live demo: https://168.113.158.206.nip.io/

## Stack

- **API:** Python 3.14, FastAPI, Pydantic, SQLAlchemy (async) with asyncpg, Alembic
- **Data:** PostgreSQL 18, Redis for caching and rate limiting
- **Background jobs:** Celery with RabbitMQ, transactional outbox for durable cache invalidation
- **Auth:** RS256 JWT in HttpOnly cookies, rotating refresh tokens, Argon2, ALTCHA proof-of-work CAPTCHA
- **Observability:** OpenTelemetry traces and logs, Prometheus, Loki, Tempo, Grafana
- **Tests:** pytest (unit and integration), Vitest, Playwright
- **Frontend:** React, TypeScript, Vite
- **Infrastructure:** Docker Compose, Caddy with automatic HTTPS, GitHub Actions CI/CD

## Requirements

Requires Docker with Compose, uv, make, and OpenSSL. Run commands from the repository root with Docker running.

On a fresh Ubuntu system, install the tools for local development:

```sh
sudo apt update
sudo apt install -y ca-certificates curl make openssl
curl --fail --silent --show-error --location https://get.docker.com -o /tmp/etch-docker-install.sh
sudo sh /tmp/etch-docker-install.sh
sudo systemctl enable --now docker
sudo usermod --append --groups docker "$(id -un)"
curl --fail --silent --show-error --location https://astral.sh/uv/install.sh | sh
```

If the uv installer fails, use pipx instead:

```sh
sudo apt install -y pipx
pipx install uv
pipx ensurepath
```

Log out and back in to apply Docker group membership and refresh your shell path, then check:

```sh
docker info
docker compose version
uv --version
```

Installation details: [Docker](https://docs.docker.com/engine/install/ubuntu/), [uv](https://docs.astral.sh/uv/getting-started/installation/), [pipx](https://pipx.pypa.io/latest/how-to/install-pipx.html).

## Quick start

```sh
make dev-up
```

Setup copies missing configs from templates and prompts to generate JWT keys. Containers start and migrations run automatically. Open http://localhost:5173 (default port).

To include the optional RAG assistant, copy `user-guide-rag/.env.example` to
`user-guide-rag/.env`, set `LLM_API_KEY`, then run `make dev-up RAG=1`.
The same flag works with `make dev-rebuild RAG=1` and `make dev-down RAG=1`.
It adds `docker-compose-rag.yml` and enables the `rag` profile in the existing
Compose project. Plain `make dev-up` starts Etch without RAG and does not read
the RAG env file.

RAG is intentionally disabled in production to avoid spending the project owner's
LLM API tokens. The chat widget is still visible on desktop, but questions return
an assistant-unavailable message.

The copied configs use example values. To replace them before the first launch, follow the manual setup below.

## Manual setup

Copy the configs on a fresh checkout:

```sh
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
cp redis/users.acl.example redis/users.acl
cp prometheus/metrics_token.example prometheus/metrics_token
chmod 600 .env backend/.env frontend/.env
```

Edit all three `.env` files: replace example credentials and secrets, and adjust ports and URLs as needed. Keep these values consistent:

- Database name, user, and password in `.env` and `backend/.env`.
- Redis passwords in `redis/users.acl`; the admin password must match `redis_password` in `backend/.env`.
- RabbitMQ user and password in `.env` and in `celery_broker_url` in `backend/.env`.
- `metrics_token` in `backend/.env` and the contents of `prometheus/metrics_token`.

Also set your own `refresh_pepper` and `altcha_hmac_key` in `backend/.env`, and `grafana_admin_password` in `.env`. A random value can be generated with `openssl rand -hex 32`.

Generate JWT keys and start:

```sh
make certs
make dev-up
```

## Tests

```sh
make test-api
```

Starts the separate test stack, applies migrations, and runs backend tests with file progress and no test logs. Uses `backend/.env.test`; keep the test database name `etch_test_integration`.

Frontend and E2E tests run on the host and need Node 24 with installed packages and Playwright browsers:

```sh
npm --prefix frontend ci
npm --prefix frontend exec playwright install -- --with-deps chromium firefox webkit
make test-frontend  # Format, typecheck, lint, unit tests, build
make test-e2e       # Playwright: mocked, visual, and integration on the test stack
make test-all       # Frontend, E2E, and backend tests
```

## Kubernetes

Manifests live in `k8s/`, scripts in `scripts/k8s/`; pod counts per mode are in `k8s/overlays/*/scale.yaml`.

Local development runs on a three-node [kind](https://kind.sigs.k8s.io/) cluster (needs kind, kubectl, Helm; ports 80 and 443 free), served at https://localhost:

```sh
make k8s-kind-up      # Create the cluster, install add-ons, build and deploy
make k8s-kind-deploy  # Rebuild and redeploy
make k8s-kind-down    # Delete the cluster
```

Production runs on single-node [K3s](https://docs.k3s.io/), with all commands run on the server from its own checkout and env files. Install K3s and set up the `etch-prod` kubectl context as described at the top of `k8s/k3s-config.yaml`, then:

```sh
make k8s-prod-addons K8S_CONTEXT=etch-prod  # Once: Gateway API, Traefik, cert-manager
make k8s-prod-deploy K8S_CONTEXT=etch-prod IMAGE_TAG=$(git rev-parse HEAD)
```

Grafana: `kubectl -n etch port-forward svc/grafana 3000` (on the server, through `ssh -L 3000:127.0.0.1:3000`).

## Other commands

```sh
make dev-rebuild  # Rebuild and start development containers
make dev-down     # Stop development containers
make test-down    # Stop the test stack and remove its volumes
```
