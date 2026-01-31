.PHONY: dev backend frontend test

dev:
    cd backend && uvicorn app.main:app --reload & \
    cd frontend && npm run dev

backend:
    cd backend && uvicorn app.main:app --reload

frontend:
    cd frontend && npm run dev

test:
    cd backend && pytest -q
