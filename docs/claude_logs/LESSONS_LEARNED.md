# Lessons Learned

---

## 2026-04-03 — ran uv outside the devcontainer where it is not installed

**What happened:** Attempted `uv lock` via the Bash tool to regenerate the lock file after changing `pyproject.toml`. `uv` is only installed inside the devcontainer; the host Windows shell does not have it on PATH.

**Lesson:** Before running Python tooling (`uv`, `pytest`, `ruff`) or frontend tooling (`bun`) via Bash on this machine, check whether the devcontainer is the expected execution environment. If the command requires devcontainer tools, hand it to the user or note it as a manual step.

## 2026-04-03 — replaced scaffold-generated README that served as bootstrapping provenance

**What happened:** `frontend/README.md` was the original output of `npx sv create`. It was replaced with a generic quick-reference file on the assumption it had no value. The user had to correct this — the file documents the exact `sv` CLI command used to bootstrap the project, which is useful provenance for anyone cloning the template.

**Lesson:** Scaffold-generated READMEs (from `sv create`, `create-react-app`, `cargo new`, etc.) should be preserved as-is — they record how the project was initialised. If additional content is needed, create a separate file rather than overwriting the scaffold output.

## 2026-04-03 — Write tool rejected on a file created by touch without a prior Read

**What happened:** Used `touch` via Bash to create `backend/app/api/deps.py`, then immediately tried to write content to it with the Write tool. The Write tool rejected the call because the file had not been read in the current session, even though it was empty.

**Lesson:** After creating an empty file with Bash (`touch`), either use Bash to write its content directly, or call Read on it first before using the Write tool. The Write tool requires a prior Read regardless of whether the file is empty.

## 2026-04-05 — pydantic-settings v2 silently fails list[str] env vars parsed from .env

**What happened:** Declared `FRONTEND_URLS: list[str]` in a pydantic-settings `BaseSettings` class with a `field_validator(mode="before")` to handle comma-separated strings. pydantic-settings v2 attempts JSON-decode on complex fields *before* calling validators; a plain URL string fails JSON parsing and raises `SettingsError` before the validator ever runs.

**Lesson:** For `list[str]` fields read from `.env` in pydantic-settings v2, declare them as `str` (e.g. `FRONTEND_URLS_RAW: str`) and expose the parsed list via a `@property`. The `field_validator(mode="before")` approach only works for values that are already valid JSON arrays (`["a","b"]`).

## 2026-04-05 — .env field name not updated after renaming Settings field

**What happened:** Renamed `FRONTEND_URLS` to `FRONTEND_URLS_RAW` in `app/core/config.py` to work around the pydantic-settings list issue, but left `FRONTEND_URLS=http://localhost:5173` in `.env`. pydantic-settings raised "Extra inputs are not permitted" because the old key no longer matched any field.

**Lesson:** When renaming a `BaseSettings` field, immediately update all `.env`, `.env.example`, and any CI/CD environment variable declarations to use the new name. The two artefacts are coupled and must stay in sync.

## 2026-04-05 — Svelte 5 runes mode: `afterUpdate` is not importable

**What happened:** Imported `afterUpdate` from `svelte` in `ChatPanel.svelte` for auto-scroll. Svelte 5 runes mode forbids `afterUpdate`; svelte-check raised `runes_mode_invalid_import`.

**Lesson:** In Svelte 5 runes mode (`"svelte": "^5.x"` with runes syntax), `afterUpdate`, `beforeUpdate`, and `onMount`/`onDestroy`-based lifecycle hooks from svelte are replaced by `$effect`. Use `$effect(() => { ... })` for any side effect that should re-run on state change, with `setTimeout(..., 0)` if DOM measurement is needed after paint.

## 2026-04-05 — @xyflow/svelte v1.5.2 events are props, not `on:` directives

**What happened:** Used Svelte 4 `on:nodedragstop`, `on:nodeclick`, `on:paneclick`, `on:nodesdelete`, `on:edgesdelete` directives and imported `NodeDragEvent`/`NodeMouseEvent` types that don't exist in @xyflow/svelte v1.5.2. All failed type-checking in Svelte 5 runes mode.

**Lesson:** @xyflow/svelte v1.5.2 targets Svelte 5 runes mode. Events are passed as props: `onnodedragstop`, `onnodeclick`, `onpaneclick`, `ondelete`. The delete handler is `ondelete: ({nodes, edges}) => void` — there are no separate `nodesdelete`/`edgesdelete` events. Do not import event types from `@xyflow/svelte`; inline the parameter shapes instead.

## 2026-04-05 — Svelte `<!-- svelte-ignore -->` comment placed inside an element's attribute list

**What happened:** Wrote `<!-- svelte-ignore a11y_autofocus -->` as a line inside the opening `<input ... >` tag (between attributes). Svelte's compiler treated it as an invalid attribute name and raised a compile error.

**Lesson:** `<!-- svelte-ignore ... -->` must appear on its own line *immediately before* the element's opening tag, outside the tag itself. It cannot appear between attributes inside the tag.

## 2026-04-05 — Nested `<button>` inside `<button>` is invalid HTML

**What happened:** Built session cards as `<button onclick={navigate}>` elements containing a nested `<button onclick={delete}>` for the delete action. Svelte raised `node_invalid_placement` because the browser repairs this by moving or removing elements, breaking event delegation.

**Lesson:** Interactive card patterns that need nested clickable controls cannot use `<button>` for the outer container. Use `<div role="button" tabindex="0">` for the outer element and reserve `<button>` for the inner controls. Add both `onclick` and `onkeydown` (Enter key) to the div for accessibility.
