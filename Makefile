up:
	docker compose -f docker-compose.yml up -d
rebuild:
	docker compose -f docker-compose.yml up --build -d
down:
	docker compose -f docker-compose.yml down
config:
	docker compose -f docker-compose.yml config

	