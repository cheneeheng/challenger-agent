# FRONTEND IMPLEMENTATION REFERENCE
> Authoritative implementation guide for the React + Vite + TypeScript frontend.
> Claude Code: read this before implementing any frontend component.

---

## 1. Project Bootstrap

```bash
cd apps/web
npm create vite@latest . -- --template react-ts
npm install

# All dependencies:
npm install \
  react-router-dom \
  zustand immer \
  axios @tanstack/react-query \
  zod react-hook-form @hookform/resolvers \
  @xyflow/react @dagrejs/dagre \
  react-resizable-panels \
  motion \
  tailwindcss @tailwindcss/vite \
  @radix-ui/react-dialog @radix-ui/react-dropdown-menu \
  @radix-ui/react-tooltip @radix-ui/react-context-menu @radix-ui/react-select \
  class-variance-authority clsx tailwind-merge \
  lucide-react sonner date-fns uuid

npm install -D \
  @types/uuid vitest @testing-library/react \
  @testing-library/user-event playwright \
  eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin \
  prettier husky lint-staged
```

---

## 2. Environment Config (`src/config.ts`)

```typescript
// Single source of truth for all environment-derived values
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? ''
// Dev  → 'http://localhost:8000'  (cross-origin; FastAPI CORS handles it)
// Prod → ''  (same-origin; nginx proxies /api/ and /auth/ to api container)
```

`vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',       // required inside Docker
    port: 3000,
    hmr: {
      host: 'localhost',   // browser connects HMR WebSocket to host machine port
      port: 3000,
    },
  },
})
```

---

## 3. App Entry (`src/main.tsx`)

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
        <Toaster position="bottom-right" richColors />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
)
```

---

## 4. Router (`src/App.tsx`)

```tsx
import { Routes, Route, Navigate } from 'react-router-dom'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { ApiKeyGuard } from './components/auth/ApiKeyGuard'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Session from './pages/Session'
import Settings from './pages/Settings'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Authenticated routes */}
      <Route element={<ProtectedRoute />}>
        {/* Settings accessible even without API key */}
        <Route path="/settings" element={<Settings />} />

        {/* Routes requiring API key */}
        <Route element={<ApiKeyGuard />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/session/:id" element={<Session />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
```

```tsx
// src/components/auth/ProtectedRoute.tsx
import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'

export function ProtectedRoute() {
  const { user, accessToken } = useAuthStore()
  if (!user || !accessToken) return <Navigate to="/login" replace />
  return <Outlet />
}

// src/components/auth/ApiKeyGuard.tsx
export function ApiKeyGuard() {
  const user = useAuthStore(s => s.user)
  if (!user?.has_api_key) return <Navigate to="/settings?prompt=api-key" replace />
  return <Outlet />
}
```

---

## 5. Axios Instance (`src/services/api.ts`)

```typescript
import axios from 'axios'
import { API_BASE_URL } from '../config'
import { useAuthStore } from '../stores/authStore'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,  // required: sends httpOnly refresh_token cookie on /auth/* requests
})

// Inject access token on every request
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
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
          resolve: (token) => { original.headers.Authorization = `Bearer ${token}`; resolve(apiClient(original)) },
          reject,
        })
      })
    }

    original._retry = true
    isRefreshing = true
    try {
      const resp = await apiClient.post('/auth/refresh')
      const token = resp.data.access_token
      useAuthStore.getState().setAccessToken(token)
      queue.forEach(q => q.resolve(token))
      queue = []
      original.headers.Authorization = `Bearer ${token}`
      return apiClient(original)
    } catch (e) {
      queue.forEach(q => q.reject(e))
      queue = []
      useAuthStore.getState().logout()
      window.location.href = '/login'
      return Promise.reject(e)
    } finally {
      isRefreshing = false
    }
  }
)
```

---

## 6. SSE Chat Service (`src/services/chatService.ts`)

Uses `fetch` (not `EventSource`) because we need POST + Authorization header.

```typescript
import { API_BASE_URL } from '../config'
import { useAuthStore } from '../stores/authStore'
import { LLMGraphActionSchema } from '../schemas/graph'
import type { LLMGraphAction } from '../schemas/graph'

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
  const token = useAuthStore.getState().accessToken
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
  let lastId: string | undefined

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
      if (id) lastId = id

      if (eventType === 'token') callbacks.onToken(data)
      else if (eventType === 'graph_action') {
        try {
          const validated = LLMGraphActionSchema.parse(JSON.parse(data))
          callbacks.onGraphAction(validated)
        } catch { console.warn('Invalid graph_action received:', data) }
      }
      else if (eventType === 'error') callbacks.onError(data)
      else if (eventType === 'done') { callbacks.onDone(); return }
      // 'ping' — ignored intentionally
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
      // One automatic retry after 2s
      await new Promise(r => setTimeout(r, 2000))
      try {
        await _doStream(body, callbacks, controller.signal, lastEventId)
      } catch {
        callbacks.onError('Connection lost. Please try again.')
        callbacks.onDone()
      }
    }
  })()

  return () => controller.abort()   // returns cancel function
}
```

---

## 7. Zustand Stores

### `src/stores/authStore.ts`
```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User { id: string; email: string; name: string; has_api_key: boolean }

interface AuthStore {
  user: User | null
  accessToken: string | null
  setUser: (u: User) => void
  setAccessToken: (t: string) => void
  updateUser: (patch: Partial<User>) => void
  logout: () => void
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null, accessToken: null,
      setUser: (user) => set({ user }),
      setAccessToken: (accessToken) => set({ accessToken }),
      updateUser: (patch) => set(s => ({ user: s.user ? { ...s.user, ...patch } : null })),
      logout: () => set({ user: null, accessToken: null }),
    }),
    { name: 'auth', partialize: s => ({ user: s.user, accessToken: s.accessToken }) }
  )
)
```

### `src/stores/chatStore.ts`
```typescript
import { create } from 'zustand'
export interface ChatMessage { id: string; role: 'user' | 'assistant' | 'system'; content: string; isStreaming?: boolean }

interface ChatStore {
  messages: ChatMessage[]
  isStreaming: boolean
  error: string | null
  addMessage: (m: ChatMessage) => void
  appendToken: (id: string, chunk: string) => void
  finalizeMessage: (id: string) => void
  setError: (e: string | null) => void
  setStreaming: (v: boolean) => void
  setMessages: (msgs: ChatMessage[]) => void
  clear: () => void
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [], isStreaming: false, error: null,
  addMessage: m => set(s => ({ messages: [...s.messages, m] })),
  appendToken: (id, chunk) => set(s => ({
    messages: s.messages.map(m => m.id === id ? { ...m, content: m.content + chunk } : m)
  })),
  finalizeMessage: id => set(s => ({
    messages: s.messages.map(m => m.id === id ? { ...m, isStreaming: false } : m),
    isStreaming: false,
  })),
  setError: error => set({ error }),
  setStreaming: isStreaming => set({ isStreaming }),
  setMessages: messages => set({ messages }),
  clear: () => set({ messages: [], isStreaming: false, error: null }),
}))
```

### `src/stores/graphStore.ts`
```typescript
import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import { v4 as uuidv4 } from 'uuid'
import type { AnalysisNode, AnalysisEdge, LLMGraphAction } from '../schemas/graph'
import { getIncrementalPosition } from '../utils/graphLayout'

interface GraphStore {
  nodes: AnalysisNode[]
  edges: AnalysisEdge[]
  selectedNodeId: string | null
  setGraph: (nodes: AnalysisNode[], edges: AnalysisEdge[]) => void
  applyGraphActions: (actions: LLMGraphAction[]) => void
  addNode: (payload: Omit<AnalysisNode, 'position' | 'userPositioned'>) => void
  updateNode: (id: string, patch: Partial<AnalysisNode>) => void
  deleteNode: (id: string) => void
  addEdge: (edge: Omit<AnalysisEdge, 'id'>) => void
  deleteEdge: (id: string) => void
  setNodePosition: (id: string, pos: { x: number; y: number }) => void
  setSelectedNodeId: (id: string | null) => void
  clearGraph: () => void
}

export const useGraphStore = create<GraphStore>()(
  immer((set, get) => ({
    nodes: [], edges: [], selectedNodeId: null,

    setGraph: (nodes, edges) => set({ nodes, edges }),

    applyGraphActions: (actions) => set(state => {
      for (const action of actions) {
        if (action.action === 'add') {
          const position = getIncrementalPosition(state.nodes, action.payload.parent_id ?? undefined)
          state.nodes.push({ ...action.payload, position, userPositioned: false })
        } else if (action.action === 'update') {
          const node = state.nodes.find(n => n.id === action.payload.id)
          if (node) {
            // Preserve userPositioned position — don't overwrite if user dragged it
            const { position: _p, userPositioned: _u, ...rest } = action.payload as Partial<AnalysisNode>
            Object.assign(node, rest)
          }
        } else if (action.action === 'delete') {
          state.nodes = state.nodes.filter(n => n.id !== action.payload.id)
          state.edges = state.edges.filter(e => e.source !== action.payload.id && e.target !== action.payload.id)
        } else if (action.action === 'connect') {
          state.edges.push({ id: uuidv4(), ...action.payload })
        }
      }
    }),

    addNode: (payload) => set(state => {
      const position = getIncrementalPosition(state.nodes)
      state.nodes.push({ ...payload, position, userPositioned: false })
    }),

    updateNode: (id, patch) => set(state => {
      const node = state.nodes.find(n => n.id === id)
      if (node) Object.assign(node, patch)
    }),

    deleteNode: (id) => set(state => {
      state.nodes = state.nodes.filter(n => n.id !== id)
      state.edges = state.edges.filter(e => e.source !== id && e.target !== id)
    }),

    addEdge: (edge) => set(state => { state.edges.push({ id: uuidv4(), ...edge }) }),
    deleteEdge: (id) => set(state => { state.edges = state.edges.filter(e => e.id !== id) }),

    setNodePosition: (id, pos) => set(state => {
      const node = state.nodes.find(n => n.id === id)
      if (node) { node.position = pos; node.userPositioned = true }
    }),

    setSelectedNodeId: id => set({ selectedNodeId: id }),
    clearGraph: () => set({ nodes: [], edges: [], selectedNodeId: null }),
  }))
)
```

### `src/stores/sessionStore.ts`
```typescript
import { create } from 'zustand'
import { apiClient } from '../services/api'
import { useGraphStore } from './graphStore'
import { useChatStore } from './chatStore'
import { debounce } from '../utils/debounce'

interface SessionListItem { id: string; name: string; idea: string; selected_model: string; updated_at: string }

interface SessionStore {
  sessions: SessionListItem[]
  currentSessionId: string | null
  currentSession: { id: string; name: string; idea: string; selected_model: string } | null  // full loaded session
  selectedModel: string
  isLoading: boolean
  error: string | null
  fetchSessions: () => Promise<void>
  createSession: (idea: string, model: string) => Promise<string>
  loadSession: (id: string) => Promise<void>
  saveGraph: () => void   // debounced 1s
  updateSession: (id: string, patch: { name?: string; selected_model?: string }) => Promise<void>
  deleteSession: (id: string) => Promise<void>
  setSelectedModel: (m: string) => void
}

const _persistGraph = debounce(async (sessionId: string) => {
  const { nodes, edges } = useGraphStore.getState()
  await apiClient.put(`/api/sessions/${sessionId}/graph`, { graph_state: { nodes, edges } })
}, 1000)

export const useSessionStore = create<SessionStore>((set, get) => ({
  sessions: [], currentSessionId: null, currentSession: null,
  selectedModel: 'claude-sonnet-4-6',
  isLoading: false, error: null,

  fetchSessions: async () => {
    set({ isLoading: true, error: null })
    try {
      const resp = await apiClient.get('/api/sessions?page=1&limit=20')
      set({ sessions: resp.data.items })
    } catch { set({ error: 'Failed to load sessions' }) }
    finally { set({ isLoading: false }) }
  },

  createSession: async (idea, model) => {
    const resp = await apiClient.post('/api/sessions', { idea, selected_model: model })
    const s = resp.data
    set(state => ({ sessions: [s, ...state.sessions], currentSessionId: s.id, selectedModel: model }))
    return s.id
  },

  loadSession: async (id) => {
    set({ isLoading: true, error: null })
    try {
      const resp = await apiClient.get(`/api/sessions/${id}`)
      const session = resp.data
      set({
        currentSessionId: id,
        currentSession: { id: session.id, name: session.name, idea: session.idea, selected_model: session.selected_model },
        selectedModel: session.selected_model,
      })
      useGraphStore.getState().setGraph(session.graph_state.nodes, session.graph_state.edges)
      useChatStore.getState().setMessages(
        session.messages.map((m: { id: string; role: 'user'|'assistant'|'system'; content: string }) =>
          ({ id: m.id, role: m.role, content: m.content })
        )
      )
    } catch (e: unknown) {
      const status = (e as { response?: { status: number } }).response?.status
      set({ error: status === 403 ? 'Access denied' : 'Session not found' })
    } finally { set({ isLoading: false }) }
  },

  saveGraph: () => {
    const { currentSessionId } = get()
    if (currentSessionId) _persistGraph(currentSessionId)
  },

  updateSession: async (id, patch) => {
    await apiClient.patch(`/api/sessions/${id}`, patch)
    set(s => ({ sessions: s.sessions.map(sess => sess.id === id ? { ...sess, ...patch } : sess) }))
  },

  deleteSession: async (id) => {
    await apiClient.delete(`/api/sessions/${id}`)
    set(s => ({
      sessions: s.sessions.filter(sess => sess.id !== id),
      currentSessionId: s.currentSessionId === id ? null : s.currentSessionId,
    }))
  },

  setSelectedModel: model => set({ selectedModel: model }),
}))
```

---

## 8. Graph Schemas (`src/schemas/graph.ts`)

```typescript
import { z } from 'zod'

export const DimensionTypeSchema = z.enum([
  'root','concept','requirement','gap','benefit',
  'drawback','feasibility','flaw','alternative','question'
])

export const EdgeTypeSchema = z.enum(['supports','contradicts','requires','leads_to'])

// NodePayload — what the LLM sends (no position field)
export const NodePayloadSchema = z.object({
  id: z.string(),
  type: DimensionTypeSchema,
  label: z.string(),
  content: z.string(),
  score: z.number().min(0).max(10).nullable().optional(),
  parent_id: z.string().nullable().optional(),
})

// AnalysisNode — what graphStore holds (NodePayload + position + userPositioned)
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
  z.object({ action: z.literal('add'),     payload: NodePayloadSchema }),  // no position
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

## 9. React Flow — Controlled Pattern (`src/components/graph/GraphPanel.tsx`)

**Critical rules:**
1. `nodeTypes` must be defined at module level (outside the component) — React Flow remounts all nodes if this object is recreated on each render
2. Use graphStore as the single source of truth — do NOT use `useNodesState` / `useEdgesState`
3. Convert store types to React Flow types in the render function

```tsx
import { ReactFlow, Background, Controls, MiniMap, Node, Edge } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useGraphStore } from '../../stores/graphStore'
import { useSessionStore } from '../../stores/sessionStore'
import AnalysisNodeComponent from './nodes/AnalysisNodeComponent'
import GraphToolbar from './GraphToolbar'
import NodeDetailPanel from './NodeDetailPanel'

// MUST be at module level — not inside the component
const nodeTypes = { analysisNode: AnalysisNodeComponent }

export default function GraphPanel() {
  const nodes = useGraphStore(s => s.nodes)
  const edges = useGraphStore(s => s.edges)
  const selectedNodeId = useGraphStore(s => s.selectedNodeId)
  const setSelectedNodeId = useGraphStore(s => s.setSelectedNodeId)
  const setNodePosition = useGraphStore(s => s.setNodePosition)
  const deleteNode = useGraphStore(s => s.deleteNode)
  const deleteEdge = useGraphStore(s => s.deleteEdge)
  const saveGraph = useSessionStore(s => s.saveGraph)

  const rfNodes: Node[] = nodes.map(n => ({
    id: n.id,
    type: 'analysisNode',
    position: n.position,
    data: n,                   // full AnalysisNode available in AnalysisNodeComponent via props.data
    selected: n.id === selectedNodeId,
  }))

  const rfEdges: Edge[] = edges.map(e => ({
    id: e.id, source: e.source, target: e.target, label: e.label,
  }))

  return (
    <div className="relative h-full w-full">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => setSelectedNodeId(node.id)}
        onPaneClick={() => setSelectedNodeId(null)}
        onNodeDragStop={(_, node) => {
          setNodePosition(node.id, node.position)
          saveGraph()
        }}
        onNodesDelete={ns => ns.forEach(n => deleteNode(n.id))}
        onEdgesDelete={es => es.forEach(e => deleteEdge(e.id))}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
      <GraphToolbar />
      {selectedNodeId && <NodeDetailPanel nodeId={selectedNodeId} />}
    </div>
  )
}
```

---

## 10. New Analysis Flow (`src/pages/Session.tsx`)

The session page auto-sends the idea as the first message when a fresh session is loaded. The `sendMessage` function in `chatStore` orchestrates the full SSE flow.

```tsx
import { useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { v4 as uuidv4 } from 'uuid'
import { useSessionStore } from '../stores/sessionStore'
import { useChatStore } from '../stores/chatStore'
import { useGraphStore } from '../stores/graphStore'
import { streamChat } from '../services/chatService'
import { layoutGraph } from '../utils/graphLayout'
import { isGraphNearLimit } from '../utils/graphGuards'
import SplitLayout from '../components/layout/SplitLayout'
import ChatPanel from '../components/chat/ChatPanel'
import GraphPanel from '../components/graph/GraphPanel'
import { toast } from 'sonner'

export default function Session() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const loadSession = useSessionStore(s => s.loadSession)
  const currentSession = useSessionStore(s => s.currentSession)
  const selectedModel = useSessionStore(s => s.selectedModel)
  const saveGraph = useSessionStore(s => s.saveGraph)
  const isLoading = useSessionStore(s => s.isLoading)
  const error = useSessionStore(s => s.error)
  const messages = useChatStore(s => s.messages)
  const initialMessageSent = useRef(false)

  useEffect(() => {
    if (!id) return
    initialMessageSent.current = false  // reset on id change
    loadSession(id)
  }, [id])

  // Auto-send idea as first message for fresh sessions
  useEffect(() => {
    if (isLoading) return
    if (error) { toast.error(error); navigate('/'); return }
    if (!currentSession) return
    if (messages.length > 0) return        // session already has messages — don't auto-send
    if (initialMessageSent.current) return  // StrictMode double-fire guard
    initialMessageSent.current = true
    sendMessage(currentSession.idea)
  }, [isLoading, error, currentSession, messages.length])

  // sendMessage — full SSE orchestration. Export this or pass to ChatPanel via prop/context.
  const sendMessage = useCallback(async (text: string) => {
    const { isStreaming, setStreaming, addMessage, appendToken, finalizeMessage, setError } = useChatStore.getState()
    const { nodes, edges, applyGraphActions } = useGraphStore.getState()
    const { currentSessionId } = useSessionStore.getState()

    if (isStreaming || !currentSessionId || !text.trim()) return

    // Add user message to chat
    const userMsgId = uuidv4()
    addMessage({ id: userMsgId, role: 'user', content: text })
    setStreaming(true)
    setError(null)

    // Add placeholder assistant message (will be streamed into)
    const assistantMsgId = uuidv4()
    addMessage({ id: assistantMsgId, role: 'assistant', content: '', isStreaming: true })

    let receivedAnyGraphActions = false

    const cancel = await streamChat(
      {
        session_id: currentSessionId,
        message: text,
        graph_state: { nodes, edges },
        model: selectedModel,
      },
      {
        onToken: (chunk) => appendToken(assistantMsgId, chunk),
        onGraphAction: (action) => {
          receivedAnyGraphActions = true
          applyGraphActions([action])
          // After first batch of nodes, run Dagre layout if graph was empty
          const currentNodes = useGraphStore.getState().nodes
          if (currentNodes.length <= 2) {  // root + first new node
            const laid = layoutGraph(currentNodes, useGraphStore.getState().edges)
            useGraphStore.getState().setGraph(laid, useGraphStore.getState().edges)
          }
          saveGraph()
          if (isGraphNearLimit(useGraphStore.getState().nodes)) {
            toast.warning('Your graph is getting large. Consider removing unused nodes.')
          }
        },
        onError: (msg) => {
          setError(msg)
          toast.error(msg)
        },
        onDone: () => finalizeMessage(assistantMsgId),
      }
    )

    // cancel() can be called to abort mid-stream (e.g. on component unmount)
    return cancel
  }, [selectedModel])

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-muted-foreground animate-pulse">Loading session...</div>
      </div>
    )
  }

  return <SplitLayout left={<ChatPanel onSend={sendMessage} />} right={<GraphPanel />} />
}
```

**Note:** `sendMessage` is passed as a prop to `ChatPanel` so the chat input can invoke it. `ChatPanel` receives `onSend: (text: string) => void` and calls it on form submit. This avoids circular store dependencies.

---

## 11. Graph Layout Utils

```typescript
// src/utils/graphLayout.ts
import Dagre from '@dagrejs/dagre'
import type { AnalysisNode, AnalysisEdge } from '../schemas/graph'

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
// src/utils/graphStyles.ts
import type { DimensionType } from '../schemas/graph'

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
// src/utils/graphGuards.ts
import type { AnalysisNode, AnalysisEdge } from '../schemas/graph'
export const NODE_WARN  = 150
export const NODE_LIMIT = 200
export const EDGE_LIMIT = 400
export const isGraphNearLimit = (nodes: AnalysisNode[]) => nodes.length >= NODE_WARN
export const isGraphAtLimit   = (nodes: AnalysisNode[], edges: AnalysisEdge[]) =>
  nodes.length >= NODE_LIMIT || edges.length >= EDGE_LIMIT

// src/utils/debounce.ts
export function debounce<T extends (...args: Parameters<T>) => void>(fn: T, ms: number): T {
  let tid: ReturnType<typeof setTimeout>
  return ((...args) => { clearTimeout(tid); tid = setTimeout(() => fn(...args), ms) }) as T
}
```

---

## 12. System Messages in Chat UI

System messages are stored with `role: 'system'` and rendered as muted context indicators, not chat bubbles:

```tsx
// MessageBubble.tsx — render branch for system messages
if (message.role === 'system') {
  return (
    <div className="flex justify-center my-1 px-4">
      <span className="text-xs text-muted-foreground italic bg-muted px-2 py-0.5 rounded-full">
        {message.content}
      </span>
    </div>
  )
}
```

These messages are included in the messages array sent to `POST /api/chat`. The backend converts them to `role: 'user'` with `[Context]: ` prefix before passing to Anthropic.

---

## 13. Split Layout

```tsx
// src/components/layout/SplitLayout.tsx
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels'

export default function SplitLayout({ left, right }: { left: React.ReactNode; right: React.ReactNode }) {
  return (
    <PanelGroup direction="horizontal" className="h-full w-full">
      <Panel defaultSize={40} minSize={25}>
        <div className="h-full flex flex-col overflow-hidden">{left}</div>
      </Panel>
      <PanelResizeHandle className="w-1.5 bg-border hover:bg-primary/40 transition-colors cursor-col-resize" />
      <Panel defaultSize={60} minSize={30}>
        <div className="h-full relative">{right}</div>
      </Panel>
    </PanelGroup>
  )
}
```