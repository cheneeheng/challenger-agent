# Frontend

SvelteKit 2 + Svelte 5 (runes), TypeScript strict, TailwindCSS 4, Vite 7. See
the root [README](../README.md) for full development instructions and project
structure.

## Quick reference

```bash
bun install          # install dependencies
bun run dev          # dev server on :5173
bun run build        # production build
bun run preview      # preview production build
bun run check        # svelte-check + tsc
bun run test         # vitest (run once)
bun run test:coverage
```

## Environment

Public env vars live in `frontend/.env.development` and
`frontend/.env.production` alongside `vite.config.ts` — Vite requires this.
See the root [README](../README.md#environment-variables) for the full
variable reference.
