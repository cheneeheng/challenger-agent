import { writable, get } from 'svelte/store'
import { apiClient } from '$lib/services/api'
import { graphStore } from '$lib/stores/graphStore'
import { chatStore } from '$lib/stores/chatStore'
import { debounce } from '$lib/utils/debounce'
import type { SessionListItem, SessionResponse } from '$lib/services/sessionService'

interface SessionState {
  sessions: SessionListItem[]
  currentSessionId: string | null
  currentSession: SessionResponse | null
  selectedModel: string
  isLoading: boolean
  error: string | null
}

const _persistGraph = debounce(async (sessionId: string) => {
  const { nodes, edges } = graphStore.getSnapshot()
  try {
    await apiClient.put(`/api/sessions/${sessionId}/graph`, {
      graph_state: { nodes, edges },
    })
  } catch {
    // silently fail on background save
  }
}, 1000)

function createSessionStore() {
  const { subscribe, set, update } = writable<SessionState>({
    sessions: [],
    currentSessionId: null,
    currentSession: null,
    selectedModel: 'claude-sonnet-4-6',
    isLoading: false,
    error: null,
  })

  return {
    subscribe,

    setSelectedModel(model: string) {
      update((s) => ({ ...s, selectedModel: model }))
    },

    setLoading(loading: boolean) {
      update((s) => ({ ...s, isLoading: loading }))
    },

    setSessions(sessions: SessionListItem[]) {
      update((s) => ({ ...s, sessions }))
    },

    setCurrentSession(session: SessionResponse | null) {
      update((s) => ({
        ...s,
        currentSession: session,
        currentSessionId: session?.id ?? null,
        selectedModel: session?.selected_model ?? s.selectedModel,
      }))
    },

    updateCurrentSession(changes: Partial<SessionResponse>) {
      update((s) => ({
        ...s,
        currentSession: s.currentSession
          ? { ...s.currentSession, ...changes }
          : null,
      }))
    },

    removeSession(id: string) {
      update((s) => ({
        ...s,
        sessions: s.sessions.filter((sess) => sess.id !== id),
      }))
    },

    async loadSession(id: string): Promise<void> {
      update((s) => ({ ...s, isLoading: true, error: null }))
      try {
        const resp = await apiClient.get(`/api/sessions/${id}`)
        const session = resp.data as SessionResponse & {
          messages?: Array<{ id: string; role: 'user' | 'assistant' | 'system'; content: string }>
        }

        update((s) => ({
          ...s,
          currentSessionId: id,
          currentSession: session,
          selectedModel: session.selected_model,
        }))

        // Populate graph store
        const gs = session.graph_state as { nodes?: unknown[]; edges?: unknown[] }
        graphStore.setGraph({
          nodes: (gs.nodes ?? []) as import('$lib/schemas/graph').AnalysisNode[],
          edges: (gs.edges ?? []) as import('$lib/schemas/graph').AnalysisEdge[],
        })

        // Populate chat store
        const messages = session.messages ?? []
        chatStore.setMessages(
          messages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
          }))
        )
      } catch (e: unknown) {
        const status = (e as { response?: { status: number } }).response?.status
        update((s) => ({
          ...s,
          error: status === 403 ? 'Access denied' : 'Session not found',
        }))
      } finally {
        update((s) => ({ ...s, isLoading: false }))
      }
    },

    saveGraph() {
      const { currentSessionId } = get({ subscribe })
      if (currentSessionId) _persistGraph(currentSessionId)
    },

    getSnapshot(): SessionState {
      return get({ subscribe })
    },
  }
}

export const sessionStore = createSessionStore()
