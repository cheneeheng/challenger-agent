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
