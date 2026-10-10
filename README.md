# etch

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

## other commands

```sh
make dev-rebuild  # rebuild and start development containers
make dev-down     # stop development containers
make test-down    # stop the test stack and remove its volumes
```
