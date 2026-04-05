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
