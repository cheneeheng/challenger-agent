.PHONY: dev backend frontend test

dev:
	cd backend && uv run uvicorn app.main:app --reload & \
	cd frontend && bun run dev

backend:
	cd backend && uv run uvicorn app.main:app --reload

frontend:
	cd frontend && bun run dev

test:
	cd backend && uv run pytest -q
