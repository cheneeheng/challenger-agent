import { API_BASE_URL } from '$lib/config'
import { authStore } from '$lib/stores/authStore'
import { llmGraphActionSchema, type LLMGraphAction } from '$lib/schemas/graph'
import { get } from 'svelte/store'
import type { AnalysisGraph } from '$lib/schemas/graph'

export interface SSECallbacks {
  onToken: (token: string) => void
  onGraphAction: (action: LLMGraphAction) => void
  onError: (msg: string) => void
  onDone: () => void
}

export async function streamChat(
  sessionId: string,
  message: string,
  graphState: AnalysisGraph,
  model: string,
  callbacks: SSECallbacks,
  lastEventId?: string
): Promise<void> {
  const { accessToken } = get(authStore)

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`
  }
  if (lastEventId) {
    headers['Last-Event-ID'] = lastEventId
  }

  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify({
      session_id: sessionId,
      message,
      graph_state: graphState,
      model,
    }),
  })

  if (!response.body) {
    callbacks.onError('No response body from server.')
    callbacks.onDone()
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''

    for (const part of parts) {
      const lines = part.trim().split('\n')
      let eventType = 'message'
      let data = ''

      for (const line of lines) {
        if (line.startsWith('event:')) {
          eventType = line.slice('event:'.length).trim()
        } else if (line.startsWith('data:')) {
          data = line.slice('data:'.length).trim()
        }
      }

      if (!eventType || eventType === 'ping') continue

      if (eventType === 'token') {
        // data may contain escaped JSON string (quoted)
        try {
          callbacks.onToken(JSON.parse(data) as string)
        } catch {
          callbacks.onToken(data)
        }
      } else if (eventType === 'graph_action') {
        try {
          const raw = JSON.parse(data)
          const parsed = llmGraphActionSchema.safeParse(raw)
          if (parsed.success) {
            callbacks.onGraphAction(parsed.data)
          }
        } catch {
          // ignore malformed action
        }
      } else if (eventType === 'error') {
        callbacks.onError(data)
      } else if (eventType === 'done') {
        callbacks.onDone()
        return
      }
    }
  }

  callbacks.onDone()
}
