---
doc: 04_LIBRARIES_AND_FRAMEWORKS
status: ready
version: 1
created: 2026-04-18
scope: Full dependency list (frontend A React, frontend B SvelteKit, backend, dev tooling) with versions, rationale, and rejected libraries
relates_to:
  - 01_PROJECT_PLAN
  - 03_ARCHITECTURE
  - 06_BACKEND_IMPLEMENTATION
  - 07_FRONTEND_IMPLEMENTATION
  - 07_FRONTEND_IMPLEMENTATION_SVELTE
---
# LIBRARIES & FRAMEWORKS — IdeaLens
**Stack:** React 19 + Vite · SvelteKit · TypeScript · Python 3.12 · FastAPI · PostgreSQL · SQLAlchemy 2.x async · Anthropic SDK

> Two frontend implementations share one backend. Each frontend has its own dependency set.
> Both are built and kept in sync; only one is deployed to production at a time.
> React version details: 07_FRONTEND_IMPLEMENTATION.md
> SvelteKit version details: 07_FRONTEND_IMPLEMENTATION_SVELTE.md

---

## FRONTEND A — React + Vite (`/apps/web-react`) — TypeScript

### Core
| Library | Version | Purpose |
|---|---|---|
| `react` | ^19.x | UI framework |
| `react-dom` | ^19.x | DOM rendering |
| `vite` | ^6.x | Build tool and dev server |
| `typescript` | ^5.x | Type safety |

### Routing
| Library | Version | Purpose |
|---|---|---|
| `react-router-dom` | ^7.x | Client-side routing; `ProtectedRoute`, `ApiKeyGuard` wrappers |

### State Management
| Library | Version | Purpose |
|---|---|---|
| `zustand` | ^5.x | Global state: auth (persisted), chat, graph, sessions |
| `immer` | ^10.x | Immutable state mutations in graphStore |

### Data Fetching
| Library | Version | Purpose |
|---|---|---|
| `axios` | ^1.x | HTTP client; Bearer injection + 401 auto-refresh interceptors |
| `@tanstack/react-query` | ^5.x | Server state, caching, loading/error states for REST calls |

### Node Graph Visualization
| Library | Version | Purpose |
|---|---|---|
| `@xyflow/react` | ^12.x | Interactive node graph (React Flow); controlled via graphStore |
| `@dagrejs/dagre` | ^1.x | Directed graph auto-layout for initial render |

### Layout
| Library | Version | Purpose |
|---|---|---|
| `react-resizable-panels` | ^2.x | Resizable split panel between chat and graph |

### UI Components & Styling
| Library | Version | Purpose |
|---|---|---|
| `tailwindcss` | ^4.x | Utility-first CSS |
| `@radix-ui/react-dialog` | latest | NewAnalysis modal, delete confirmation modal |
| `@radix-ui/react-dropdown-menu` | latest | User avatar menu |
| `@radix-ui/react-tooltip` | latest | Node hover tooltips |
| `@radix-ui/react-context-menu` | latest | Node right-click menu |
| `@radix-ui/react-select` | latest | Model selector, DimensionType selector |
| `class-variance-authority` | ^0.7.x | Variant-based component styling |
| `clsx` | ^2.x | Conditional classnames |
| `tailwind-merge` | ^2.x | Conflict-free Tailwind class merging |
| `lucide-react` | ^0.400.x | Icons (one per DimensionType + UI icons) |
| `sonner` | ^1.x | Toast notifications |

### Forms & Validation
| Library | Version | Purpose |
|---|---|---|
| `react-hook-form` | ^7.x | Form state management |
| `zod` | ^3.x | Schema validation — mirrors Pydantic backend models |
| `@hookform/resolvers` | ^3.x | Connects Zod schemas to React Hook Form |

### Animation
| Library | Version | Purpose |
|---|---|---|
| `motion` | ^11.x | Node transitions, panel animations |

### Utilities
| Library | Version | Purpose |
|---|---|---|
| `date-fns` | ^3.x | Session timestamp formatting (relative time) |
| `uuid` | ^9.x | Client-side unique ID generation for graph nodes and edges |

---

## FRONTEND B — SvelteKit (`/apps/web-svelte`) — TypeScript

### Core
| Library | Version | Purpose |
|---|---|---|
| `svelte` | ^5.x | UI framework |
| `@sveltejs/kit` | ^2.x | Full-stack framework; file-based routing; SPA mode via `ssr = false` |
| `@sveltejs/adapter-node` | ^5.x | Node.js build target (production Docker container) |
| `vite` | ^6.x | Build tool (internal to SvelteKit) |
| `typescript` | ^5.x | Type safety |

### Routing
| Notes | |
|---|---|
| Built into SvelteKit | File-based routing in `src/routes/`; auth guards via `+layout.ts` `load()` functions + `redirect()` — no separate routing library needed |

### State Management
| Library | Version | Purpose |
|---|---|---|
| (built-in) | — | Svelte `writable`, `derived`, `get` from `svelte/store` — replaces Zustand |

### Data Fetching
| Library | Version | Purpose |
|---|---|---|
| `axios` | ^1.x | HTTP client; Bearer injection + 401 auto-refresh interceptors (same logic as React version) |

### Node Graph Visualization
| Library | Version | Purpose |
|---|---|---|
| `@xyflow/svelte` | ^0.1.x | Interactive node graph (Svelte Flow — Svelte port of React Flow); same controlled pattern |
| `@dagrejs/dagre` | ^1.x | Directed graph auto-layout (identical usage to React version) |

### Layout
| Library | Version | Purpose |
|---|---|---|
| `svelte-splitpanes` | ^9.x | Resizable split panel between chat and graph |

### UI Components & Styling
| Library | Version | Purpose |
|---|---|---|
| `tailwindcss` | ^4.x | Utility-first CSS (identical config to React version) |
| `@melt-ui/svelte` | ^0.86.x | Headless accessible UI primitives (Svelte equivalent of Radix UI) |
| `@melt-ui/pp` | latest | Melt UI preprocessor — required for `use:melt` directive |
| `class-variance-authority` | ^0.7.x | Variant-based component styling |
| `clsx` | ^2.x | Conditional classnames |
| `tailwind-merge` | ^2.x | Conflict-free Tailwind class merging |
| `lucide-svelte` | ^0.400.x | Icons (Svelte port of lucide-react — same icon names) |
| `svelte-sonner` | ^0.3.x | Toast notifications (Svelte port of sonner — same API) |

### Forms & Validation
| Library | Version | Purpose |
|---|---|---|
| `sveltekit-superforms` | ^2.x | Form state management with progressive enhancement |
| `zod` | ^3.x | Schema validation — same schemas as React version |

### Animation
| Notes | |
|---|---|
| Built into Svelte | `svelte/transition` (`fly`, `fade`, `scale`) and `svelte/animate` — no additional library needed |

### Utilities
| Library | Version | Purpose |
|---|---|---|
| `date-fns` | ^3.x | Session timestamp formatting (identical to React version) |
| `uuid` | ^9.x | Client-side unique ID generation (identical to React version) |

---

## Shared / Equivalent Libraries — Comparison Table

| Concern | React (web-react) | SvelteKit (web-svelte) |
|---|---|---|
| Framework | `react` + `react-dom` | `svelte` + `@sveltejs/kit` |
| Routing | `react-router-dom` | Built-in (file-based) |
| State | `zustand` + `immer` | `svelte/store` (built-in) |
| Server state | `@tanstack/react-query` | SvelteKit `load()` |
| HTTP client | `axios` | `axios` (identical) |
| Graph library | `@xyflow/react` | `@xyflow/svelte` |
| Layout panels | `react-resizable-panels` | `svelte-splitpanes` |
| Headless UI | `@radix-ui/*` | `@melt-ui/svelte` |
| Forms | `react-hook-form` + `@hookform/resolvers` | `sveltekit-superforms` |
| Validation | `zod` | `zod` (identical schemas) |
| Toasts | `sonner` | `svelte-sonner` |
| Icons | `lucide-react` | `lucide-svelte` |
| Animation | `motion` | `svelte/transition` (built-in) |
| Date utils | `date-fns` | `date-fns` (identical) |
| UUID | `uuid` | `uuid` (identical) |
| Tailwind | `tailwindcss` | `tailwindcss` (identical) |
| Build | `vite` | `vite` (via SvelteKit) |

---

## BACKEND (`/apps/api`) — Python
*Shared by both frontends.*

### Core Framework
| Library | Version | Purpose |
|---|---|---|
| `fastapi` | ^0.115.x | Async web framework; Pydantic-native; auto OpenAPI; StreamingResponse |
| `uvicorn[standard]` | ^0.34.x | ASGI server with uvloop + httptools |
| `python-multipart` | ^0.0.x | Required for FastAPI form/cookie parsing |

### Configuration & Validation
| Library | Version | Purpose |
|---|---|---|
| `pydantic` | ^2.x | Request/response validation; LLM output parsing; discriminated unions |
| `pydantic[email]` | ^2.x | `EmailStr` field type for auth schemas |
| `pydantic-settings` | ^2.x | Type-safe settings loaded from `.env` + environment |

### Database
| Library | Version | Purpose |
|---|---|---|
| `sqlalchemy[asyncio]` | ^2.x | Async ORM; `Mapped` columns; `onupdate=func.now()` |
| `asyncpg` | ^0.30.x | Async PostgreSQL driver for SQLAlchemy |
| `alembic` | ^1.x | Schema migrations; must use async `env.py` pattern |

### Authentication
| Library | Version | Purpose |
|---|---|---|
| `python-jose[cryptography]` | ^3.x | JWT HS256 encode/decode |
| `passlib[bcrypt]` | ^1.x | Password hashing and verification |

### Encryption
| Library | Version | Purpose |
|---|---|---|
| `cryptography` | ^44.x | `Fernet` symmetric encryption for user API keys at rest |

### LLM Integration
| Library | Version | Purpose |
|---|---|---|
| `anthropic` | ^0.49.x | Official Anthropic SDK; async streaming; used for key validation test call |

### Security & Middleware
| Library | Version | Purpose |
|---|---|---|
| `slowapi` | ^0.1.x | Rate limiting for FastAPI; per-IP for auth; per-user for chat |

### Logging
| Library | Version | Purpose |
|---|---|---|
| `structlog` | ^25.x | Structured JSON logging (prod) / human-readable (dev) |

### Dependency Management
| Tool | Purpose |
|---|---|
| `uv` | Fast Python package manager + virtual env (`uv add`, `uv sync`) |

---

## DEVELOPER TOOLING

### Backend (Python)
| Tool | Version | Purpose |
|---|---|---|
| `pytest` | ^8.x | Test runner |
| `pytest-asyncio` | ^0.25.x | Async test support |
| `httpx` | ^0.28.x | Async FastAPI test client |
| `ruff` | ^0.9.x | Linter + formatter |
| `mypy` | ^1.x | Static type checking |

### Frontend — React (`apps/web-react`)
| Tool | Version | Purpose |
|---|---|---|
| `vitest` | ^3.x | Unit + integration tests |
| `@testing-library/react` | ^16.x | React component testing |
| `@testing-library/user-event` | ^14.x | Simulated user interactions |
| `playwright` | ^1.x | End-to-end browser tests |
| `eslint` | ^9.x | Linting |
| `@typescript-eslint/parser` | ^8.x | TypeScript ESLint rules |
| `prettier` | ^3.x | Code formatting |
| `@types/uuid` | ^9.x | Types for uuid |

### Frontend — SvelteKit (`apps/web-svelte`)
| Tool | Version | Purpose |
|---|---|---|
| `vitest` | ^3.x | Unit + integration tests |
| `@testing-library/svelte` | ^5.x | Svelte component testing |
| `@testing-library/user-event` | ^14.x | Simulated user interactions |
| `playwright` | ^1.x | End-to-end browser tests |
| `svelte-check` | ^3.x | Type checking for `.svelte` files (replaces `tsc --noEmit`) |
| `prettier` + `prettier-plugin-svelte` | ^3.x | Code formatting with Svelte support |
| `@types/uuid` | ^9.x | Types for uuid |

### Both Frontends
| Tool | Version | Purpose |
|---|---|---|
| `husky` | ^9.x | Git hook runner |
| `lint-staged` | ^15.x | Run linters on staged files only |

### Infrastructure
| Tool | Version | Purpose |
|---|---|---|
| `terraform` | ^1.9.x | IaC for all AWS resources |

---

## INFRASTRUCTURE — AWS (v1)

| Service | Config | Purpose |
|---|---|---|
| EC2 | t4g.small (API, runs Docker + Nginx) | Backend container host |
| S3 + CloudFront | 1 bucket, 1 distribution | Frontend static asset hosting + global CDN |
| ECR | 3 repos | `idealens-api`, `idealens-web-react`, `idealens-web-svelte` — both frontend images built and stored; only selected one deployed |
| RDS PostgreSQL 16 | db.t3.micro, 20GB | Managed database (shared by both frontends) |
| ACM | DNS validation | Auto-renewing TLS certificates |
| Secrets Manager | 3 secrets | JWT_SECRET, API_KEY_ENCRYPTION_KEY, DATABASE_URL |
| S3 | 1 bucket | Terraform remote state |
| DynamoDB | 1 table | Terraform state locking |
| IAM | execution + task roles | Secrets Manager read + ECR pull |

---

## DECISION RATIONALE

| Decision | Choice | Reason |
|---|---|---|
| Two frontends, one repo | Monorepo | Backend is fully shared; single CI pipeline with parallel frontend jobs; no config drift between implementations |
| Single frontend in production | `DEPLOY_FRONTEND` variable | Only one web service runs at a time — keeps infra cost and complexity at single-frontend level |
| Frontend ports in dev | React :3000, SvelteKit :3001 | Both run simultaneously in local dev for side-by-side comparison; port collision avoided |
| Both images in ECR | Yes | Both are built and stored regardless of which is active; switching is a deploy-only operation with no rebuild required |
| Production port | 80 for both | React via nginx; SvelteKit via `PORT=80` on adapter-node — unchanged when switching |
| CORS in dev | Both origins in `allow_origins` | Backend must accept requests from both local ports |
| CORS in production | Single deployed origin only | Only one frontend is live; no need to expose both |
| SvelteKit mode | SPA (`ssr = false`) | Matches React SPA behaviour; no SSR complexity; auth guard logic stays client-side |
| SvelteKit adapter | `adapter-node` | Runs as a Node server in Docker; same container lifecycle pattern as the React nginx container |
| Auth guards | React: components; SvelteKit: `+layout.ts` load | Idiomatic to each framework while producing identical UX |
| Zod schemas | Identical content in both frontends | Single source of truth for graph schema; copy maintained manually or via shared package |
| Graph flow library | `@xyflow/react` / `@xyflow/svelte` | Same underlying library family; same controlled pattern; comparable API surface |
| State management | Zustand (React) / writable (SvelteKit) | Idiomatic to each framework; store shapes and method names kept parallel for easy comparison |
| IaC | Terraform | Cloud-agnostic; enables GCP v2 |
| LLM gateway | None — direct Anthropic SDK | LiteLLM had critical supply chain attack (March 2026) |
| Context management | Last 20 + Haiku summary | Haiku cheapest; stored once and reused |
| SSE client | `fetch`-based in both | Same implementation — not framework-dependent |
| message_index | SELECT FOR UPDATE | Prevents concurrent insert collision |
| /docs endpoint | Disabled in production | Prevents API schema exposure |