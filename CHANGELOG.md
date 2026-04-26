# Changelog

All notable changes to this template are documented here.

Format: `[version] YYYY-MM-DD — description`

---

## [0.3.6] 2026-04-26 — E2E test suite, graph context menu, node animations, dashboard polish

### Added
- **`frontend/playwright.config.ts`** — Playwright configuration targeting Chromium with `baseURL http://localhost:5173` and a `webServer` block that starts `bun run dev` automatically before the test run.
- **`frontend/e2e/helpers.ts`** — Shared E2E utilities: `buildSSEBody()` for constructing streaming request payloads and `registerUser()` for creating a test account in setup/teardown.
- **`frontend/e2e/auth.spec.ts`** — 4 Playwright tests covering the full auth surface: register-and-redirect, login, logout, and duplicate-email error handling.
- **`frontend/e2e/user-journey.spec.ts`** — 1 comprehensive happy-path test: register → set API key → create analysis → interact with graph → send follow-up → edit node → navigate to settings → delete account.
- **`frontend/e2e/tsconfig.json`** — TypeScript config scoped to the `e2e/` directory so Playwright's globals type-check correctly without polluting the main frontend tsconfig.
- **`frontend/src/lib/components/graph/FitViewEffect.svelte`** — New component that calls `fitView()` from inside the SvelteFlow provider context, working around the constraint that `useNodes`/`useSvelteFlow` hooks must be invoked inside the flow tree.
- **`frontend/src/lib/components/graph/GraphPanel.svelte`** — Right-click context menu via `onnodecontextmenu`; edge persistence via `onconnect` handler that writes new edges to `graphStore`.
- **`frontend/src/lib/components/graph/nodes/AnalysisNodeComponent.svelte`** — `node-pulse` CSS keyframe animation triggered via `highlightedNodeIds` store when the LLM adds or updates a node.
- **`frontend/src/lib/components/layout/AppHeader.svelte`** — Inline session rename on double-click, model badge display, and logout action.
- **`frontend/src/lib/stores/graphStore.ts`** — `highlightedNodeIds` set, `fitViewSignal` derived store, `deleteEdge` action, and Zod validation on `applyGraphActions` LLM payloads.
- **`frontend/src/routes/(protected)/(requires-api-key)/+page.svelte`** — Delete-with-undo toast, loading skeleton, and full session CRUD wiring.
- **`backend/app/api/routes/sessions.py`** — Rate limits (`60/minute`) applied to all session routes including the `add_message` endpoint introduced in 0.3.5.

### Changed
- **`frontend/package.json`** — Added `@playwright/test` devDependency; added `test:e2e` and `test:e2e:ui` scripts.
- **`CLAUDE.md`** — Corrected stale `sudo service postgresql start` → `make db` (Docker-based); added `make db`, `make db-stop`, `make db-migrate` command entries; added `test:e2e` and `test:e2e:ui` to frontend commands; updated frontend architecture tree with `FitViewEffect.svelte` and the `e2e/` directory.
- **`README.md`** — Updated E2E test count to 5 tests, added run instructions, listed `e2e/` in project structure, added `test:e2e` to commands table.

### Docs
- **`docs/plan/02_TODOS.md`** — Task 5.5 (E2E Playwright) marked complete `[x]`.
- **`docs/claude_logs/DECISION_LOG.md`** — Added Entry 019 documenting E2E test design decisions (Chromium-only, `webServer` integration, helper extraction).

---

## [0.3.5] 2026-04-19 — System message persistence, node entry animation, CI hardening

### Added
- **`backend/app/api/routes/sessions.py`** — New `POST /api/sessions/{session_id}/messages` endpoint. Accepts `{ role: "system", content: "..." }` and appends a `Message` row with a correctly sequenced `message_index` (uses `SELECT MAX ... FOR UPDATE` to prevent races). 403 on wrong user, 404 on missing session.
- **`backend/app/schemas/chat.py`** — `AddMessageRequest` schema with a `@field_validator` that restricts `role` to `"system"`, preventing clients from injecting `user` or `assistant` messages via this endpoint.
- **`backend/tests/test_sessions.py`** — 6 new tests: happy-path 201 and message appears in GET, default role, invalid role → 422, not found → 404, forbidden → 403, sequential `message_index` increment.
- **`frontend/src/lib/services/sessionService.ts`** — `addSystemMessage(sessionId, content)` — thin wrapper around `POST /api/sessions/{id}/messages` used for fire-and-forget system message persistence.
- **`frontend/src/lib/components/graph/nodes/AnalysisNodeComponent.svelte`** — `in:scale={{ duration: 200, start: 0.85 }}` transition on the node wrapper `<div>`. Nodes now scale in smoothly when Claude adds them to the graph.
- **`.github/workflows/ci.yaml`** — New `deploy-scripts` CI job that runs `bash deploy/tests/test_deploy_scripts.sh` (9 tests: syntax checks, required-variable enforcement, Dockerfile verification) on every push and pull request.

### Changed
- **`frontend/src/routes/(protected)/(requires-api-key)/session/[id]/+page.svelte`** — `handleSystemMessage` now calls `addSystemMessage` (fire-and-forget, failure is silent) after adding the message to `chatStore`, so node-edit and node-delete system messages survive page reload.
- **`.github/workflows/ci.yaml`** — Changed trigger from `workflow_dispatch`-only to `push` (branches: `main`, `feat/**`, `fix/**`) + `pull_request` + `workflow_dispatch`. CI now runs automatically on every push and PR instead of only when manually triggered.

### Fixed
- **`frontend/src/lib/services/chatService.test.ts`** — Pre-existing `svelte-check` error: `vi.mock` factory used CommonJS `require('svelte/store')`, which is invalid in an ESM context. Converted to `async () => { const { writable } = await import('svelte/store') }`. `svelte-check` now reports 0 errors/warnings.

### Docs
- **`docs/plan/02_TODOS.md`** — Complete re-audit against the live codebase. All completed items marked `[x]`, deferred or N/A items marked `[-]` with an inline reason (e.g. Add Edge, right-click menu, Terraform/ECS, E2E Playwright), remaining open items left `[ ]`. Rate limiting, SSE reconnection, system message persistence, node entry animation, and deploy script testing all marked `[x]`.
- **`README.md`** — Version bump 0.3.4 → 0.3.5. Features section updated (system message persistence, entry animation). Test coverage counts updated (104 backend, 81 frontend, 9 deploy). "What's not yet built" trimmed to genuinely unbuilt items only. Backend test note clarifies PostgreSQL requirement. Deploy test command added.

---

## [0.3.4] 2026-04-16 — AWS infrastructure setup, deploy script overhaul, .env sourcing

### Added
- **`deploy/aws/setup-infra.sh`** — One-time idempotent script that provisions the AWS infrastructure needed before a first deploy: RDS PostgreSQL 16 (private, `db.t3.micro`, 7-day backups) in the default VPC; a security group allowing port 5432 from the VPC CIDR; an RDS subnet group; an App Runner VPC connector so the backend service has egress to the private database; and Secrets Manager entries for `DATABASE_URL`, `JWT_SECRET`, and `API_KEY_ENCRYPTION_KEY`. Prints the `VPC_CONNECTOR_ARN` and `DATABASE_URL` values to add to `.env`.
- **`deploy/aws/README.md`** — Full AWS deployment procedure: IAM role creation, step-by-step first deploy (setup-infra → migrations → deploy), subsequent deploy flow, Secrets Manager promotion path, notes on `PUBLIC_API_URL` build-time compilation and CORS.

### Changed
- **`deploy/aws/deploy.sh`** — Major overhaul. Now sources root `.env` automatically (no manual exports needed). Added `DATABASE_URL`, `JWT_SECRET`, `API_KEY_ENCRYPTION_KEY` as required vars and optional `VPC_CONNECTOR_ARN`. Fixed `APP_ENV` → `ENVIRONMENT`. Build order corrected: backend builds and deploys first, then frontend image is built with `--build-arg PUBLIC_API_URL=https://$BACKEND_URL` so Vite compiles the correct backend URL into the bundle. `FRONTEND_URLS_RAW` defaults to the deployed frontend URL and is set on the backend in a second pass. `PUBLIC_API_URL` removed from runtime env vars (it is baked into the image at build time).
- **`infra/Dockerfile.frontend`** — Added `ARG PUBLIC_API_URL` and `ENV PUBLIC_API_URL=$PUBLIC_API_URL` before `bun run build`. Vite picks this up via `$env/static/public`, allowing the backend URL to be injected at image build time rather than being hardcoded in the repo.
- **`.github/workflows/deploy-aws.yaml`** — Removed duplicate build steps (the old workflow built images in the workflow *and* in `deploy.sh`). Workflow now solely configures AWS credentials and runs `deploy.sh`. Added `DATABASE_URL`, `JWT_SECRET`, `API_KEY_ENCRYPTION_KEY`, `VPC_CONNECTOR_ARN` secrets. Removed `AWS_ACCOUNT_ID` (obtained via `sts get-caller-identity` in the script). Image tag computed as short SHA via a dedicated step.
- **`.env.example`** — Added `# --- AWS Deploy ---` section with `APP_NAME`, `AWS_REGION`, `APPRUNNER_ECR_ROLE_ARN`, `DB_PASSWORD`, and `VPC_CONNECTOR_ARN` so all deployment config lives in one file.
- **`deploy/aws/setup-infra.sh`** (and `deploy.sh`) — Both scripts source the root `.env` at startup using `set -o allexport` + `source` with comment/blank-line stripping, so no manual `export` calls are needed before running them.

### Docs
- **`deploy/README.md`** — Quick-start simplified to "fill in `.env` and run the script". AWS secrets list corrected (removed `AWS_ACCOUNT_ID`, added `DATABASE_URL`/`JWT_SECRET`/`API_KEY_ENCRYPTION_KEY`/`VPC_CONNECTOR_ARN`). "Adding a database" section updated: AWS handled by `setup-infra.sh`, GCP/Azure instructions remain. Terraform note updated to reflect that AWS networking complexity is now handled.
- **`infra/README.md`** — `Dockerfile.frontend` entry notes the `PUBLIC_API_URL` build arg.
- **`README.md`** — Project tree updated to show `deploy/aws/` subdirectory with all three files. Deployment section simplified to point to `deploy/README.md`.

---

## [0.3.3] 2026-04-16 — Consolidate env files and move docker-compose to infra

### Changed
- **`.env.example`** — Merged root and `backend/.env.example` into a single file at the repo root. Corrected `FRONTEND_URLS` → `FRONTEND_URLS_RAW` to match the actual pydantic-settings field name. Added an inline note explaining that frontend public vars live in `frontend/.env.*` and why they cannot move (Vite requires env files alongside `vite.config.ts`).
- **`backend/app/core/config.py`** — `env_file` changed from `".env"` to `("../.env", ".env")` so the backend resolves the root-level `.env` whether invoked from `backend/` or the repo root, with a local fallback for convenience.
- **`docker-compose.yml` → `infra/docker-compose.dev.yml`** — Moved the postgres-only dev compose from the repo root into `infra/`. Fixed the init-SQL volume path from `./docker/postgres/init.sql` to `../docker/postgres/init.sql` to reflect the new location.
- **`Makefile`** — Updated `make db` and `make db-stop` to pass `-f infra/docker-compose.dev.yml`.
- **`.gitignore`** — Added explicit `!frontend/.env.development` and `!frontend/.env.production` negations so these non-secret public-var files are tracked despite the broad `.env.*` ignore rule.

### Fixed
- **`deploy/aws/deploy.sh`, `deploy/gcp/deploy.sh`, `deploy/azure/deploy.sh`** — All three scripts were setting `PUBLIC_API_BASE_URL` but the frontend reads `PUBLIC_API_URL` (imported via `$env/static/public` in `src/lib/config.ts`). Renamed to `PUBLIC_API_URL` so the deployed frontend actually receives the backend URL.

### Removed
- **`backend/.env.example`** — Deleted; superseded by the consolidated root `.env.example`.

### Docs
- **`README.md`** — Updated quick-start `cp` command to `cp .env.example .env`. Added `ORIGIN` to the env vars table. Updated project tree to show `infra/docker-compose.dev.yml` instead of the root `docker-compose.yml`.
- **`deploy/README.md`** — Replaced duplicated env vars table with a reference to the root README. Updated env var names to match actual settings (`APP_ENV` → `ENVIRONMENT`, `SECRET_KEY` → `JWT_SECRET`, `CORS_ORIGINS` → `FRONTEND_URLS_RAW`, `PUBLIC_API_BASE_URL` → `PUBLIC_API_URL`).
- **`infra/README.md`** — Added `docker-compose.dev.yml` entry to the file table.
- **`backend/README.md`** — Fixed commands to use `uv run` prefix. Added env file loading note.
- **`frontend/README.md`** — Replaced scaffolded SvelteKit boilerplate with project-specific commands and env file guidance.

---

## [0.3.2] 2026-04-10 — Workspace rename to challenger-agent and external Docker network

### Changed
- **`.devcontainer/Dockerfile`** — Renamed `/workspace` to `/challenger-agent` as the container working directory. Updated `PYTHONPATH` to `/challenger-agent/backend` to match.
- **`.devcontainer/devcontainer.json`** — Added `runArgs: ["--network=backend"]` so the devcontainer joins the external `backend` Docker network, enabling direct connectivity to the postgres container running via `docker-compose.yml`.
- **`.vscode/settings.json`** — Updated `PYTHONPATH`, `python.defaultInterpreterPath`, and `ruff.interpreter` from `/workspace/...` to `/challenger-agent/...` to match the Dockerfile path rename.
- **`docker-compose.yml`** — Attached the `postgres` service to an external Docker network named `backend`. Added the `networks` section declaring `backend` as `external: true` so the devcontainer and compose services share a network namespace.
- **`backend/pyproject.toml`** — Bumped version to `0.3.2`. Changed license field from a classifier string to SPDX `license = "Apache-2.0"`. Added `[tool.setuptools.packages.find]` with `include = ["app"]` and `exclude = ["alembic"]` to scope package discovery correctly.
- **`frontend/package.json`** — Bumped version to `0.3.2`.
- **`README.md`** — Added `Version: 0.3.2` line.

---

## [0.3.1] 2026-04-05 — Bug fixes, test coverage to 99%, and frontend unit tests

### Fixed
- **`backend/tests/conftest.py`** — Test `AsyncSession` was missing `expire_on_commit=False`, which the production `AsyncSessionLocal` has. The divergence caused `MissingGreenlet` errors in `test_chat_context_summarization` (the only test that triggered `db.commit()` mid-request). Added `expire_on_commit=False` to match production behaviour.
- **`backend/app/api/routes/chat.py`** — `messages`, `context_summary`, and `context_summary_covers_up_to` are now captured into local Python variables before `db.commit()`. This prevents expired-attribute lazy loads when `build_messages` accesses those values after the commit inside the `StreamingResponse` generator.
- **`backend/pyproject.toml`** — Removed `"asyncio"` from `[tool.coverage.run] concurrency`. `asyncio` is not a valid coverage.py concurrency option; its presence caused `ConfigError: Unknown concurrency choices: asyncio` and crashed pytest on startup.

### Added
- **`frontend/src/lib/stores/graphStore.test.ts`** — 21 vitest unit tests covering all graphStore mutation methods (`addNode`, `updateNode`, `deleteNode`, `addEdge`, `deleteEdge`, `setNodePosition`, `setGraph`, `clearGraph`, `getSnapshot`) and all four `applyGraphActions` action types (`add`, `update`, `delete`, `connect`), including edge cases (duplicate IDs, protected root node, duplicate edges).
- **`frontend/src/lib/stores/chatStore.test.ts`** — 11 vitest unit tests covering `addMessage`, `setMessages`, `appendToken` (streaming and non-streaming targets), `finalizeMessage`, `setStreaming`, `setError`, and `clear`.
- **`frontend/src/lib/utils/debounce.test.ts`** — 4 vitest unit tests with fake timers verifying the trailing-call debounce contract.
- **`frontend/src/lib/utils/graphLayout.test.ts`** — 6 vitest unit tests for `applyDagreLayout`: node count preserved, `userPositioned` nodes kept at their coordinates, non-user-positioned nodes receive Dagre-assigned positions, empty graph handled, edges involving user-positioned nodes skipped.
- **`frontend/src/lib/schemas/graph.test.ts`** — 19 vitest unit tests for all Zod schemas: `dimensionTypeSchema` (all 10 valid types + rejection), `analysisNodeSchema` (default `userPositioned`, required fields, numeric score), `analysisEdgeSchema` (minimal + optional fields), `analysisGraphSchema`, `llmGraphActionSchema` (all 4 discriminated union branches + rejection).

### Changed
- **`docs/plan/02_TODOS.md`** — Full audit against implemented code. All completed backend and SvelteKit tasks marked `[x]`, React-only tasks marked `[-]` (N/A), remaining items left `[ ]` with accurate descriptions.
- **`README.md`** — Complete rewrite to reflect IdeaLens application. Covers features, quick start, environment variables, command reference, annotated project structure, test coverage stats, architecture notes (streaming, graph actions, context management, API key security, auth), and a "what's not yet built" section pointing to `docs/plan/02_TODOS.md`.

---

## [0.3.0] 2026-04-04 — IdeaLens application: full backend and frontend implementation

### Added

#### Backend
- **`backend/app/core/config.py`** — Rebuilt as pydantic-settings v2 `Settings` with `get_settings()` lru_cache. List fields (`FRONTEND_URLS`, `ALLOWED_CLAUDE_MODELS`) are stored as `_RAW` string env vars and exposed via `@property` to work around pydantic-settings v2 JSON-decoding list fields before validators run.
- **`backend/app/db/models/`** — Four SQLAlchemy ORM models: `User`, `RefreshToken`, `Session` (with JSONB `graph_state`), `Message` (using `metadata_` to avoid SQLAlchemy reserved-name conflict).
- **`backend/app/db/base.py`** — Async engine and `AsyncSessionLocal` factory using `asyncpg`.
- **`backend/app/db/session.py`** — `get_db` async generator dependency with commit/rollback.
- **`backend/app/services/auth_service.py`** — JWT access/refresh tokens and bcrypt password hashing.
- **`backend/app/services/encryption_service.py`** — Fernet symmetric encryption for storing user API keys at rest.
- **`backend/app/services/llm_service.py`** — `build_messages`, `stream_with_heartbeat`, `parse_llm_response`, `summarize_messages`, `persist_messages`. Handles streaming SSE, graph action extraction from LLM output, and context window management via summarisation.
- **`backend/app/schemas/`** — Pydantic schemas for `auth`, `user`, `session`, `chat`, `graph`, `models`.
- **`backend/app/dependencies/auth.py`** — `get_current_user` FastAPI dependency.
- **`backend/app/api/routes/auth.py`** — register, login, token refresh, logout.
- **`backend/app/api/routes/users.py`** — profile, password change, API key management, account deletion.
- **`backend/app/api/routes/sessions.py`** — session CRUD and graph state PUT.
- **`backend/app/api/routes/chat.py`** — SSE streaming endpoint with reconnection support.
- **`backend/app/api/routes/models.py`** — public listing of allowed Claude model IDs.
- **`backend/app/prompts/analysis_system.py`** — Full v1.0 system prompt for IdeaLens idea analysis.
- **`backend/alembic/`** — Async Alembic configuration (`env.py`, `script.py.mako`) and initial schema migration (`f965869e64a3_initial_schema`) covering all four tables. Migration has been applied.
- **`backend/.env.example`** — Reference file documenting all required environment variables.

#### Frontend
- **`frontend/src/app.css`** — Tailwind import and custom scrollbar styles.
- **`frontend/src/lib/config.ts`** — `API_BASE_URL` sourced from `PUBLIC_API_URL`.
- **`frontend/src/lib/schemas/graph.ts`** — Zod schemas for graph node/edge types and LLM graph actions.
- **`frontend/src/lib/stores/`** — Four Svelte stores: `authStore` (with localStorage persistence), `chatStore` (streaming message state), `graphStore` (`applyGraphActions`, `getSnapshot`), `sessionStore` (session CRUD with debounced graph save).
- **`frontend/src/lib/services/`** — `api.ts` (Axios instance with Bearer interceptor and 401 auto-refresh), `authService.ts`, `userService.ts`, `sessionService.ts`, `chatService.ts`.
- **`frontend/src/lib/utils/`** — `graphLayout.ts` (Dagre auto-layout, respects `userPositioned` flag), `graphStyles.ts` (colour/label map per `DimensionType`), `debounce.ts`.
- **`frontend/src/routes/+layout.ts`** — SPA mode (`ssr = false`, `prerender = false`).
- **`frontend/src/routes/login/+page.svelte`** and **`register/+page.svelte`** — Auth forms.
- **`frontend/src/routes/(protected)/+layout.ts`** — Auth guard redirecting unauthenticated users to `/login`.
- **`frontend/src/routes/(protected)/settings/+page.svelte`** — Profile, API key, password, and danger-zone (account deletion) settings.
- **`frontend/src/routes/(protected)/(requires-api-key)/+layout.ts`** — Guard redirecting users without an API key to settings.
- **`frontend/src/routes/(protected)/(requires-api-key)/+page.svelte`** — Dashboard with session list and New Analysis modal.
- **`frontend/src/routes/(protected)/(requires-api-key)/session/[id]/+page.svelte`** — Workspace with auto-send on load, streaming chat, and live graph action processing.
- **`frontend/src/lib/components/layout/`** — `AppHeader.svelte` (inline session rename), `SplitLayout.svelte` (svelte-splitpanes 40/60 split).
- **`frontend/src/lib/components/chat/`** — `ChatPanel.svelte`, `ChatInput.svelte`, `MessageBubble.svelte`, `ModelSelector.svelte`.
- **`frontend/src/lib/components/graph/`** — `GraphPanel.svelte` (@xyflow/svelte controlled flow), `GraphToolbar.svelte` (auto-layout trigger), `NodeDetailPanel.svelte` (slide-over with edit/delete), `nodes/AnalysisNodeComponent.svelte` (custom node styled by `DimensionType`).

### Changed
- **`backend/app/main.py`** — Rewrote with `create_app()` factory, correct middleware order (CORS then SecurityHeaders), slowapi rate limiter, and lifespan DB connectivity check.
- **`frontend/src/routes/+layout.svelte`** — Added `<Toaster>` and `authStore.init()` call.
- **`frontend/svelte.config.js`** — Added `vitePreprocess()`.
- **`frontend/vite.config.ts`** — Configured `server.host` and `server.port` (5173).
- **`frontend/package.json`** — Added dependencies: `@xyflow/svelte`, `@dagrejs/dagre`, `zod`, `axios`, `svelte-sonner`, `svelte-splitpanes`, `lucide-svelte`, `date-fns`, `uuid`.

### Removed
- **`frontend/src/routes/+page.svelte`** — Deleted; the dashboard now lives at `(protected)/(requires-api-key)/+page.svelte`.

---

## [0.2.2] 2026-04-03 — Devcontainer and developer experience fixes

### Fixed
- **`.devcontainer/Dockerfile`** — `PYTHONPATH` was set to `/workspace`, but the backend source is at `/workspace/backend/app/`, so `from app.X import Y` would only resolve because `cd backend` added the CWD to `sys.path` at runtime. Changed to `/workspace/backend` so the path is correct unconditionally and VS Code's language server can resolve imports without relying on the shell's working directory.
- **`.vscode/settings.json`** — `PYTHONPATH` in the integrated terminal was `/workspace:/workspace/src`; `/workspace/src` does not exist and the base path was wrong (see above). Changed to `/workspace/backend`. Also fixed `ruff.interpreter` and added `python.defaultInterpreterPath`, both pointing to `/workspace/backend/.venv/bin/python3` — the correct venv location created by `uv venv backend/.venv` in the Dockerfile. Previously they pointed to `/workspace/.venv` which does not exist, meaning Ruff and Pylance would silently use the wrong interpreter.
- **`.vscode/settings.json`** — `python.testing.pytestArgs` was `["tests"]`, which VS Code resolves relative to the workspace root (`/workspace/tests/` — does not exist). Changed to `["backend/tests"]` so the VS Code test runner discovers and runs tests correctly.
- **`Makefile`** — `uvicorn` and `pytest` were called as bare commands, which requires the `.venv` to be manually activated beforehand. Changed all backend commands to use `uv run` (`uv run uvicorn`, `uv run pytest`), which automatically resolves and uses the `backend/.venv` without requiring any activation step.
- **`backend/pyproject.toml`** — Added `asyncio_mode = "auto"` to `[tool.pytest.ini_options]`. Without this, any async test function added in the future would require an explicit `@pytest.mark.asyncio` decorator to run; with `auto` mode, async tests are discovered and run automatically by `pytest-asyncio`.
- **`backend/pyproject.toml`** — Changed `authors[0].email` from `{{ author_email }}` (an invalid placeholder that fails `pyproject.toml` validation with `must be idn-email`) to `author@example.com`, a syntactically valid placeholder that tools can parse without errors.

### Changed
- **`MAINTENANCE.md`** — Updated the placeholder replacement table: `{{ author_email }}` is now `author@example.com` to match the pyproject.toml change. Added a note to commit `frontend/bun.lock` after first opening the devcontainer — it is generated by `bun install` in `postStartCommand` and must be tracked for reproducible frontend builds.
- **`README.md`** — Updated the placeholder table to reflect `author@example.com` instead of `{{ author_email }}`.

---

## [0.2.1] 2026-04-03 — Bug fixes and template polish

### Fixed
- **`backend/app/core/config.py`** — `CORS_ORIGINS` was typed as `list[str]` but Pydantic would treat a comma-separated string like `http://localhost:5173,https://example.com` as a single-element list containing the whole string. Added a `@field_validator` that splits on commas when the value is a plain string, matching the documented behaviour. Multiple origins now work correctly.
- **`deploy/aws/deploy.sh`** — The frontend's `ORIGIN` env var was hardcoded to `https://$APP_NAME-frontend.us-east-1.awsapprunner.com`. App Runner assigns URLs with an unpredictable hash segment (e.g. `abc123.us-east-1.awsapprunner.com`), so this value was always wrong and would break CSRF protection on the frontend. Restructured to a two-pass deploy: create/update the service first, then query the real URL from App Runner and do a follow-up `update-service` call to set `ORIGIN` to the actual assigned URL.
- **`deploy/azure/deploy.sh`** — The frontend's `ORIGIN` was set to `https://$APP_NAME-frontend`, which is missing the full Azure Container Apps FQDN suffix. This would cause `adapter-node` to reject all requests with a 403 CSRF error. Restructured to the same two-pass pattern: deploy without `ORIGIN`, query the real FQDN from Azure, then update with the correct value.

### Changed
- **`.vscode/settings.json`** — Removed three stale `geminicodeassist.*` settings that were left over from a previous project. The `google.geminicodeassist` extension was already removed from the devcontainer in 0.2.0 but these settings were missed.
- **`backend/pyproject.toml`** — Pinned `ruff==0.14.0` in dev dependencies to match the version already pinned in `.pre-commit-config.yaml`. Previously `ruff` had no version constraint, which meant local development and pre-commit could run different versions and produce inconsistent lint results.
- **`frontend/package.json`** — Added `"engines": { "node": ">=24" }` to make the `engine-strict=true` setting in `.npmrc` meaningful. Without an `engines` field, the strict check had nothing to enforce.
- **`.github/workflows/ci.yaml`** — Changed `bun-version: latest` to `bun-version: "1"` on all bun setup steps. Using `latest` risks CI breaking on a future major version bump; pinning to the major version `"1"` matches the `oven/bun:1` image used in `Dockerfile.frontend`.
- **`README.md`** — Clarified the Docker ports note: the frontend runs on `:3000` only in the Docker production build; during local development with `make dev` it runs on `:5173` via the Vite dev server.
- **`frontend/README.md`** — Restored to the original `sv` CLI scaffold output. The file serves as a permanent record of how the frontend was bootstrapped and what command reproduces that exact configuration. Usage instructions remain in the root README.
- **`backend/README.md`** — Replaced empty file with a quick-reference command list for backend development tasks.
- **`infra/README.md`** — Replaced empty file with a brief description of each Dockerfile and the docker-compose file, with a pointer to `deploy/README.md`.
- **`deploy/README.md`** — Added a "Terraform" section explaining why the CLI scripts are the right fit for this template's current scope, and listing the five concrete triggers for migrating to Terraform (database, private networking, multiple environments, drift detection, team ownership).
- **`CHANGELOG.md`** — Fixed a forward reference to version `0.3.0` in the 0.1.0 entry; corrected to `0.2.0`.

---

## [0.2.0] 2026-04-03 — Template hardening and production readiness

### Added
- **Backend scaffold directories** (`api/routes/`, `api/deps.py`, `core/`, `services/`, `models/`, `schemas/`, `db/`) — The README described a layered architecture but none of the directories existed on disk, so cloning the template and following the guide would immediately fail. These directories are now created with `.gitkeep` files so the structure is present and committed. `deps.py` contains a short comment explaining its purpose so it is clear where FastAPI dependencies belong.
- **Frontend scaffold directories** (`lib/components/`, `lib/stores/`, `lib/api/`) — Same issue as the backend: the documented structure was missing from the actual file tree. These directories are now present so new components, stores, and API client modules have an obvious home from the start.
- **`.env.example`** — A reference file documenting every environment variable the application reads, with inline comments explaining acceptable values and how to generate secrets. `.env` is gitignored; `.env.example` is committed so that anyone cloning the template knows exactly what to set up before running the app. Includes `APP_ENV`, `SECRET_KEY`, `DATABASE_URL` (commented, for when a database is added), `CORS_ORIGINS`, and frontend `PUBLIC_` prefixed vars.
- **`MAINTENANCE.md`** — A checklist documenting everything that needs periodic attention: Python version bumps, backend and frontend dependency upgrades, pre-commit hook version updates, Node.js version updates in the devcontainer, and GitHub Actions action version pins. Each section includes the exact commands to run. Also lists the `{{ placeholder }}` tokens that must be replaced when the template is first used.
- **`infra/Dockerfile.backend`** — A production-grade multi-layer image. Dependencies are installed before copying source code so that rebuilds triggered by source-only changes reuse the cached dependency layer. Uses `uv` copied directly from its official image via `COPY --from=ghcr.io/astral-sh/uv:latest` to avoid installing it at runtime and to ensure a reproducible version.
- **`infra/Dockerfile.frontend`** — A multi-stage build. Stage one uses `oven/bun:1` to install dependencies and run `bun run build`. Stage two copies only the compiled `build/` output into a `node:24-alpine` image, resulting in a final image that contains no source code, no `node_modules`, and no build tooling — only the Node runtime and the compiled application.
- **`backend/app/core/config.py`** — Introduced a `pydantic-settings` `Settings` class as the single source of truth for all runtime configuration. Settings are read from environment variables and `.env` files automatically. This replaces the pattern of reading `os.environ` directly in application code and makes configuration type-safe and testable.
- **`backend/tests/conftest.py`** — Added a `client` pytest fixture that wraps FastAPI's `TestClient` in a context manager. All test files in the suite can now request this fixture without repeating setup boilerplate.
- **`backend/tests/test_main.py`** — First concrete test: a smoke test against the `/health` endpoint that confirms the app starts, routes correctly, and returns the expected JSON shape. Serves as the baseline test to verify the test infrastructure itself is working.
- **`frontend/src/lib/example.test.ts`** — A minimal passing vitest test added as a placeholder. The intent is to keep the CI pipeline green from day one while making it obvious where unit tests for stores, utilities, and API client code should be written.
- **`vitest` + `@vitest/coverage-v8`** — Added vitest as the frontend test runner. It integrates directly with the existing Vite config, so no separate test bundler config is needed. `@vitest/coverage-v8` provides coverage reports using V8's built-in instrumentation, which is faster than Babel-based alternatives.
- **`test`, `test:watch`, `test:coverage` scripts** — Three new npm scripts in `frontend/package.json`. `test` runs once for CI, `test:watch` runs in interactive watch mode during development, and `test:coverage` produces a coverage report to `coverage/`.
- **`httpx`** added to backend dev dependencies — FastAPI's `TestClient` requires `httpx` as a transport backend when testing async endpoints. Without it, tests that call async route handlers will fail silently or raise import errors.
- **`deploy/aws/deploy.sh`** — A bash script that builds the backend and frontend Docker images, pushes them to Amazon ECR (creating the repositories if they do not yet exist), then creates or updates App Runner services for both. The script is idempotent: re-running it on an existing deployment updates the image without touching service configuration. The image tag defaults to the current git commit SHA so every deployment is traceable.
- **`deploy/gcp/deploy.sh`** — Equivalent deployment script for Google Cloud Platform. Pushes images to Artifact Registry, deploys both services to Cloud Run with `--allow-unauthenticated`, and wires `PUBLIC_API_BASE_URL` on the frontend service to the Cloud Run URL of the backend. A second `gcloud run services update` pass sets `ORIGIN` on the frontend once its own URL is known — this is required by `adapter-node` for CSRF protection to work correctly.
- **`deploy/azure/deploy.sh`** — Equivalent deployment script for Azure. Creates an Azure Container Registry (if absent), pushes both images, provisions a Container Apps Environment, and deploys both services into it. On update it calls `az containerapp update` instead of re-creating the service, preserving scaling rules and secret references configured outside this script.
- **`deploy/README.md`** — Explains how to use the three deployment scripts, documents every environment variable required by each provider, lists the GitHub secrets that must be configured for the Actions workflows, and includes guidance on adding a managed database.
- **`.github/workflows/deploy-aws.yaml`**, **`deploy-gcp.yaml`**, **`deploy-azure.yaml`** — GitHub Actions workflows for each cloud provider, triggered manually via `workflow_dispatch`. Each workflow authenticates with the provider using repository secrets, then runs the corresponding `deploy/*.sh` script. The `image_tag` input defaults to the triggering commit SHA. Instructions for switching to automatic `push`-triggered deploys are in `deploy/README.md`.
- **`frontend-tests` CI job** — A dedicated job in `ci.yaml` that runs `bun run test`. The existing `frontend-build` job now declares `needs: frontend-tests`, so a failing test blocks the build step entirely rather than letting a broken build reach main.

### Changed
- **`.devcontainer/devcontainer.json`** — Fixed a stale `--tag` build option that referenced `gradio-chat-agent:260104`, a name copied from a different project. Changed to `fastapi-sveltekit-dev:latest` to match this template. Also added a `~/.claude` bind mount alongside the existing `~/.gemini` mount so that Claude Code authentication and settings persist between container rebuilds without needing to re-authenticate each time. Added `anthropic.claude-code` to the VS Code extensions list.
- **`.devcontainer/Dockerfile`** — Added `npm install -g @anthropic-ai/claude-code` to the Node.js setup block so that the `claude` CLI is available globally inside the container immediately after build, with no manual post-start steps required.
- **`backend/pyproject.toml`** — The initial `dependencies` list contained only `pip` and `pyyaml`, which are not the actual runtime dependencies of a FastAPI application. Replaced with `fastapi`, `uvicorn[standard]` (includes `httptools` and `websockets` for production throughput), and `pydantic-settings`. Also removed a stale `[project.scripts]` entry that pointed to `backend.app.main:app` under the name `gradio-agent` — a leftover from the project this template was derived from. Fixed `--cov=src` in pytest options to `--cov=app` to match the actual source directory. Genericised the `authors` field to `{{ author_name }}` / `{{ author_email }}` placeholders.
- **`infra/docker-compose.yaml`** — Added `env_file: ../.env` to both services so that environment variables are injected at runtime without hardcoding them in the compose file. Added a `healthcheck` on the backend service that polls `GET /health` every 30 seconds. Added `depends_on` with `condition: service_healthy` on the frontend so it does not start until the backend is confirmed ready. Removed the deprecated top-level `version:` key, which Compose v2 ignores with a warning.
- **`Makefile`** — Changed `npm run dev` to `bun run dev` in both the `dev` and `frontend` targets. The devcontainer installs Bun as the package manager and the `postStartCommand` uses `bun install`, but the Makefile was still invoking `npm`, which would not be on the PATH in a Bun-only environment.
- **`.github/workflows/ci.yaml`** — The original file was entirely commented out and referenced outdated tooling (Python 3.11, `pip install -r requirements.txt`, Node 18, `npm install`). Rewrote it as three active jobs: `backend-tests` (runs `pytest` via `uv run`), `backend-lint` (runs `ruff check` and `ruff format --check`), and `frontend-build` (installs with `bun`, runs `svelte-check`, runs `vite build`). Uses `astral-sh/setup-uv@v5` and `oven-sh/setup-bun@v2` which handle tool caching automatically.
- **`frontend/svelte.config.js`** — Replaced `@sveltejs/adapter-auto` with `@sveltejs/adapter-node`. `adapter-auto` detects the deployment target at build time by inspecting environment variables set by hosting platforms. Because this template builds inside Docker with no hosting-platform variables present, `adapter-auto` was falling back to an incorrect adapter. `adapter-node` produces a standard Node.js server unconditionally and is the correct choice for any Docker-based or self-hosted deployment.
- **`frontend/vite.config.ts`** — Changed the `defineConfig` import from `vite` to `vitest/config`. This is required to add a `test` block to the config with full TypeScript type support. The `plugins` array and existing Vite settings are unchanged.
- **`backend/app/main.py`** — Added `CORSMiddleware` configured from `settings.cors_origins`. Without explicit CORS headers, browser requests from the frontend domain to the backend are blocked. The origins are controlled via the `CORS_ORIGINS` environment variable so they can differ between development (`http://localhost:5173`) and production (the real frontend URL) without code changes.
- **`.env.example`** — Added `ORIGIN` and `PORT` entries under a new `Frontend (adapter-node)` section. `ORIGIN` is mandatory in production — `adapter-node` uses it to validate the `Host` header for CSRF protection, and requests will fail with a 403 if it is missing or wrong.
- **`README.md`** — Complete rewrite. The previous file contained only a three-line feature list and a `make dev` command. The new version covers: how to create a project from the template, placeholder replacement, environment setup, devcontainer usage, full annotated project structure, development workflows for backend and frontend, Docker local usage, deployment quick-start for all three providers, and a configuration reference table.

### Removed
- **`google.geminicodeassist`** VS Code extension — Removed from the devcontainer extension list. This extension is tied to a specific AI assistant product and is not appropriate for a generic template that others will use with different tooling preferences.

---

## [0.1.0] 2026-01-31 — Initial template

### Added
- **FastAPI backend skeleton** — A minimal `app/main.py` with a single `GET /health` endpoint returning `{"status": "ok"}`. Managed with `uv` and targeting Python 3.12. The health endpoint serves as both a liveness check and a baseline integration test target.
- **SvelteKit 2 + Svelte 5 frontend** — Scaffolded with Svelte 5 runes syntax (`$props()`, `$state()`, `$derived()`, `{@render ...}`). TailwindCSS 4 is configured via the `@tailwindcss/vite` plugin — no `tailwind.config.js` file is needed. TypeScript strict mode is enabled. The adapter is set to `adapter-auto` at this point (later changed to `adapter-node` in 0.2.0).
- **VS Code devcontainer** — Ubuntu 24.04 base image with Python 3.12.11 (installed via `uv`), Node.js 24 (installed via `nvm`), and Bun as the frontend package manager. Also installs the Google Gemini CLI. The `postStartCommand` syncs Python dependencies and installs frontend packages so the environment is ready to use as soon as the container starts.
- **`Makefile`** — Four targets: `dev` (runs backend and frontend in parallel), `backend` (uvicorn with `--reload`), `frontend` (`npm run dev`, later corrected to `bun run dev`), and `test` (runs pytest).
- **`backend/pyproject.toml`** — Configures `uv`, `ruff`, and `pytest`. Ruff is set to line length 79 with double quotes, targeting Python 3.12. Pytest is configured with `-ra -q`, coverage reporting, and `asyncio` support for testing async route handlers. Ruff lint rules include `E`, `F`, `I` (isort), `C`, `W`, `UP`, `PERF`, `SIM`, and selected `RUF` and `PLC` codes.
- **`.pre-commit-config.yaml`** — Installs two Ruff hooks: `ruff-check` (with `--fix`) and `ruff-format`, both scoped to the `backend/` directory only. Frontend code is formatted by Prettier via the VS Code extension on save rather than as a pre-commit hook.
- **`.vscode/settings.json`** — Configures Ruff as the default Python formatter, enables pytest test discovery, associates `.css` files with the Tailwind CSS language server, and sets `PYTHONPATH=/workspace` in the integrated terminal so that `from app.X import Y` imports resolve correctly.
- **`.vscode/launch.json`** — Two `debugpy` launch configurations: one that debugs the currently open Python file and one that runs the pytest test suite under the debugger, allowing breakpoints inside test code.
- **`infra/docker-compose.yaml`** — Initial stub with `backend` and `frontend` services pointing at the two production Dockerfiles. Both Dockerfiles are empty placeholders at this stage.
- **`.github/workflows/ci.yaml`** — Added as a fully commented-out placeholder. The intent was to document the expected CI structure (backend tests + frontend build) without running it, as the backend has no real dependencies installed yet.
- **`LICENSE`** — Apache 2.0.
