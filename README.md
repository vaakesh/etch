# etch

etch is a web app for learning vocabulary with flashcards: build decks of word pairs, share them publicly, save other people's decks, and practice in typed-answer training sessions with progress and daily activity tracking.

live demo: https://168.113.158.206.nip.io/

## stack

- **api:** python 3.14, fastapi, pydantic, sqlalchemy (async) with asyncpg, alembic
- **data:** postgresql 18, redis for caching and rate limiting
- **background jobs:** celery with rabbitmq, transactional outbox for durable cache invalidation
- **auth:** rs256 jwt in httponly cookies, rotating refresh tokens, argon2, altcha proof-of-work captcha
- **observability:** opentelemetry traces and logs, prometheus, loki, tempo, grafana
- **tests:** pytest (unit and integration), vitest, playwright
- **frontend:** react, typescript, vite
- **infrastructure:** docker compose, caddy with automatic https, github actions ci/cd

## requirements

requires docker with compose, uv, make, and openssl. run commands from the repository root with docker running.

on a fresh ubuntu system, install the tools for local development:

```sh
sudo apt update
sudo apt install -y ca-certificates curl make openssl
curl --fail --silent --show-error --location https://get.docker.com -o /tmp/etch-docker-install.sh
sudo sh /tmp/etch-docker-install.sh
sudo systemctl enable --now docker
sudo usermod --append --groups docker "$(id -un)"
curl --fail --silent --show-error --location https://astral.sh/uv/install.sh | sh
```

if the uv installer fails, use pipx instead:

```sh
sudo apt install -y pipx
pipx install uv
pipx ensurepath
```

log out and back in to apply docker group membership and refresh your shell path, then check:

```sh
docker info
docker compose version
uv --version
```

installation details: [docker](https://docs.docker.com/engine/install/ubuntu/), [uv](https://docs.astral.sh/uv/getting-started/installation/), [pipx](https://pipx.pypa.io/latest/how-to/install-pipx.html).

## quick start

```sh
make dev-up
```

setup copies missing configs from templates and prompts to generate jwt keys. containers start and migrations run automatically. open http://localhost:5173 (default port).

the copied configs use example values. to replace them before the first launch, follow the manual setup below.

## manual setup

copy the configs on a fresh checkout:

```sh
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
cp redis/users.acl.example redis/users.acl
cp prometheus/metrics_token.example prometheus/metrics_token
chmod 600 .env backend/.env frontend/.env
```

edit all three `.env` files: replace example credentials and secrets, and adjust ports and urls as needed. keep these values consistent:

- database name, user, and password in `.env` and `backend/.env`.
- redis passwords in `redis/users.acl`; the admin password must match `redis_password` in `backend/.env`.
- rabbitmq user and password in `.env` and in `celery_broker_url` in `backend/.env`.
- `metrics_token` in `backend/.env` and the contents of `prometheus/metrics_token`.

also set your own `refresh_pepper` and `altcha_hmac_key` in `backend/.env`, and `grafana_admin_password` in `.env`. a random value can be generated with `openssl rand -hex 32`.

generate jwt keys and start:

```sh
make certs
make dev-up
```

## tests

```sh
make test-api
```

starts the separate test stack, applies migrations, and runs backend tests with file progress and no test logs. uses `backend/.env.test`; keep the test database name `etch_test_integration`.

frontend and e2e tests run on the host and need node 24 with installed packages and playwright browsers:

```sh
npm --prefix frontend ci
npm --prefix frontend exec playwright install -- --with-deps chromium firefox webkit
make test-frontend  # format, typecheck, lint, unit tests, build
make test-e2e       # playwright: mocked, visual, and integration on the test stack
make test-all       # frontend, e2e, and backend tests
```

## kubernetes

manifests live in `k8s/`, scripts in `scripts/k8s/`; pod counts per mode are in `k8s/overlays/*/scale.yaml`.

local development runs on a three-node [kind](https://kind.sigs.k8s.io/) cluster (needs kind, kubectl, helm; ports 80 and 443 free), served at https://localhost:

```sh
make k8s-kind-up      # create the cluster, install add-ons, build and deploy
make k8s-kind-deploy  # rebuild and redeploy
make k8s-kind-down    # delete the cluster
```

production runs on single-node [k3s](https://docs.k3s.io/), with all commands run on the server from its own checkout and env files. install k3s and set up the `etch-prod` kubectl context as described at the top of `k8s/k3s-config.yaml`, then:

```sh
make k8s-prod-addons K8S_CONTEXT=etch-prod  # once: gateway api, traefik, cert-manager
make k8s-prod-deploy K8S_CONTEXT=etch-prod IMAGE_TAG=$(git rev-parse HEAD)
```

grafana: `kubectl -n etch port-forward svc/grafana 3000` (on the server, through `ssh -L 3000:127.0.0.1:3000`).

## other commands

```sh
make dev-rebuild  # rebuild and start development containers
make dev-down     # stop development containers
make test-down    # stop the test stack and remove its volumes
```
