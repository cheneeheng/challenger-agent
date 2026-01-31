# challenger-agent

An interactive challenger agent designed to actively interrogate a user’s stated topic (decision, belief, assumption, or thought). The agent challenges the user through structured questioning while maintaining a parallel, structured reasoning record.

## Development

### Start backend

```
make backend
```

### Start frontend

```
make frontend
```

### Start both

```
make dev
```

## Repo Structure

- FastAPI backend
- SvelteKit frontend
- Docker + Devcontainers
- GitHub Actions CI
- Clean architecture
- Ready for production

```
my-project/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   └── example.py
│   │   │   └── deps.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── security.py
│   │   ├── services/
│   │   │   └── example_service.py
│   │   ├── models/
│   │   │   └── example.py
│   │   ├── schemas/
│   │   │   └── example.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── base.py
│   │   └── main.py
│   ├── tests/
│   ├── pyproject.toml
│   └── README.md
│
├── frontend/
│   ├── src/
│   │   ├── lib/
│   │   │   ├── api/
│   │   │   │   └── client.ts
│   │   │   ├── components/
│   │   │   └── stores/
│   │   ├── routes/
│   │   │   └── +page.svelte
│   │   └── app.d.ts
│   ├── static/
│   ├── package.json
│   └── README.md
│
├── infra/
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── README.md
│
├── .devcontainer/
│   ├── devcontainer.json
│   └── Dockerfile
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── Makefile
└── README.md
```
