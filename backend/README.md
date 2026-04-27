# Backend

FastAPI + Uvicorn, Python 3.12, managed with `uv`. See the root
[README](../README.md) for full development instructions, project structure,
and deployment guidance.

## Quick reference

```bash
uv sync                                        # install / sync dependencies
uv run uvicorn app.main:app --reload           # dev server on :8000
uv run pytest -q                               # run tests
uv run pytest --no-cov                         # run tests without coverage
uv run alembic upgrade head                    # apply migrations
uv run alembic revision --autogenerate -m "…"  # generate migration
ruff check .                                   # lint
ruff format .                                  # format
```

## Environment

Reads `../.env` (repo root) with `.env` in the current directory as a
fallback. See the root [README](../README.md#environment-variables) for the
full variable reference.
