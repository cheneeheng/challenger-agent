# FRONTEND IMPLEMENTATION REFERENCE — SVELTEKIT
> SvelteKit replacement for the React + Vite frontend described in 07_FRONTEND_IMPLEMENTATION.md.
> All functionality is identical. Only the framework, libraries, and implementation patterns differ.
> Claude Code: read this instead of 07_FRONTEND_IMPLEMENTATION.md when building the frontend.
>
> Cross-reference changes vs React version:
>   01_PROJECT_PLAN.md  §1 stack, §3.1–3.12 feature details
>   02_TODOS.md         §1.2–1.4, §1.9–1.14, §3.x, §4.x, §5.x
>   03_ARCHITECTURE.md  §3 repo structure, §10 state architecture
>   04_LIBRARIES_AND_FRAMEWORKS.md  frontend section
>   05_INFRASTRUCTURE_AND_DEPLOYMENT.md  §9 CI frontend job

---

## SVELTE vs REACT — KEY DIFFERENCES TO KEEP IN MIND

| Concern | React version | SvelteKit version |
|---|---|---|
| Routing | react-router-dom v7 | SvelteKit file-based routing (`src/routes/`) |
| State | Zustand + immer | Svelte stores (`writable`, `derived`, custom) |
| Data fetching | @tanstack/react-query | SvelteKit `load()` functions + `fetch` |
| Forms | react-hook-form + Zod | Svelte `use:enhance` + Zod (client) / SuperForms |
| SSE streaming | fetch + manual parser | Same fetch pattern — no change needed |
| Graph | @xyflow/react (React Flow) | `@xyflow/svelte` (Svelte Flow — same API family) |
| Layout | react-resizable-panels | `svelte-splitpanes` |
| Styling | Tailwind v4 | Tailwind v4 (identical) |
| UI components | Radix UI | Melt UI (Svelte-native headless primitives) |
| Animation | motion (framer) | `svelte/transition` + `svelte/animate` (built-in) |
| Toast | sonner | `svelte-sonner` (same API, Svelte port) |
| Icons | lucide-react | `lucide-svelte` |
| Build | Vite (internal to SvelteKit) | Vite (internal to SvelteKit — same) |
| SSR | Not used (Vite SPA) | Disabled globally (`ssr = false`) — SPA mode |
| Auth guard | ProtectedRoute component | `+layout.ts` load function + redirect |

SvelteKit is run in **SPA mode** (`adapter-static` or `adapter-node` with `ssr = false`).
This preserves the same client-side-only behaviour as the React SPA while gaining
SvelteKit's file-based routing and `load()` ergonomics.

---

## 1. Project Bootstrap

```bash
cd apps/web
npm create svelte@latest .
# Choose: SvelteKit → Skeleton project → TypeScript → ESLint + Prettier

npm install

# Core SvelteKit + adapter
npm install -D @sveltejs/adapter-node   # or adapter-static for pure SPA
# Use adapter-node so the Docker container can serve SSR-disabled SvelteKit

# Graph visualization (Svelte Flow — same underlying library as React Flow)
npm install @xyflow/svelte

# Dagre layout (identical to React version)
npm install @dagrejs/dagre
npm install -D @types/dagre

# State + validation
npm install zod

# HTTP client
npm install axios

# UI headless primitives
npm install @melt-ui/svelte @internationalized/date

# Svelte-compatible preprocessor for melt-ui (required)
npm install -D @melt-ui/pp

# Layout split panels
npm install svelte-splitpanes

# Toasts (Svelte port of sonner — identical API)
npm install svelte-sonner

# Icons
npm install lucide-svelte

# Date formatting (identical to React version)
npm install date-fns

# UUID (identical)
npm install uuid
npm install -D @types/uuid

# Tailwind v4
npm install -D tailwindcss @tailwindcss/vite

# Forms: sveltekit-superforms + Zod adapter
npm install sveltekit-superforms zod
# SuperForms gives progressive-enhancement forms with Zod validation,
# replacing react-hook-form + @hookform/resolvers

# Dev tooling
npm install -D vitest @testing-library/svelte @playwright/test
npm install -D prettier prettier-plugin-svelte
npm install -D husky lint-staged
```

`svelte.config.js`:
```javascript
import adapter from '@sveltejs/adapter-node'
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte'
import { preprocessMeltUI, sequence } from '@melt-ui/pp'

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: sequence([vitePreprocess(), preprocessMeltUI()]),
  kit: {
    adapter: adapter(),
  },
}
export default config
```

`vite.config.ts`:
```typescript
import { sveltekit } from '@sveltejs/kit/vite'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [sveltekit(), tailwindcss()],
  server: {
    host: '0.0.0.0',    // required inside Docker
    port: 3000,
    hmr: { host: 'localhost', port: 3000 },
  },
})
```

`src/app.d.ts` (SvelteKit type augmentation):
```typescript
declare global {
  namespace App {
    interface Locals {
      user: { id: string; email: string; name: string; has_api_key: boolean } | null
    }
  }
}
export {}
```

---

## 2. Environment Config (`src/lib/config.ts`)

Replaces `src/config.ts` in the React version. SvelteKit uses `$env/static/public` for
public env vars (prefix `PUBLIC_`). The `VITE_API_URL` variable is renamed `PUBLIC_API_URL`.

```typescript
// src/lib/config.ts
import { PUBLIC_API_URL } from '$env/static/public'

export const API_BASE_URL: string = PUBLIC_API_URL ?? ''
// Dev  → 'http://localhost:8000'  (cross-origin; FastAPI CORS handles it)
// Prod → ''  (same-origin; nginx proxies /api/ and /auth/ to api container)
```

`.env.development`:
```
PUBLIC_API_URL=http://localhost:8000
```

`.env.production`:
```
PUBLIC_API_URL=
```

Update `apps/api/.env.example` reference:  `FRONTEND_URL=http://localhost:3000` — unchanged.

---

## 3. SPA Mode — Disable SSR Globally

Create `src/routes/+layout.ts` to disable SSR across the entire app:

```typescript
// src/routes/+layout.ts
export const ssr = false
export const prerender = false
```

This makes SvelteKit behave identically to the React SPA. All data loading happens
client-side. There is no server-side rendering.

---

## 4. File-Based Route Structure

SvelteKit uses the filesystem as the router. The equivalent of the React router is:

```
src/routes/
├── +layout.ts               # ssr = false (global)
├── +layout.svelte            # QueryClient, Toaster, auth init
├── login/
│   └── +page.svelte          # /login
├── register/
│   └── +page.svelte          # /register
├── (protected)/              # route group — shares auth guard layout
│   ├── +layout.ts            # load() — redirect to /login if no token
│   ├── settings/
│   │   └── +page.svelte      # /settings  (accessible without API key)
│   └── (requires-api-key)/   # nested route group
│       ├── +layout.ts        # load() — redirect to /settings if no api key
│       ├── +page.svelte      # / (Dashboard)
│       └── session/
│           └── [id]/
│               └── +page.svelte   # /session/:id
```

**Auth guard via load functions** (replaces React `ProtectedRoute` and `ApiKeyGuard`):

```typescript
// src/routes/(protected)/+layout.ts
import { redirect } from '@sveltejs/kit'
import { get } from 'svelte/store'
import { authStore } from '$lib/stores/authStore'

export const ssr = false

export function load() {
  const { user, accessToken } = get(authStore)
  if (!user || !accessToken) {
    throw redirect(302, '/login')
  }
}
```

```typescript
// src/routes/(protected)/(requires-api-key)/+layout.ts
import { redirect } from '@sveltejs/kit'
import { get } from 'svelte/store'
import { authStore } from '$lib/stores/authStore'

export const ssr = false

export function load() {
  const { user } = get(authStore)
  if (!user?.has_api_key) {
    throw redirect(302, '/settings?prompt=api-key')
  }
}
```

---

## 5. Root Layout (`src/routes/+layout.svelte`)

Replaces `src/main.tsx` + `src/App.tsx`:

```svelte
<!-- src/routes/+layout.svelte -->
<script lang="ts">
  import { Toaster } from 'svelte-sonner'
  import { onMount } from 'svelte'
  import { authStore } from '$lib/stores/authStore'
  import '../app.css'

  // Rehydrate auth from localStorage on mount (SPA mode — no SSR)
  onMount(() => {
    authStore.init()
  })
</script>

<slot />
<Toaster position="bottom-right" richColors />
```

---

## 6. Axios Instance (`src/lib/services/api.ts`)

Identical to the React version — no Svelte-specific changes needed. Axios works the same.

```typescript
// src/lib/services/api.ts
import axios from 'axios'
import { API_BASE_URL } from '$lib/config'
import { authStore } from '$lib/stores/authStore'
import { get } from 'svelte/store'
import { goto } from '$app/navigation'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
})

// Inject access token on every request
apiClient.interceptors.request.use((config) => {
  const { accessToken } = get(authStore)
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})

// Auto-refresh on 401
let isRefreshing = false
let queue: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = []

apiClient.interceptors.response.use(
  res => res,
  async (error) => {
    const original = error.config
    if (error.response?.status !== 401 || original._retry) return Promise.reject(error)

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        queue.push({
          resolve: (token) => {
            original.headers.Authorization = `Bearer ${token}`
            resolve(apiClient(original))
          },
          reject,
        })
      })
    }

    original._retry = true
    isRefreshing = true
    try {
      const resp = await apiClient.post('/auth/refresh')
      const token = resp.data.access_token
      authStore.setAccessToken(token)
      queue.forEach(q => q.resolve(token))
      queue = []
      original.headers.Authorization = `Bearer ${token}`
      return apiClient(original)
    } catch (e) {
      queue.forEach(q => q.reject(e))
      queue = []
      authStore.logout()
      goto('/login')
      return Promise.reject(e)
    } finally {
      isRefreshing = false
    }
  }
)
```

Note: `goto('/login')` replaces `window.location.href = '/login'` — SvelteKit's
programmatic navigation function.

---

## 7. SSE Chat Service (`src/lib/services/chatService.ts`)

**Identical to the React version.** The raw `fetch`-based SSE implementation does not
depend on any React APIs. Copy it verbatim with these two substitutions:

- `import { API_BASE_URL } from '../config'`
  → `import { API_BASE_URL } from '$lib/config'`
- `import { useAuthStore } from '../stores/authStore'`
  → `import { authStore } from '$lib/stores/authStore'; import { get } from 'svelte/store'`
- All `useAuthStore.getState().accessToken`
  → `get(authStore).accessToken`

```typescript
// src/lib/services/chatService.ts
import { API_BASE_URL } from '$lib/config'
import { authStore } from '$lib/stores/authStore'
import { get } from 'svelte/store'
import { LLMGraphActionSchema } from '$lib/schemas/graph'
import type { LLMGraphAction } from '$lib/schemas/graph'

export interface StreamCallbacks {
  onToken: (chunk: string) => void
  onGraphAction: (action: LLMGraphAction) => void
  onError: (msg: string) => void
  onDone: () => void
}

async function _doStream(
  body: { session_id: string; message: string; graph_state: object; model: string },
  callbacks: StreamCallbacks,
  signal: AbortSignal,
  lastEventId?: string,
): Promise<void> {
  const token = get(authStore).accessToken
  const resp = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    signal,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(lastEventId ? { 'Last-Event-ID': lastEventId } : {}),
    },
    body: JSON.stringify(body),
  })

  if (!resp.ok) { callbacks.onError(`Request failed: ${resp.status}`); callbacks.onDone(); return }

  const reader = resp.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''

    for (const part of parts) {
      if (!part.trim()) continue
      let eventType = 'message', data = '', id = ''
      for (const line of part.split('\n')) {
        if (line.startsWith('event: ')) eventType = line.slice(7).trim()
        else if (line.startsWith('data: ')) data = line.slice(6)
        else if (line.startsWith('id: ')) id = line.slice(4).trim()
      }

      if (eventType === 'token') callbacks.onToken(data)
      else if (eventType === 'graph_action') {
        try {
          const validated = LLMGraphActionSchema.parse(JSON.parse(data))
          callbacks.onGraphAction(validated)
        } catch { console.warn('Invalid graph_action received:', data) }
      }
      else if (eventType === 'error') callbacks.onError(data)
      else if (eventType === 'done') { callbacks.onDone(); return }
    }
  }
}

export async function streamChat(
  body: Parameters<typeof _doStream>[0],
  callbacks: StreamCallbacks,
): Promise<() => void> {
  const controller = new AbortController()
  let lastEventId: string | undefined

  ;(async () => {
    try {
      await _doStream(body, callbacks, controller.signal, lastEventId)
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') return
      await new Promise(r => setTimeout(r, 2000))
      try {
        await _doStream(body, callbacks, controller.signal, lastEventId)
      } catch {
        callbacks.onError('Connection lost. Please try again.')
        callbacks.onDone()
      }
    }
  })()

  return () => controller.abort()
}
```

---

## 8. Svelte Stores (replacing Zustand)

Svelte's built-in `writable` store replaces Zustand. The API is different but the shape
and semantics of each store are preserved exactly.

### `src/lib/stores/authStore.ts`

```typescript
import { writable, derived, get } from 'svelte/store'

interface User { id: string; email: string; name: string; has_api_key: boolean }

interface AuthState {
  user: User | null
  accessToken: string | null
}

function createAuthStore() {
  const { subscribe, set, update } = writable<AuthState>({ user: null, accessToken: null })

  return {
    subscribe,
    /** Call once on app mount to rehydrate from localStorage */
    init() {
      const raw = localStorage.getItem('auth')
      if (raw) {
        try { set(JSON.parse(raw)) } catch { /* ignore */ }
      }
    },
    setUser(user: User) {
      update(s => {
        const next = { ...s, user }
        localStorage.setItem('auth', JSON.stringify(next))
        return next
      })
    },
    setAccessToken(accessToken: string) {
      update(s => {
        const next = { ...s, accessToken }
        localStorage.setItem('auth', JSON.stringify(next))
        return next
      })
    },
    updateUser(patch: Partial<User>) {
      update(s => {
        const next = { ...s, user: s.user ? { ...s.user, ...patch } : null }
        localStorage.setItem('auth', JSON.stringify(next))
        return next
      })
    },
    logout() {
      set({ user: null, accessToken: null })
      localStorage.removeItem('auth')
    },
  }
}

export const authStore = createAuthStore()

// Derived helpers — use in components via $hasApiKey
export const currentUser = derived(authStore, $s => $s.user)
export const hasApiKey   = derived(authStore, $s => $s.user?.has_api_key ?? false)
```

### `src/lib/stores/chatStore.ts`

```typescript
import { writable } from 'svelte/store'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  isStreaming?: boolean
  error?: string
}

interface ChatState {
  messages: ChatMessage[]
  isStreaming: boolean
  error: string | null
}

function createChatStore() {
  const { subscribe, set, update } = writable<ChatState>({
    messages: [], isStreaming: false, error: null,
  })

  return {
    subscribe,
    addMessage: (m: ChatMessage) =>
      update(s => ({ ...s, messages: [...s.messages, m] })),
    appendToken: (id: string, chunk: string) =>
      update(s => ({
        ...s,
        messages: s.messages.map(m =>
          m.id === id ? { ...m, content: m.content + chunk } : m
        ),
      })),
    finalizeMessage: (id: string) =>
      update(s => ({
        ...s,
        isStreaming: false,
        messages: s.messages.map(m =>
          m.id === id ? { ...m, isStreaming: false } : m
        ),
      })),
    setError: (error: string | null) => update(s => ({ ...s, error })),
    setStreaming: (isStreaming: boolean) => update(s => ({ ...s, isStreaming })),
    setMessages: (messages: ChatMessage[]) => update(s => ({ ...s, messages })),
    clear: () => set({ messages: [], isStreaming: false, error: null }),
  }
}

export const chatStore = createChatStore()
```

### `src/lib/stores/graphStore.ts`

Svelte doesn't have immer middleware, but Svelte's reactivity handles immutable-style
updates. The store shape and all methods are identical to the React/Zustand version.

```typescript
import { writable, get } from 'svelte/store'
import { v4 as uuidv4 } from 'uuid'
import type { AnalysisNode, AnalysisEdge, LLMGraphAction } from '$lib/schemas/graph'
import { getIncrementalPosition } from '$lib/utils/graphLayout'

interface GraphState {
  nodes: AnalysisNode[]
  edges: AnalysisEdge[]
  selectedNodeId: string | null
}

function createGraphStore() {
  const { subscribe, set, update } = writable<GraphState>({
    nodes: [], edges: [], selectedNodeId: null,
  })

  return {
    subscribe,
    setGraph: (nodes: AnalysisNode[], edges: AnalysisEdge[]) =>
      set({ nodes, edges, selectedNodeId: null }),

    applyGraphActions: (actions: LLMGraphAction[]) =>
      update(state => {
        let { nodes, edges } = state
        for (const action of actions) {
          if (action.action === 'add') {
            const position = getIncrementalPosition(nodes, action.payload.parent_id ?? undefined)
            nodes = [...nodes, { ...action.payload, position, userPositioned: false }]
          } else if (action.action === 'update') {
            nodes = nodes.map(n => {
              if (n.id !== action.payload.id) return n
              // Preserve user-dragged position
              const { position: _p, userPositioned: _u, ...rest } = action.payload as Partial<AnalysisNode>
              return { ...n, ...rest }
            })
          } else if (action.action === 'delete') {
            nodes = nodes.filter(n => n.id !== action.payload.id)
            edges = edges.filter(e =>
              e.source !== action.payload.id && e.target !== action.payload.id
            )
          } else if (action.action === 'connect') {
            edges = [...edges, { id: uuidv4(), ...action.payload }]
          }
        }
        return { ...state, nodes, edges }
      }),

    addNode: (payload: Omit<AnalysisNode, 'position' | 'userPositioned'>) =>
      update(s => {
        const position = getIncrementalPosition(s.nodes)
        return { ...s, nodes: [...s.nodes, { ...payload, position, userPositioned: false }] }
      }),

    updateNode: (id: string, patch: Partial<AnalysisNode>) =>
      update(s => ({
        ...s, nodes: s.nodes.map(n => n.id === id ? { ...n, ...patch } : n),
      })),

    deleteNode: (id: string) =>
      update(s => ({
        ...s,
        nodes: s.nodes.filter(n => n.id !== id),
        edges: s.edges.filter(e => e.source !== id && e.target !== id),
        selectedNodeId: s.selectedNodeId === id ? null : s.selectedNodeId,
      })),

    addEdge: (edge: Omit<AnalysisEdge, 'id'>) =>
      update(s => ({ ...s, edges: [...s.edges, { id: uuidv4(), ...edge }] })),

    deleteEdge: (id: string) =>
      update(s => ({ ...s, edges: s.edges.filter(e => e.id !== id) })),

    setNodePosition: (id: string, pos: { x: number; y: number }) =>
      update(s => ({
        ...s,
        nodes: s.nodes.map(n => n.id === id ? { ...n, position: pos, userPositioned: true } : n),
      })),

    setSelectedNodeId: (id: string | null) =>
      update(s => ({ ...s, selectedNodeId: id })),

    clearGraph: () => set({ nodes: [], edges: [], selectedNodeId: null }),

    /** Read current state synchronously (for use outside reactive context) */
    getSnapshot: () => get({ subscribe }),
  }
}

export const graphStore = createGraphStore()
```

### `src/lib/stores/sessionStore.ts`

```typescript
import { writable, get } from 'svelte/store'
import { apiClient } from '$lib/services/api'
import { graphStore } from './graphStore'
import { chatStore } from './chatStore'
import { debounce } from '$lib/utils/debounce'

export interface SessionListItem {
  id: string; name: string; idea: string; selected_model: string; updated_at: string
}

interface SessionState {
  sessions: SessionListItem[]
  currentSessionId: string | null
  currentSession: { id: string; name: string; idea: string; selected_model: string } | null
  selectedModel: string
  isLoading: boolean
  error: string | null
}

const _persistGraph = debounce(async (sessionId: string) => {
  const { nodes, edges } = graphStore.getSnapshot()
  await apiClient.put(`/api/sessions/${sessionId}/graph`, { graph_state: { nodes, edges } })
}, 1000)

function createSessionStore() {
  const { subscribe, set, update } = writable<SessionState>({
    sessions: [], currentSessionId: null, currentSession: null,
    selectedModel: 'claude-sonnet-4-6', isLoading: false, error: null,
  })

  return {
    subscribe,
    fetchSessions: async () => {
      update(s => ({ ...s, isLoading: true, error: null }))
      try {
        const resp = await apiClient.get('/api/sessions?page=1&limit=20')
        update(s => ({ ...s, sessions: resp.data.items }))
      } catch {
        update(s => ({ ...s, error: 'Failed to load sessions' }))
      } finally {
        update(s => ({ ...s, isLoading: false }))
      }
    },
    createSession: async (idea: string, model: string): Promise<string> => {
      const resp = await apiClient.post('/api/sessions', { idea, selected_model: model })
      const session = resp.data
      update(s => ({
        ...s,
        sessions: [session, ...s.sessions],
        currentSessionId: session.id,
        selectedModel: model,
      }))
      return session.id
    },
    loadSession: async (id: string) => {
      update(s => ({ ...s, isLoading: true, error: null }))
      try {
        const resp = await apiClient.get(`/api/sessions/${id}`)
        const session = resp.data
        update(s => ({
          ...s,
          currentSessionId: id,
          currentSession: {
            id: session.id, name: session.name,
            idea: session.idea, selected_model: session.selected_model,
          },
          selectedModel: session.selected_model,
        }))
        graphStore.setGraph(session.graph_state.nodes, session.graph_state.edges)
        chatStore.setMessages(
          session.messages.map((m: { id: string; role: 'user'|'assistant'|'system'; content: string }) =>
            ({ id: m.id, role: m.role, content: m.content })
          )
        )
      } catch (e: unknown) {
        const status = (e as { response?: { status: number } }).response?.status
        update(s => ({
          ...s,
          error: status === 403 ? 'Access denied' : 'Session not found',
        }))
      } finally {
        update(s => ({ ...s, isLoading: false }))
      }
    },
    saveGraph: () => {
      const { currentSessionId } = get({ subscribe })
      if (currentSessionId) _persistGraph(currentSessionId)
    },
    updateSession: async (id: string, patch: { name?: string; selected_model?: string }) => {
      await apiClient.patch(`/api/sessions/${id}`, patch)
      update(s => ({
        ...s,
        sessions: s.sessions.map(sess => sess.id === id ? { ...sess, ...patch } : sess),
      }))
    },
    deleteSession: async (id: string) => {
      await apiClient.delete(`/api/sessions/${id}`)
      update(s => ({
        ...s,
        sessions: s.sessions.filter(sess => sess.id !== id),
        currentSessionId: s.currentSessionId === id ? null : s.currentSessionId,
      }))
    },
    setSelectedModel: (model: string) => update(s => ({ ...s, selectedModel: model })),
    getSnapshot: () => get({ subscribe }),
  }
}

export const sessionStore = createSessionStore()
```

---

## 9. Graph Schemas (`src/lib/schemas/graph.ts`)

**Identical to the React version** — Zod works the same in Svelte. Only the import path
alias changes from `../schemas/graph` to `$lib/schemas/graph`.

```typescript
// src/lib/schemas/graph.ts
import { z } from 'zod'

export const DimensionTypeSchema = z.enum([
  'root','concept','requirement','gap','benefit',
  'drawback','feasibility','flaw','alternative','question'
])

export const EdgeTypeSchema = z.enum(['supports','contradicts','requires','leads_to'])

export const NodePayloadSchema = z.object({
  id: z.string(),
  type: DimensionTypeSchema,
  label: z.string(),
  content: z.string(),
  score: z.number().min(0).max(10).nullable().optional(),
  parent_id: z.string().nullable().optional(),
})

export const AnalysisNodeSchema = NodePayloadSchema.extend({
  position: z.object({ x: z.number(), y: z.number() }).default({ x: 0, y: 0 }),
  userPositioned: z.boolean().default(false),
})

export const AnalysisEdgeSchema = z.object({
  id: z.string(),
  source: z.string(),
  target: z.string(),
  label: z.string().optional(),
  type: EdgeTypeSchema.optional(),
})

export const LLMGraphActionSchema = z.discriminatedUnion('action', [
  z.object({ action: z.literal('add'),     payload: NodePayloadSchema }),
  z.object({ action: z.literal('update'),  payload: z.object({ id: z.string() }).passthrough() }),
  z.object({ action: z.literal('delete'),  payload: z.object({ id: z.string() }) }),
  z.object({ action: z.literal('connect'), payload: AnalysisEdgeSchema }),
])

export type DimensionType   = z.infer<typeof DimensionTypeSchema>
export type NodePayload     = z.infer<typeof NodePayloadSchema>
export type AnalysisNode    = z.infer<typeof AnalysisNodeSchema>
export type AnalysisEdge    = z.infer<typeof AnalysisEdgeSchema>
export type LLMGraphAction  = z.infer<typeof LLMGraphActionSchema>
```

---

## 10. Graph Layout Utils (`src/lib/utils/`)

**Identical to the React version.** Only import path aliases change.

```typescript
// src/lib/utils/graphLayout.ts
import Dagre from '@dagrejs/dagre'
import type { AnalysisNode, AnalysisEdge } from '$lib/schemas/graph'

const W = 220, H = 90

export function layoutGraph(nodes: AnalysisNode[], edges: AnalysisEdge[]): AnalysisNode[] {
  const g = new Dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'TB', nodesep: 60, ranksep: 100 })
  nodes.forEach(n => g.setNode(n.id, { width: W, height: H }))
  edges.forEach(e => g.setEdge(e.source, e.target))
  Dagre.layout(g)
  return nodes.map(n => {
    const pos = g.node(n.id)
    return { ...n, position: { x: pos.x - W / 2, y: pos.y - H / 2 } }
  })
}

export function getIncrementalPosition(
  existingNodes: AnalysisNode[],
  parentId?: string
): { x: number; y: number } {
  if (existingNodes.length === 0) return { x: 400, y: 300 }
  if (parentId) {
    const parent = existingNodes.find(n => n.id === parentId)
    if (parent?.position) {
      const siblings = existingNodes.filter(n => n.parent_id === parentId).length
      return { x: parent.position.x + 250, y: parent.position.y + siblings * 110 }
    }
  }
  const maxY = Math.max(...existingNodes.map(n => n.position.y))
  const avgX = existingNodes.reduce((s, n) => s + n.position.x, 0) / existingNodes.length
  return { x: avgX, y: maxY + 130 }
}
```

```typescript
// src/lib/utils/graphStyles.ts
import type { DimensionType } from '$lib/schemas/graph'

export interface DimensionStyle {
  bgClass: string; borderClass: string; textClass: string; label: string; icon: string
}

export const DIMENSION_STYLES: Record<DimensionType, DimensionStyle> = {
  root:        { bgClass: 'bg-slate-800', borderClass: 'border-slate-600', textClass: 'text-white',       label: 'Idea',          icon: 'Lightbulb' },
  concept:     { bgClass: 'bg-blue-50',   borderClass: 'border-blue-400',  textClass: 'text-blue-900',    label: 'Concept',       icon: 'BookOpen' },
  requirement: { bgClass: 'bg-purple-50', borderClass: 'border-purple-400',textClass: 'text-purple-900',  label: 'Requirement',   icon: 'ClipboardList' },
  gap:         { bgClass: 'bg-yellow-50', borderClass: 'border-yellow-400',textClass: 'text-yellow-900',  label: 'Gap',           icon: 'AlertCircle' },
  benefit:     { bgClass: 'bg-green-50',  borderClass: 'border-green-400', textClass: 'text-green-900',   label: 'Benefit',       icon: 'TrendingUp' },
  drawback:    { bgClass: 'bg-red-50',    borderClass: 'border-red-400',   textClass: 'text-red-900',     label: 'Drawback',      icon: 'TrendingDown' },
  feasibility: { bgClass: 'bg-indigo-50', borderClass: 'border-indigo-400',textClass: 'text-indigo-900',  label: 'Feasibility',   icon: 'BarChart2' },
  flaw:        { bgClass: 'bg-orange-50', borderClass: 'border-orange-400',textClass: 'text-orange-900',  label: 'Flaw',          icon: 'XOctagon' },
  alternative: { bgClass: 'bg-teal-50',   borderClass: 'border-teal-400',  textClass: 'text-teal-900',    label: 'Alternative',   icon: 'GitBranch' },
  question:    { bgClass: 'bg-gray-50',   borderClass: 'border-gray-400',  textClass: 'text-gray-900',    label: 'Question',      icon: 'HelpCircle' },
}
```

```typescript
// src/lib/utils/graphGuards.ts
import type { AnalysisNode, AnalysisEdge } from '$lib/schemas/graph'
export const NODE_WARN  = 150
export const NODE_LIMIT = 200
export const EDGE_LIMIT = 400
export const isGraphNearLimit = (nodes: AnalysisNode[]) => nodes.length >= NODE_WARN
export const isGraphAtLimit   = (nodes: AnalysisNode[], edges: AnalysisEdge[]) =>
  nodes.length >= NODE_LIMIT || edges.length >= EDGE_LIMIT
```

```typescript
// src/lib/utils/debounce.ts
export function debounce<T extends (...args: Parameters<T>) => void>(fn: T, ms: number): T {
  let tid: ReturnType<typeof setTimeout>
  return ((...args: Parameters<T>) => {
    clearTimeout(tid)
    tid = setTimeout(() => fn(...args), ms)
  }) as T
}
```

---

## 11. Graph Panel — Svelte Flow (`src/lib/components/graph/GraphPanel.svelte`)

`@xyflow/svelte` (Svelte Flow) is the official Svelte port of React Flow. The API is nearly
identical. Custom node types are registered the same way. The controlled pattern from the
React version is preserved: `graphStore` is the single source of truth.

```svelte
<!-- src/lib/components/graph/GraphPanel.svelte -->
<script lang="ts">
  import { SvelteFlow, Background, Controls, MiniMap, type Node, type Edge } from '@xyflow/svelte'
  import '@xyflow/svelte/dist/style.css'
  import { derived } from 'svelte/store'
  import { graphStore } from '$lib/stores/graphStore'
  import { sessionStore } from '$lib/stores/sessionStore'
  import AnalysisNodeComponent from './nodes/AnalysisNodeComponent.svelte'
  import GraphToolbar from './GraphToolbar.svelte'
  import NodeDetailPanel from './NodeDetailPanel.svelte'

  // nodeTypes must be defined at module level (same rule as React Flow)
  // In SvelteKit, define outside the component or as a module-level const.
  const nodeTypes = { analysisNode: AnalysisNodeComponent }

  // Derive React-Flow-compatible nodes/edges from graphStore
  const rfNodes = derived(graphStore, $g =>
    $g.nodes.map(n => ({
      id: n.id,
      type: 'analysisNode',
      position: n.position,
      data: n,
      selected: n.id === $g.selectedNodeId,
    }) satisfies Node)
  )

  const rfEdges = derived(graphStore, $g =>
    $g.edges.map(e => ({
      id: e.id, source: e.source, target: e.target, label: e.label,
    }) satisfies Edge)
  )

  function handleNodeDragStop(event: CustomEvent<{ node: Node }>) {
    const { node } = event.detail
    graphStore.setNodePosition(node.id, node.position)
    sessionStore.saveGraph()
  }

  function handleNodeClick(event: CustomEvent<{ node: Node }>) {
    graphStore.setSelectedNodeId(event.detail.node.id)
  }

  function handlePaneClick() {
    graphStore.setSelectedNodeId(null)
  }

  function handleNodesDelete(event: CustomEvent<{ nodes: Node[] }>) {
    event.detail.nodes.forEach(n => graphStore.deleteNode(n.id))
  }

  function handleEdgesDelete(event: CustomEvent<{ edges: Edge[] }>) {
    event.detail.edges.forEach(e => graphStore.deleteEdge(e.id))
  }

  $: selectedNodeId = $graphStore.selectedNodeId
</script>

<div class="relative h-full w-full">
  <SvelteFlow
    nodes={$rfNodes}
    edges={$rfEdges}
    {nodeTypes}
    fitView
    on:nodedragstop={handleNodeDragStop}
    on:nodeclick={handleNodeClick}
    on:paneclick={handlePaneClick}
    on:nodesdelete={handleNodesDelete}
    on:edgesdelete={handleEdgesDelete}
  >
    <Background />
    <Controls />
    <MiniMap />
  </SvelteFlow>

  <GraphToolbar />
  {#if selectedNodeId}
    <NodeDetailPanel nodeId={selectedNodeId} />
  {/if}
</div>
```

---

## 12. Split Layout (`src/lib/components/layout/SplitLayout.svelte`)

`svelte-splitpanes` is the Svelte equivalent of `react-resizable-panels`.

```svelte
<!-- src/lib/components/layout/SplitLayout.svelte -->
<script lang="ts">
  import { Splitpanes, Pane } from 'svelte-splitpanes'
</script>

<Splitpanes class="h-full w-full">
  <Pane size={40} minSize={25}>
    <div class="h-full flex flex-col overflow-hidden">
      <slot name="left" />
    </div>
  </Pane>
  <Pane size={60} minSize={30}>
    <div class="h-full relative">
      <slot name="right" />
    </div>
  </Pane>
</Splitpanes>
```

Usage in `+page.svelte`:
```svelte
<SplitLayout>
  <svelte:fragment slot="left"><ChatPanel {sendMessage} /></svelte:fragment>
  <svelte:fragment slot="right"><GraphPanel /></svelte:fragment>
</SplitLayout>
```

---

## 13. Session Page — New Analysis Flow (`src/routes/(protected)/(requires-api-key)/session/[id]/+page.svelte`)

Replaces `src/pages/Session.tsx`. The auto-send guard uses Svelte's `onMount` with a
module-scoped boolean rather than `useRef`.

```svelte
<!-- src/routes/(protected)/(requires-api-key)/session/[id]/+page.svelte -->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import { page } from '$app/stores'
  import { goto } from '$app/navigation'
  import { v4 as uuidv4 } from 'uuid'
  import { toast } from 'svelte-sonner'
  import { sessionStore } from '$lib/stores/sessionStore'
  import { chatStore } from '$lib/stores/chatStore'
  import { graphStore } from '$lib/stores/graphStore'
  import { streamChat } from '$lib/services/chatService'
  import { layoutGraph } from '$lib/utils/graphLayout'
  import { isGraphNearLimit } from '$lib/utils/graphGuards'
  import SplitLayout from '$lib/components/layout/SplitLayout.svelte'
  import ChatPanel from '$lib/components/chat/ChatPanel.svelte'
  import GraphPanel from '$lib/components/graph/GraphPanel.svelte'

  // Reactive session id from URL
  $: sessionId = $page.params.id

  let initialMessageSent = false
  let cancelStream: (() => void) | undefined

  // Load session whenever the id changes (handles navigation between sessions)
  $: if (sessionId) {
    initialMessageSent = false
    sessionStore.loadSession(sessionId)
  }

  // Auto-send idea when a fresh session is loaded
  $: {
    const { isLoading, error, currentSession } = $sessionStore
    const messages = $chatStore.messages

    if (!isLoading && error) {
      toast.error(error)
      goto('/')
    } else if (!isLoading && currentSession && messages.length === 0 && !initialMessageSent) {
      initialMessageSent = true
      sendMessage(currentSession.idea)
    }
  }

  async function sendMessage(text: string) {
    const { isStreaming } = $chatStore
    const { currentSessionId, selectedModel } = $sessionStore
    const { nodes, edges } = $graphStore

    if (isStreaming || !currentSessionId || !text.trim()) return

    const userMsgId = uuidv4()
    chatStore.addMessage({ id: userMsgId, role: 'user', content: text })
    chatStore.setStreaming(true)
    chatStore.setError(null)

    const assistantMsgId = uuidv4()
    chatStore.addMessage({ id: assistantMsgId, role: 'assistant', content: '', isStreaming: true })

    cancelStream = await streamChat(
      {
        session_id: currentSessionId,
        message: text,
        graph_state: { nodes, edges },
        model: selectedModel,
      },
      {
        onToken: (chunk) => chatStore.appendToken(assistantMsgId, chunk),
        onGraphAction: (action) => {
          graphStore.applyGraphActions([action])
          const currentNodes = $graphStore.nodes
          if (currentNodes.length <= 2) {
            const laid = layoutGraph(currentNodes, $graphStore.edges)
            graphStore.setGraph(laid, $graphStore.edges)
          }
          sessionStore.saveGraph()
          if (isGraphNearLimit($graphStore.nodes)) {
            toast.warning('Your graph is getting large. Consider removing unused nodes.')
          }
        },
        onError: (msg) => {
          chatStore.setError(msg)
          toast.error(msg)
        },
        onDone: () => chatStore.finalizeMessage(assistantMsgId),
      }
    )
  }

  onDestroy(() => cancelStream?.())
</script>

{#if $sessionStore.isLoading}
  <div class="h-full flex items-center justify-center">
    <p class="text-muted-foreground animate-pulse">Loading session...</p>
  </div>
{:else}
  <SplitLayout>
    <svelte:fragment slot="left">
      <ChatPanel onSend={sendMessage} />
    </svelte:fragment>
    <svelte:fragment slot="right">
      <GraphPanel />
    </svelte:fragment>
  </SplitLayout>
{/if}
```

---

## 14. Chat Panel (`src/lib/components/chat/ChatPanel.svelte`)

```svelte
<!-- src/lib/components/chat/ChatPanel.svelte -->
<script lang="ts">
  import { chatStore } from '$lib/stores/chatStore'
  import MessageBubble from './MessageBubble.svelte'
  import ChatInput from './ChatInput.svelte'
  import ModelSelector from './ModelSelector.svelte'
  import { afterUpdate, tick } from 'svelte'

  export let onSend: (text: string) => void

  let messagesEl: HTMLDivElement

  afterUpdate(async () => {
    await tick()
    messagesEl?.scrollTo({ top: messagesEl.scrollHeight, behavior: 'smooth' })
  })
</script>

<div class="flex flex-col h-full">
  <!-- Header -->
  <div class="flex items-center justify-between px-4 py-2 border-b">
    <span class="font-semibold text-sm">Chat</span>
    <ModelSelector />
  </div>

  <!-- Messages -->
  <div bind:this={messagesEl} class="flex-1 overflow-y-auto p-4 space-y-3">
    {#if $chatStore.messages.length === 0}
      <p class="text-center text-muted-foreground text-sm mt-12">Describe your idea to begin</p>
    {/if}
    {#each $chatStore.messages as message (message.id)}
      <MessageBubble {message} />
    {/each}
    {#if $chatStore.isStreaming}
      <div class="flex gap-1 px-4">
        <span class="w-2 h-2 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.3s]" />
        <span class="w-2 h-2 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.15s]" />
        <span class="w-2 h-2 rounded-full bg-muted-foreground animate-bounce" />
      </div>
    {/if}
  </div>

  <!-- Input -->
  <ChatInput disabled={$chatStore.isStreaming} {onSend} />
</div>
```

---

## 15. Message Bubble (`src/lib/components/chat/MessageBubble.svelte`)

```svelte
<!-- src/lib/components/chat/MessageBubble.svelte -->
<script lang="ts">
  import type { ChatMessage } from '$lib/stores/chatStore'
  export let message: ChatMessage
</script>

{#if message.role === 'system'}
  <div class="flex justify-center my-1 px-4">
    <span class="text-xs text-muted-foreground italic bg-muted px-2 py-0.5 rounded-full">
      {message.content}
    </span>
  </div>
{:else if message.role === 'user'}
  <div class="flex justify-end">
    <div class="max-w-[80%] rounded-2xl rounded-tr-sm bg-primary text-primary-foreground px-4 py-2 text-sm">
      {message.content}
    </div>
  </div>
{:else}
  <div class="flex gap-2">
    <div class="w-7 h-7 rounded-full bg-muted flex items-center justify-center text-xs font-bold shrink-0">
      AI
    </div>
    <div class="max-w-[80%] rounded-2xl rounded-tl-sm bg-muted px-4 py-2 text-sm whitespace-pre-wrap">
      {message.content}
      {#if message.isStreaming}
        <span class="inline-block w-0.5 h-4 bg-current ml-0.5 animate-pulse" />
      {/if}
    </div>
  </div>
{/if}
```

---

## 16. Forms — SuperForms + Zod (replacing react-hook-form)

SvelteKit SuperForms replaces `react-hook-form` + `@hookform/resolvers`. The Zod schemas
are identical — only the form binding API differs.

Example: Login page (`src/routes/login/+page.svelte`):

```svelte
<!-- src/routes/login/+page.svelte -->
<script lang="ts">
  import { superForm } from 'sveltekit-superforms/client'
  import { zod } from 'sveltekit-superforms/adapters'
  import { z } from 'zod'
  import { goto } from '$app/navigation'
  import { apiClient } from '$lib/services/api'
  import { authStore } from '$lib/stores/authStore'
  import { toast } from 'svelte-sonner'

  const loginSchema = z.object({
    email: z.string().email('Invalid email'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
  })

  // Client-only form — no server action needed (SPA mode)
  const { form, errors, enhance, submitting } = superForm(
    { email: '', password: '' },
    {
      validators: zod(loginSchema),
      SPA: true,
      onUpdate: async ({ form }) => {
        if (!form.valid) return
        try {
          const resp = await apiClient.post('/auth/login', form.data)
          authStore.setUser(resp.data.user)
          authStore.setAccessToken(resp.data.access_token)
          goto('/')
        } catch (e: unknown) {
          const msg = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          toast.error(msg ?? 'Login failed')
        }
      },
    }
  )
</script>

<div class="min-h-screen flex items-center justify-center">
  <form method="POST" use:enhance class="w-full max-w-sm space-y-4 p-6 bg-card rounded-xl shadow">
    <h1 class="text-xl font-bold">Sign in to IdeaLens</h1>

    <div>
      <label class="text-sm font-medium" for="email">Email</label>
      <input id="email" type="email" bind:value={$form.email}
        class="w-full mt-1 px-3 py-2 border rounded-md text-sm" />
      {#if $errors.email}<p class="text-destructive text-xs mt-1">{$errors.email}</p>{/if}
    </div>

    <div>
      <label class="text-sm font-medium" for="password">Password</label>
      <input id="password" type="password" bind:value={$form.password}
        class="w-full mt-1 px-3 py-2 border rounded-md text-sm" />
      {#if $errors.password}<p class="text-destructive text-xs mt-1">{$errors.password}</p>{/if}
    </div>

    <button type="submit" disabled={$submitting}
      class="w-full py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium disabled:opacity-50">
      {$submitting ? 'Signing in…' : 'Sign in'}
    </button>

    <p class="text-center text-sm text-muted-foreground">
      No account? <a href="/register" class="text-primary underline">Register</a>
    </p>
  </form>
</div>
```

---

## 17. Melt UI — Replacing Radix UI

Melt UI provides accessible headless primitives for Svelte. Direct equivalents:

| Radix UI (React) | Melt UI (Svelte) | Used for |
|---|---|---|
| `@radix-ui/react-dialog` | `createDialog` from `@melt-ui/svelte` | NewAnalysis modal, delete modal |
| `@radix-ui/react-dropdown-menu` | `createDropdownMenu` | User avatar menu |
| `@radix-ui/react-tooltip` | `createTooltip` | Node hover tooltips |
| `@radix-ui/react-context-menu` | `createContextMenu` | Node right-click menu |
| `@radix-ui/react-select` | `createSelect` | Model selector, DimensionType selector |

Example — Model Selector using `createSelect`:

```svelte
<!-- src/lib/components/chat/ModelSelector.svelte -->
<script lang="ts">
  import { createSelect, melt } from '@melt-ui/svelte'
  import { ChevronDown } from 'lucide-svelte'
  import { sessionStore } from '$lib/stores/sessionStore'

  const MODELS = [
    { value: 'claude-haiku-4-5',  label: 'Haiku (Fast)' },
    { value: 'claude-sonnet-4-6', label: 'Sonnet (Default)' },
    { value: 'claude-opus-4-6',   label: 'Opus (Most capable)' },
  ]

  const {
    elements: { trigger, menu, option, label },
    states: { selectedLabel, open },
    helpers: { isSelected },
  } = createSelect({
    defaultSelected: { value: $sessionStore.selectedModel, label: 'Sonnet (Default)' },
    onSelectedChange: ({ next }) => {
      if (next?.value) sessionStore.setSelectedModel(next.value)
      return next
    },
    positioning: { placement: 'bottom-end' },
  })
</script>

<button use:melt={$trigger}
  class="flex items-center gap-1 text-xs px-2 py-1 rounded border hover:bg-muted">
  {$selectedLabel ?? 'Select model'}
  <ChevronDown size={12} />
</button>

{#if $open}
  <div use:melt={$menu} class="z-50 bg-popover border rounded-md shadow-md p-1 min-w-[180px]">
    {#each MODELS as model}
      <div use:melt={$option({ value: model.value, label: model.label })}
        class="px-2 py-1.5 text-sm rounded cursor-pointer hover:bg-muted
               data-[highlighted]:bg-muted data-[selected]:font-semibold">
        {model.label}
      </div>
    {/each}
  </div>
{/if}
```

---

## 18. Analysis Node Component (`src/lib/components/graph/nodes/AnalysisNodeComponent.svelte`)

Custom Svelte Flow node component. Registered under `nodeTypes.analysisNode`.

```svelte
<!-- src/lib/components/graph/nodes/AnalysisNodeComponent.svelte -->
<script lang="ts">
  import { Handle, Position } from '@xyflow/svelte'
  import type { AnalysisNode } from '$lib/schemas/graph'
  import { DIMENSION_STYLES } from '$lib/utils/graphStyles'
  import * as icons from 'lucide-svelte'

  // data is the full AnalysisNode passed from GraphPanel
  export let data: AnalysisNode

  $: style = DIMENSION_STYLES[data.type]
  $: IconComponent = (icons as Record<string, unknown>)[style.icon] as typeof icons.Lightbulb
</script>

<div class="rounded-xl border-2 shadow-sm px-3 py-2 min-w-[180px] max-w-[220px] text-sm
            {style.bgClass} {style.borderClass} {style.textClass}">
  <Handle type="target" position={Position.Top} class="!bg-border" />

  <div class="flex items-center gap-1.5 mb-1">
    <svelte:component this={IconComponent} size={13} />
    <span class="text-xs font-semibold uppercase tracking-wide opacity-60">{style.label}</span>
    {#if data.score !== null && data.score !== undefined}
      <span class="ml-auto text-xs font-bold">{data.score}/10</span>
    {/if}
  </div>

  <p class="font-semibold leading-snug line-clamp-2">{data.label}</p>
  <p class="text-xs opacity-70 mt-0.5 line-clamp-2">{data.content}</p>

  <Handle type="source" position={Position.Bottom} class="!bg-border" />
</div>
```

---

## 19. Node Detail Panel (`src/lib/components/graph/NodeDetailPanel.svelte`)

Replaces the React slide-over. Uses Svelte's built-in `fly` transition.

```svelte
<!-- src/lib/components/graph/NodeDetailPanel.svelte -->
<script lang="ts">
  import { fly } from 'svelte/transition'
  import { graphStore } from '$lib/stores/graphStore'
  import { chatStore } from '$lib/stores/chatStore'
  import { sessionStore } from '$lib/stores/sessionStore'
  import { v4 as uuidv4 } from 'uuid'

  export let nodeId: string

  $: node = $graphStore.nodes.find(n => n.id === nodeId)

  let label = ''
  let content = ''
  let score: number | null = null

  $: if (node) { label = node.label; content = node.content; score = node.score ?? null }

  function save() {
    if (!node) return
    graphStore.updateNode(node.id, { label, content, score })
    sessionStore.saveGraph()
    const msg = `[User action: edited node "${node.type} › ${label}"]`
    chatStore.addMessage({ id: uuidv4(), role: 'system', content: msg })
    // Also persist system message to DB via sessionService if needed
  }

  function deleteNode() {
    if (!node) return
    const msg = `[User action: deleted node "${node.type} › ${node.label}"]`
    chatStore.addMessage({ id: uuidv4(), role: 'system', content: msg })
    graphStore.deleteNode(node.id)
    sessionStore.saveGraph()
  }

  function close() {
    graphStore.setSelectedNodeId(null)
  }
</script>

{#if node}
  <div
    transition:fly={{ x: 320, duration: 250 }}
    class="absolute top-0 right-0 h-full w-80 bg-card border-l shadow-lg flex flex-col z-10 overflow-hidden"
    role="dialog"
    aria-label="Node details"
  >
    <div class="flex items-center justify-between px-4 py-3 border-b">
      <span class="font-semibold text-sm capitalize">{node.type}</span>
      <button on:click={close} class="text-muted-foreground hover:text-foreground text-lg leading-none">×</button>
    </div>

    <div class="flex-1 overflow-y-auto p-4 space-y-4">
      <div>
        <label class="text-xs font-medium text-muted-foreground uppercase tracking-wide">Label</label>
        <input bind:value={label} class="w-full mt-1 px-3 py-2 border rounded-md text-sm" />
      </div>
      <div>
        <label class="text-xs font-medium text-muted-foreground uppercase tracking-wide">Content</label>
        <textarea bind:value={content} rows={4}
          class="w-full mt-1 px-3 py-2 border rounded-md text-sm resize-none" />
      </div>
      {#if node.type === 'feasibility'}
        <div>
          <label class="text-xs font-medium text-muted-foreground uppercase tracking-wide">Score (0–10)</label>
          <input type="number" min="0" max="10" step="0.5" bind:value={score}
            class="w-full mt-1 px-3 py-2 border rounded-md text-sm" />
        </div>
      {/if}
    </div>

    <div class="p-4 border-t flex gap-2">
      <button on:click={save}
        class="flex-1 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium">
        Save
      </button>
      <button on:click={deleteNode}
        class="py-2 px-4 bg-destructive text-destructive-foreground rounded-md text-sm font-medium">
        Delete
      </button>
    </div>
  </div>
{/if}
```

---

## 20. Dashboard Page (`src/routes/(protected)/(requires-api-key)/+page.svelte`)

```svelte
<!-- src/routes/(protected)/(requires-api-key)/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte'
  import { goto } from '$app/navigation'
  import { sessionStore } from '$lib/stores/sessionStore'
  import { authStore } from '$lib/stores/authStore'
  import { formatDistanceToNow } from 'date-fns'
  import NewAnalysisModal from '$lib/components/session/NewAnalysisModal.svelte'
  import { toast } from 'svelte-sonner'

  let showModal = false

  onMount(() => {
    sessionStore.fetchSessions()
  })

  async function handleDelete(id: string) {
    await sessionStore.deleteSession(id)
    toast.success('Session deleted')
  }

  function handleCardClick(id: string) {
    goto(`/session/${id}`)
  }
</script>

<div class="max-w-4xl mx-auto px-4 py-8">
  <!-- API key banner -->
  {#if !$authStore.user?.has_api_key}
    <div class="mb-6 p-4 bg-yellow-50 border border-yellow-300 rounded-lg flex items-center justify-between">
      <span class="text-sm text-yellow-800">Set your Anthropic API key to start analysing ideas.</span>
      <a href="/settings?prompt=api-key" class="text-sm font-medium text-yellow-900 underline">Go to Settings</a>
    </div>
  {/if}

  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold">My Analyses</h1>
    <button on:click={() => showModal = true}
      class="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium">
      + New Analysis
    </button>
  </div>

  {#if $sessionStore.isLoading}
    <div class="space-y-3">
      {#each Array(3) as _}
        <div class="h-24 bg-muted animate-pulse rounded-xl" />
      {/each}
    </div>
  {:else if $sessionStore.sessions.length === 0}
    <div class="text-center py-20 text-muted-foreground">
      <p class="text-lg">No analyses yet.</p>
      <button on:click={() => showModal = true} class="mt-2 text-primary underline text-sm">
        Start your first one →
      </button>
    </div>
  {:else}
    <div class="space-y-3">
      {#each $sessionStore.sessions as session (session.id)}
        <div
          class="group relative bg-card border rounded-xl p-4 cursor-pointer hover:shadow-md transition-shadow"
          on:click={() => handleCardClick(session.id)}
          on:keydown={e => e.key === 'Enter' && handleCardClick(session.id)}
          role="button"
          tabindex="0"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="min-w-0">
              <p class="font-semibold truncate">{session.name}</p>
              <p class="text-sm text-muted-foreground mt-0.5 line-clamp-1">{session.idea}</p>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <span class="text-xs bg-muted px-2 py-0.5 rounded-full">{session.selected_model}</span>
              <span class="text-xs text-muted-foreground">
                {formatDistanceToNow(new Date(session.updated_at), { addSuffix: true })}
              </span>
            </div>
          </div>
          <button
            on:click|stopPropagation={() => handleDelete(session.id)}
            class="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity
                   text-destructive text-xs px-2 py-1 hover:bg-destructive/10 rounded">
            Delete
          </button>
        </div>
      {/each}
    </div>
  {/if}
</div>

{#if showModal}
  <NewAnalysisModal onClose={() => showModal = false} />
{/if}
```

---

## 21. Updated Repository Structure

The SvelteKit equivalent of the React `src/` directory:

```
apps/web/
├── src/
│   ├── app.css                         # global styles
│   ├── app.d.ts                        # SvelteKit type augmentation
│   ├── lib/
│   │   ├── config.ts                   # API_BASE_URL from PUBLIC_API_URL
│   │   ├── schemas/
│   │   │   └── graph.ts                # Zod schemas (identical to React version)
│   │   ├── stores/
│   │   │   ├── authStore.ts            # writable store (replaces Zustand authStore)
│   │   │   ├── chatStore.ts
│   │   │   ├── graphStore.ts
│   │   │   └── sessionStore.ts
│   │   ├── services/
│   │   │   ├── api.ts                  # Axios + interceptors
│   │   │   ├── authService.ts
│   │   │   ├── userService.ts
│   │   │   ├── sessionService.ts
│   │   │   └── chatService.ts          # SSE fetch stream (identical logic)
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   ├── ChatPanel.svelte
│   │   │   │   ├── MessageBubble.svelte
│   │   │   │   ├── ChatInput.svelte
│   │   │   │   └── ModelSelector.svelte
│   │   │   ├── graph/
│   │   │   │   ├── GraphPanel.svelte
│   │   │   │   ├── GraphToolbar.svelte
│   │   │   │   ├── NodeDetailPanel.svelte
│   │   │   │   ├── AddNodeModal.svelte
│   │   │   │   └── nodes/
│   │   │   │       └── AnalysisNodeComponent.svelte
│   │   │   ├── layout/
│   │   │   │   ├── AppHeader.svelte
│   │   │   │   └── SplitLayout.svelte
│   │   │   ├── session/
│   │   │   │   └── NewAnalysisModal.svelte
│   │   │   └── ui/                     # Button, Modal, Skeleton, Badge (Melt UI based)
│   │   └── utils/
│   │       ├── graphLayout.ts          # Dagre layout (identical)
│   │       ├── graphStyles.ts          # colour/icon map (identical)
│   │       ├── graphGuards.ts          # node limits (identical)
│   │       └── debounce.ts             # (identical)
│   └── routes/
│       ├── +layout.ts                  # ssr = false
│       ├── +layout.svelte              # Toaster, auth init
│       ├── login/
│       │   └── +page.svelte
│       ├── register/
│       │   └── +page.svelte
│       └── (protected)/
│           ├── +layout.ts              # auth guard (redirect to /login)
│           ├── settings/
│           │   └── +page.svelte
│           └── (requires-api-key)/
│               ├── +layout.ts          # api key guard (redirect to /settings)
│               ├── +page.svelte        # Dashboard
│               └── session/
│                   └── [id]/
│                       └── +page.svelte
├── static/
│   └── favicon.png
├── svelte.config.js
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── nginx.conf                          # identical to React version
└── Dockerfile                          # updated — see §22
```

---

## 22. Dockerfile (Updated for SvelteKit / adapter-node)

The SvelteKit `adapter-node` build outputs a Node.js server (`build/index.js`) instead of
static files served by nginx. The production image runs Node directly.

```dockerfile
# apps/web/Dockerfile

FROM node:20-alpine AS development
WORKDIR /app
COPY package*.json .
RUN npm ci
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]

FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
# Pass PUBLIC_API_URL at build time (same-origin in prod → empty string)
ENV PUBLIC_API_URL=""
RUN npm run build

FROM node:20-alpine AS production
WORKDIR /app
# adapter-node outputs to build/ — copy that + node_modules for runtime deps
COPY --from=builder /app/build ./build
COPY --from=builder /app/package*.json .
RUN npm ci --omit=dev
ENV PORT=3000
ENV HOST=0.0.0.0
EXPOSE 3000
CMD ["node", "build/index.js"]
```

**Impact on nginx.conf:** In the React version, nginx served static files AND acted as a
reverse proxy to the API. With adapter-node, nginx proxies BOTH the web frontend (port
3000) and the API (port 8000). The nginx.conf in the production setup needs an update:

```nginx
server {
    listen 80;
    server_name _;

    # SSE — must be before /api/ to match first
    location /api/chat {
        proxy_pass http://api:8000/api/chat;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 120s;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://api:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /auth/ {
        proxy_pass http://api:8000/auth/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # All other traffic → SvelteKit Node server (replaces static file serving)
    location / {
        proxy_pass http://web:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Alternatively, skip nginx for the web service entirely and point the ALB directly at the
SvelteKit Node container on port 3000, using ALB routing rules to forward `/api/*` and
`/auth/*` to the API container. This is cleaner for production.

---

## 23. CI/CD — Updated Frontend Job

The CI frontend steps in `05_INFRASTRUCTURE_AND_DEPLOYMENT.md §9` need these changes:

```yaml
# .github/workflows/ci.yml — frontend job (updated for SvelteKit)
frontend:
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with: { node-version: "20" }
    - run: cd apps/web && npm ci
    - run: cd apps/web && npx prettier --check src/   # replaces eslint for Svelte files
    - run: cd apps/web && npx svelte-check            # replaces tsc --noEmit for Svelte
    - run: cd apps/web && npx vitest run

# .github/workflows/deploy.yml — web image build (updated)
- name: Build and push web image
  run: |
    docker build --target production \
      --build-arg PUBLIC_API_URL="" \
      -t $ECR_REGISTRY/idealens-web:$GITHUB_SHA apps/web
    docker push $ECR_REGISTRY/idealens-web:$GITHUB_SHA
    docker push $ECR_REGISTRY/idealens-web:latest
```

Install `svelte-check` as a dev dependency:
```bash
npm install -D svelte-check
```

---

## 24. Changes to Other Planning Documents

When using this SvelteKit version, apply these overrides to the other planning docs:

### 01_PROJECT_PLAN.md — §1 Confirmed Stack
Replace:
> Frontend: React + Vite (TypeScript)

With:
> Frontend: SvelteKit + Vite (TypeScript), SPA mode via adapter-node

### 01_PROJECT_PLAN.md — §3.5 Model Table
No change — model list and defaults are identical.

### 02_TODOS.md — §1.3 Vite Environment Variables
Replace `VITE_API_URL` with `PUBLIC_API_URL` throughout. SvelteKit requires the `PUBLIC_`
prefix for client-exposed env vars.

### 02_TODOS.md — §1.9 Authentication — Frontend
Replace all React-specific steps with SvelteKit equivalents:
- `npm create vite@latest . -- --template react-ts` → `npm create svelte@latest .`
- Zustand stores → Svelte writable stores (see §8 above)
- `src/stores/authStore.ts` persisted with `persist` middleware → `localStorage.setItem` in store methods (see §8)
- `src/components/auth/ProtectedRoute.tsx` → `src/routes/(protected)/+layout.ts`
- `src/components/auth/ApiKeyGuard.tsx` → `src/routes/(protected)/(requires-api-key)/+layout.ts`

### 04_LIBRARIES_AND_FRAMEWORKS.md — Frontend section
Replace the React frontend table with:

| Library | Version | Purpose |
|---|---|---|
| `svelte` | ^5.x | UI framework |
| `@sveltejs/kit` | ^2.x | Full-stack framework (routing, load, SPA mode) |
| `@sveltejs/adapter-node` | ^5.x | Node.js build target for Docker |
| `vite` | ^6.x | Build tool (internal to SvelteKit) |
| `typescript` | ^5.x | Type safety |
| `@xyflow/svelte` | ^0.1.x | Interactive node graph (Svelte Flow) |
| `@dagrejs/dagre` | ^1.x | Directed graph auto-layout |
| `svelte-splitpanes` | ^9.x | Resizable split panels |
| `@melt-ui/svelte` | ^0.86.x | Headless accessible UI primitives |
| `@melt-ui/pp` | latest | Melt UI preprocessor (required) |
| `sveltekit-superforms` | ^2.x | Form state + validation (replaces react-hook-form) |
| `zod` | ^3.x | Schema validation |
| `axios` | ^1.x | HTTP client + interceptors |
| `svelte-sonner` | ^0.3.x | Toast notifications |
| `lucide-svelte` | ^0.400.x | Icons |
| `date-fns` | ^3.x | Date formatting |
| `uuid` | ^9.x | Client-side ID generation |
| `tailwindcss` | ^4.x | Utility-first CSS |
| `class-variance-authority` | ^0.7.x | Variant styling |
| `clsx` + `tailwind-merge` | ^2.x | Conditional classnames |
| `svelte-check` | ^3.x | Type checking for `.svelte` files (replaces `tsc --noEmit`) |
| `@testing-library/svelte` | ^5.x | Component testing |
| `vitest` | ^3.x | Unit tests |
| `@playwright/test` | ^1.x | E2E tests |
| `prettier` + `prettier-plugin-svelte` | ^3.x | Code formatting |
| `husky` + `lint-staged` | ^9.x / ^15.x | Git hooks |

Removed from React version: `react`, `react-dom`, `react-router-dom`, `zustand`, `immer`,
`@tanstack/react-query`, `@xyflow/react`, `react-resizable-panels`, `motion`,
`@radix-ui/*`, `react-hook-form`, `@hookform/resolvers`, `sonner`, `lucide-react`.

---

## 25. Functionality Parity Checklist

Verify that every feature from the React version is implemented in the SvelteKit version:

| Feature | React impl | SvelteKit impl | Parity |
|---|---|---|---|
| Email/password auth | Login.tsx + Register.tsx | login/+page.svelte + register/+page.svelte | ✓ |
| Auth guards | ProtectedRoute + ApiKeyGuard | +layout.ts load() redirect | ✓ |
| JWT refresh interceptor | api.ts Axios interceptor | api.ts Axios interceptor (identical) | ✓ |
| Settings page | Settings.tsx | settings/+page.svelte | ✓ |
| API key management | userService + settings | userService + settings (same API calls) | ✓ |
| Dashboard + session list | Dashboard.tsx | (protected)/(requires-api-key)/+page.svelte | ✓ |
| New Analysis modal | NewAnalysisModal.tsx | NewAnalysisModal.svelte | ✓ |
| Split-view workspace | SplitLayout + react-resizable-panels | SplitLayout + svelte-splitpanes | ✓ |
| SSE streaming chat | chatService.ts fetch-based | chatService.ts (identical logic) | ✓ |
| Token-by-token display | chatStore.appendToken | chatStore.appendToken (same) | ✓ |
| Graph visualization | GraphPanel + @xyflow/react | GraphPanel + @xyflow/svelte | ✓ |
| Custom node types | AnalysisNodeComponent.tsx | AnalysisNodeComponent.svelte | ✓ |
| Dagre auto-layout | graphLayout.ts | graphLayout.ts (identical) | ✓ |
| Incremental position | getIncrementalPosition | getIncrementalPosition (identical) | ✓ |
| Node detail panel | NodeDetailPanel.tsx (slide-over) | NodeDetailPanel.svelte (fly transition) | ✓ |
| Graph toolbar | GraphToolbar.tsx | GraphToolbar.svelte | ✓ |
| Right-click context menu | Radix ContextMenu | Melt UI createContextMenu | ✓ |
| Graph→chat feedback | system messages | system messages (identical logic) | ✓ |
| Graph persist (debounced) | sessionStore.saveGraph | sessionStore.saveGraph (identical) | ✓ |
| Model selector | Radix Select | Melt UI createSelect | ✓ |
| Toast notifications | sonner | svelte-sonner (identical API) | ✓ |
| Inline session rename | AppHeader.tsx | AppHeader.svelte | ✓ |
| Keyboard shortcuts | useEffect + keydown | svelte:window on:keydown | ✓ |
| Error boundaries | React ErrorBoundary | svelte:boundary (Svelte 5) or try/catch in load | ✓ |
| Loading skeletons | Tailwind animate-pulse | Tailwind animate-pulse (identical) | ✓ |
| Zod graph validation | LLMGraphActionSchema.parse | LLMGraphActionSchema.parse (identical) | ✓ |
| Context summarization | backend — no change | backend — no change | ✓ |
| SSE reconnection | Last-Event-ID header | Last-Event-ID header (identical) | ✓ |
| isStreaming guard | chatStore.isStreaming | chatStore.isStreaming | ✓ |
| nodeTypes module-level | required in React Flow | required in Svelte Flow | ✓ |
| userPositioned flag | graphStore immer | graphStore plain update | ✓ |