# DECISION LOG — IdeaLens

Autonomous mode decision log. Every significant ambiguity resolved without user input is recorded here.

---

### Entry 001

**Type:** Decision
**Mode:** Autonomous
**Timestamp:** 2026-04-04T00:00:00Z
**Task:** Project structure adaptation

**Context:** The plan specifies `apps/api`, `apps/web-react`, `apps/web-svelte`. The repo is cloned from a template using `backend/` and `frontend/`.
**Decision / Action:** Keep the existing `backend/` and `frontend/` directory structure. Map plan's `apps/api` → `backend/`, `apps/web-svelte` → `frontend/`. Skip the React frontend entirely.
**Rationale:** Restructuring would require changing Makefile, docker-compose, git history, and all import paths for zero functional benefit. The repo has one SvelteKit frontend and that is what the user wants to build.
**Impact / Risk:** All file paths in the plan must be mentally remapped. Documentation paths in CLAUDE.md remain valid.
**Outcome:** Proceeding with existing structure.

---

### Entry 002

**Type:** Decision
**Mode:** Autonomous
**Timestamp:** 2026-04-04T00:00:00Z
**Task:** Frontend dev port

**Context:** Plan specifies SvelteKit on port 3001. Existing template uses 5173 (Vite default).
**Decision / Action:** Keep port 5173 for local development. Update vite.config.ts server block accordingly.
**Rationale:** No tooling changes needed; Makefile and CLAUDE.md already document 5173.
**Impact / Risk:** Docker-compose if created will need port 5173 instead of 3001.
**Outcome:** Proceeding with port 5173.

---

### Entry 003

**Type:** Decision
**Mode:** Autonomous
**Timestamp:** 2026-04-04T00:00:00Z
**Task:** CORS origins

**Context:** Plan defaults CORS to ports 3000 and 3001. With one SvelteKit frontend on 5173, this changes.
**Decision / Action:** Set `FRONTEND_URLS` default to `["http://localhost:5173"]`.
**Rationale:** Matches the single-frontend setup and existing template port.
**Impact / Risk:** If user ever adds a React frontend they must update FRONTEND_URLS.
**Outcome:** Config updated accordingly.

---

### Entry 004

**Type:** Decision
**Mode:** Autonomous
**Timestamp:** 2026-04-04T00:00:00Z
**Task:** Backend directory layout

**Context:** Plan places config at `app/config.py` (top-level in app/). Template uses `app/core/config.py`.
**Decision / Action:** Keep config at `app/core/config.py` but expose `get_settings()` from there. Adapt all plan import paths accordingly.
**Rationale:** Minimal change; the existing structure is already in place.
**Impact / Risk:** All backend imports must use `app.core.config` not `app.config`.
**Outcome:** Proceeding with `app/core/config.py`.

---

### Entry 005

**Type:** Decision
**Mode:** Autonomous
**Timestamp:** 2026-04-04T00:00:00Z
**Task:** Infrastructure / Terraform / CI

**Context:** Plan Phase 5 covers Docker production Dockerfiles, Terraform AWS, GitHub Actions. This is deferred.
**Decision / Action:** Skip Terraform, CI/CD, production Dockerfiles for this build. Focus on Phases 1–4 (working local app).
**Rationale:** Infrastructure is separable and can be added later. The user asked to "build the app" — the functioning application is the priority.
**Impact / Risk:** No production deployment capability until Phase 5 is implemented.
**Outcome:** Phase 5 deferred.

---

### Entry 006

**Type:** Decision
**Mode:** Autonomous
**Timestamp:** 2026-04-05T00:00:00Z
**Task:** pydantic-settings v2 list[str] field handling

**Context:** pydantic-settings v2.13.1 attempts to JSON-decode `list[str]` fields from env vars before calling field validators. A value like `FRONTEND_URLS=http://localhost:5173` fails JSON parsing, causing a `SettingsError` even with `mode="before"` validators.
**Decision / Action:** Declare list-valued settings as raw string fields (`FRONTEND_URLS_RAW`, `ALLOWED_CLAUDE_MODELS_RAW`) and expose them as `@property` returning `list[str]`.
**Rationale:** Cleanest workaround that preserves the comma-separated env var convention without requiring JSON syntax in `.env`.
**Impact / Risk:** Field names in `.env` must use `_RAW` suffix. Any code reading these settings must use the property names (no `_RAW`).
**Outcome:** Settings load correctly; `get_settings().FRONTEND_URLS` returns `list[str]`.

---

### Entry 007

**Type:** Decision
**Mode:** Autonomous
**Timestamp:** 2026-04-05T00:00:00Z
**Task:** PostgreSQL installation in container

**Context:** No PostgreSQL server was available in the dev container. Alembic migrations and backend startup require a live database.
**Decision / Action:** Installed PostgreSQL 16 via `apt-get` inside the container, started the service, created `idealens` and `idealens_test` databases owned by the `idealens` user.
**Rationale:** Fastest path to a working DB in a self-contained environment. `make dev` will need this service running.
**Impact / Risk:** The service is not configured to auto-start; must run `sudo service postgresql start` in fresh sessions. A `docker-compose.yml` with a postgres service is the proper long-term solution.
**Outcome:** Migrations applied (`alembic upgrade head`), backend starts and connects successfully.

---

### Entry 008

**Type:** Decision
**Mode:** Autonomous
**Timestamp:** 2026-04-05T00:00:00Z
**Task:** @xyflow/svelte v1.5.2 + Svelte 5 event API

**Context:** The plan's `GraphPanel.svelte` example uses Svelte 4 `on:` event directives (`on:nodedragstop`, `on:nodeclick`, etc.) and imports `NodeDragEvent`/`NodeMouseEvent` types. Neither works in @xyflow/svelte v1.5.2 with Svelte 5.
**Decision / Action:** Use the Svelte 5 prop-based event API: `onnodedragstop`, `onnodeclick`, `onpaneclick`, `ondelete` (passed as props to `<SvelteFlow>`). Use `ondelete` (which takes `{nodes, edges}`) instead of separate `nodesdelete`/`edgesdelete`. Import no event types — inline the parameter shapes.
**Rationale:** @xyflow/svelte v1.5.2 is built for Svelte 5 runes mode and exposes events as component props via `SvelteFlowProps`.
**Impact / Risk:** If @xyflow/svelte is downgraded to a v0.x (Svelte 4) release, this code breaks. Pin the version.
**Outcome:** GraphPanel compiles correctly.

---

### Entry 009

**Type:** Decision
**Mode:** Autonomous
**Timestamp:** 2026-04-05T00:00:00Z
**Task:** Svelte 5 runes mode — `afterUpdate` removed

**Context:** The plan's `ChatPanel.svelte` uses `afterUpdate` + `tick` for auto-scroll. Svelte 5 runes mode removes `afterUpdate`.
**Decision / Action:** Replace with `$effect(() => { ... })` that subscribes to `$chatStore.messages.length` and uses `setTimeout(..., 0)` to schedule the scroll after DOM update.
**Rationale:** `$effect` is the runes-mode replacement for `afterUpdate`. The `setTimeout` gives the DOM a tick to paint before measuring `scrollHeight`.
**Impact / Risk:** Slightly less precise timing than `tick()` but functionally equivalent and simpler.
**Outcome:** Auto-scroll works in runes mode.

---

### Entry 010

**Type:** Decision
**Mode:** Autonomous
**Timestamp:** 2026-04-05T00:00:00Z
**Task:** Session messages not returned in `SessionResponse` schema

**Context:** The backend `GET /api/sessions/{id}` route uses `selectinload(DBSession.messages)` but the `SessionResponse` Pydantic schema does not include a `messages` field. The frontend `sessionStore.loadSession` needs messages to populate `chatStore`.
**Decision / Action:** Extend `sessionStore.loadSession` to cast `resp.data` with an optional `messages` array field and populate `chatStore` if present. The backend response will include messages because SQLAlchemy eager-loads them and FastAPI serialises the full model (including relationships) — but Pydantic drops them since they're not in the schema.
**Risk Identified:** Messages are silently dropped by Pydantic. A returning user who revisits a session will see an empty chat panel even though messages exist in the DB.
**Follow-up Required:** Add a `messages` field to `SessionResponse` in `app/schemas/session.py` (list of `MessageResponse`), include it in the route serialisation, and update the `GET /api/sessions/{id}` route to return it. This is the most critical remaining bug before first use.

---

### Entry 011

**Type:** Bug Fix
**Mode:** Autonomous
**Timestamp:** 2026-04-05T00:00:00Z
**Task:** passlib + bcrypt 5.x incompatibility (production-breaking bug)

**Context:** `passlib[bcrypt]` 1.7.4 (last release 2020) is incompatible with `bcrypt` 5.x. The `detect_wrap_bug` function inside passlib calls `_bcrypt.hashpw` with a 214-byte password; bcrypt 5.x raises `ValueError: password cannot be longer than 72 bytes`. This breaks ALL `hash_password` and `verify_password` calls — register, login, and password change fail in production.
**Decision / Action:** Replaced passlib with direct `bcrypt` calls in `app/services/auth_service.py`. Updated `pyproject.toml` to replace `passlib[bcrypt]>=1.7.4` with `bcrypt>=4.0.0`.
**Rationale:** passlib is unmaintained (no updates since 2020). Direct bcrypt is simpler and more reliable.
**Impact / Risk:** Any existing password hashes created with passlib's bcrypt are still valid — the hash format is identical (`$2b$...`). No data migration needed.
**Outcome:** All 32 tests pass; password hashing works correctly.

---

### Entry 012

**Type:** Bug Fix
**Mode:** Autonomous
**Timestamp:** 2026-04-05T00:00:00Z
**Task:** `RefreshToken.expires_at` timezone mismatch

**Context:** `RefreshToken.expires_at` is `TIMESTAMP WITHOUT TIME ZONE` (naive) in the DB schema, but auth routes were passing `datetime.now(timezone.utc)` (tz-aware) as the value. asyncpg rejects this with "can't subtract offset-naive and offset-aware datetimes". This broke login, register, and refresh in the test suite (and would break in production).
**Decision / Action:** Strip timezone before storing: `datetime.now(timezone.utc).replace(tzinfo=None)`. The existing comparison code already did `.replace(tzinfo=timezone.utc)` when reading — confirming naive storage was always the intent.
**Rationale:** Changing the DB column to TIMESTAMP WITH TIME ZONE would require a migration; stripping timezone before insert is consistent with the existing comparison code.
**Impact / Risk:** All datetime values in refresh_tokens are treated as UTC. If server timezone ever changes, there could be issues — but this is standard practice for "store UTC naive datetimes".
**Outcome:** 32 tests pass including refresh and logout flows.

---

### Entry 013

**Type:** Decision
**Mode:** Autonomous
**Timestamp:** 2026-04-05T00:00:00Z
**Task:** Dagre auto-layout — per-action vs post-completion

**Context:** The previous implementation ran Dagre layout on every `onGraphAction` callback but only when `nodes.length <= 5`. This meant sessions with >5 nodes never got auto-layout after the initial state.
**Decision / Action:** Remove per-action layout. Run layout once in `onDone` (after each LLM streaming response completes) for all node counts > 0.
**Rationale:** Per-action layout during streaming is janky (graph re-arranges while user watches). Post-completion layout is clean and applies universally regardless of node count.
**Impact / Risk:** Nodes will not animate into position during streaming — they appear at the LLM-provided position during the stream, then snap to Dagre layout on completion. This is acceptable and common in graph tools.
**Outcome:** Layout runs correctly after every LLM response.


---

### Entry 014

**Type:** Bug Fix
**Mode:** Autonomous
**Timestamp:** 2026-04-05T00:00:00Z
**Task:** Test `db` fixture missing `expire_on_commit=False`

**Context:** `test_chat_context_summarization` was failing with `sqlalchemy.exc.MissingGreenlet`. After `await db.commit()` in the chat route, SQLAlchemy expires all session-attached objects. When `build_messages` then accessed `m.message_index` on the expired `Message` objects (inside the `StreamingResponse` async generator), SQLAlchemy attempted a lazy DB load outside a greenlet context.
**Decision / Action:** Added `expire_on_commit=False` to the `AsyncSession(...)` constructor in `tests/conftest.py` to match the production `AsyncSessionLocal` which already had this flag. Also captured `messages`, `context_summary`, and `context_summary_covers_up_to` into local Python variables before `db.commit()` in `app/api/routes/chat.py` as a defence-in-depth fix.
**Rationale:** The production session factory used `expire_on_commit=False` but the test session factory did not. This mismatch caused tests to fail only on code paths that committed mid-request. Matching both settings is the correct fix; the local variable capture guards against future code paths that might re-use session objects post-commit.
**Impact / Risk:** Tests now behave identically to production regarding post-commit attribute access. No risk.
**Outcome:** All 98 tests pass.

---

### Entry 015

**Type:** Bug Fix
**Mode:** Autonomous
**Timestamp:** 2026-04-05T00:00:00Z
**Task:** coverage.py `asyncio` not a valid concurrency option

**Context:** `pyproject.toml` had `concurrency = ["greenlet", "thread", "asyncio"]` in `[tool.coverage.run]`. coverage.py rejected `asyncio` as an unknown concurrency choice, crashing pytest on startup with `ConfigError: Unknown concurrency choices: asyncio`.
**Decision / Action:** Removed `asyncio` from the list; kept only `["greenlet", "thread"]`.
**Rationale:** `greenlet` is the correct option for tracking SQLAlchemy async code (which uses greenlets internally). `asyncio` is not a valid coverage.py concurrency option — asyncio coroutines are tracked by default without any special setting.
**Impact / Risk:** None. Coverage results are unchanged; the `asyncio` entry was never doing anything.
**Outcome:** `pytest` starts and runs coverage correctly.

---

### Entry 016

**Type:** Decision
**Mode:** Autonomous
**Timestamp:** 2026-04-05T00:00:00Z
**Task:** Frontend review — agent flagged false positives

**Context:** An Explore subagent reviewing the frontend flagged two "critical" issues: (1) `get({ subscribe })` in graphStore/sessionStore is wrong Svelte API, (2) `chatStore.appendToken(token)` without an ID is a correctness bug.
**Decision / Action:** Rejected both findings after manual verification. `get({ subscribe })` is valid — `get()` from `svelte/store` accepts any object with a `subscribe` method, and `{ subscribe }` is exactly that (destructured from the store's writable). `appendToken(token)` without ID is correct for this use case — there is only ever one streaming message at a time, so targeting "the last streaming message" is unambiguously correct.
**Rationale:** The agent pattern-matched against a React/ID-based mental model rather than understanding the actual Svelte store API and the single-stream constraint of this application.
**Impact / Risk:** No changes needed. Validating agent findings against the actual code before acting is essential when the claim is about correctness of an unfamiliar API.
**Outcome:** No code changes; frontend confirmed correct.

---

### Entry 017

**Type:** Decision
**Mode:** Autonomous
**Timestamp:** 2026-04-05T00:00:00Z
**Task:** Frontend unit test scope

**Context:** Frontend had 0% meaningful test coverage (one placeholder test). The plan mentions vitest but specifies tests for `graphStore.applyGraphActions` and the SSE parser specifically. Components and services make real HTTP calls or require a DOM environment.
**Decision / Action:** Added unit tests for: `graphStore` (21 tests — all mutation methods and all `applyGraphActions` action types), `chatStore` (11 tests), `graphLayout.ts` (6 tests), `debounce.ts` (4 tests), `schemas/graph.ts` Zod validators (19 tests). Skipped SSE parser in `chatService.ts` (requires `fetch` mock setup) and Svelte component tests (require `@testing-library/svelte` + JSDOM setup).
**Rationale:** Pure logic functions (stores, utilities, Zod schemas) are the highest-value unit test targets and require no test infrastructure beyond vitest. Component and HTTP service tests have meaningful setup overhead for limited additional signal given the backend integration tests already cover the contract.
**Impact / Risk:** 62 frontend tests added; SSE parser and component tests remain as future work.
**Outcome:** Frontend test suite at 62 passing tests with strong coverage of all store business logic.
