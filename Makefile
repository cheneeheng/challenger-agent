.PHONY: dev backend frontend test db db-stop db-migrate

# Start postgres (detached) then run backend + frontend in parallel.
dev: db
	cd backend && uv run uvicorn app.main:app --reload & \
	cd frontend && bun run dev

backend:
	cd backend && uv run uvicorn app.main:app --reload

frontend:
	cd frontend && bun run dev

# Start only the postgres container (detached, waits for healthy).
db:
	docker compose -f deploy/docker-compose.dev.yml up -d postgres --wait

# Stop the postgres container.
db-stop:
	docker compose -f deploy/docker-compose.dev.yml stop postgres

# Run Alembic migrations against the dev database.
db-migrate:
	cd backend && uv run alembic upgrade head

test:
	cd backend && uv run pytest -q
