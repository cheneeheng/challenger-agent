# Backend

FastAPI backend managed with `uv`. See the root [README](../README.md) for full
development instructions, project structure, and deployment guidance.

## Quick reference

```bash
uv sync --all-extras          # install / sync dependencies
uvicorn app.main:app --reload # dev server on :8000
pytest -q                     # run tests
pytest --cov                  # run tests with coverage
ruff check app/               # lint
ruff format app/              # format
```
