.PHONY: dev install api web migrate test lint check down

dev:
	docker compose up --build
install:
	uv sync --frozen
	npm ci --prefix apps/web
api:
	uv run uvicorn apps.api.main:app --reload --host 127.0.0.1
web:
	npm run dev --prefix apps/web
migrate:
	uv run alembic upgrade head
test:
	uv run pytest -q
lint:
	uv run ruff check apps/api packages pipelines tests infra scripts
	uv run ruff format --check apps/api packages pipelines tests infra scripts
	uv run mypy
	npm run lint --prefix apps/web
	npm run typecheck --prefix apps/web
	npm run format:check --prefix apps/web
check: test lint
	npm run build --prefix apps/web
down:
	docker compose down
