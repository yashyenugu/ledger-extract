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

test:
	cd api && uv run pytest
