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

.PHONY: up rebuild down config test check certs prod-check prod-up prod-build prod-down

check:
	uv run --no-project python setup.py check dev

certs:
	uv run --no-project python setup.py certs

prod-check:
	uv run --no-project python setup.py check prod

prod-up:
	uv run --no-project python setup.py check prod
	docker compose -f docker-compose-prod.yml up -d --remove-orphans

prod-build:
	docker compose -f docker-compose-prod.yml build --no-cache --pull
	docker compose -f docker-compose-prod.yml run --rm -T api uv run --no-sync alembic upgrade head

prod-down:
	docker compose -f docker-compose-prod.yml down
