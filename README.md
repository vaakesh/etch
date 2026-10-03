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
make up
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
chmod 600 .env backend/.env frontend/.env
```

edit all three `.env` files: replace example credentials and secrets, and adjust ports and urls as needed. keep database names, users, and passwords consistent between `.env` and `backend/.env`. update redis passwords in `redis/users.acl` and match the admin password to `backend/.env`.

generate jwt keys and start:

```sh
make certs
make up
```

## tests

```sh
make test
```

starts the separate test stack, applies migrations, and runs backend tests with file progress and no test logs. uses `backend/.env.test`; keep the test database name `etch_test_integration`.

## other commands

```sh
make rebuild  # rebuild and start development containers
make down     # stop development containers
```
