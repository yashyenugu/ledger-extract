.PHONY: up down migrate logs fmt test

up:
	docker compose up --build

down:
	docker compose down

migrate:
	docker compose exec api uv run alembic upgrade head

logs:
	docker compose logs -f

fmt:
	cd api && uv run ruff format .
	cd web && npm run lint -- --fix

HOST_TEST_ENV := DATABASE_URL=postgresql+psycopg://ledger:ledger@localhost:5433/ledger_extract \
	MINIO_ENDPOINT=localhost:9000 \
	MINIO_PUBLIC_ENDPOINT=localhost:9000 \
	MINIO_ROOT_USER=minioadmin \
	MINIO_ROOT_PASSWORD=minioadmin \
	MINIO_BUCKET=documents \
	MINIO_USE_SSL=false

test:
	docker compose up -d --wait postgres minio
	cd api && $(HOST_TEST_ENV) uv run alembic upgrade head
	cd api && $(HOST_TEST_ENV) uv run pytest
