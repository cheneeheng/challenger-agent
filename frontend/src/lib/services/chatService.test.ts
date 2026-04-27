import { describe, it, expect, vi, beforeEach } from 'vitest'
import { streamChat } from './chatService'
import type { SSECallbacks } from './chatService'

// Mock the authStore module so chatService can call get(authStore)
vi.mock('$lib/stores/authStore', async () => {
  const { writable } = await import('svelte/store')
  const store = writable({ user: null, accessToken: 'test-token' })
  return { authStore: store }
})

// Minimal SSE response builder
function buildSSEStream(events: string[]): Response {
  const body = events.join('\n\n') + '\n\n'
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(body))
      controller.close()
    },
  })
  return new Response(stream, {
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

function makeCallbacks(): SSECallbacks & {
  tokens: string[]
  actions: unknown[]
  errors: string[]
  done: boolean
} {
  const tokens: string[] = []
  const actions: unknown[] = []
  const errors: string[] = []
  let done = false
  return {
    tokens,
    actions,
    errors,
    get done() {
      return done
    },
    onToken: (t) => tokens.push(t),
    onGraphAction: (a) => actions.push(a),
    onError: (e) => errors.push(e),
    onDone: () => {
      done = true
    },
  }
}

describe('streamChat SSE parser', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('parses token events', async () => {
    const sseEvents = [
      'event: token\ndata: "hello"',
      'event: token\ndata: " world"',
      'event: done\ndata: [DONE]',
    ]
    globalThis.fetch = vi.fn().mockResolvedValue(buildSSEStream(sseEvents))

    const cbs = makeCallbacks()
    await streamChat('sess1', 'test', { nodes: [], edges: [] }, 'claude-sonnet-4-6', cbs)

    expect(cbs.tokens).toEqual(['hello', ' world'])
    expect(cbs.done).toBe(true)
  })

  it('parses graph_action events and passes raw object', async () => {
    const action = { action: 'add', payload: { id: 'n1', type: 'concept', label: 'Test', content: 'c' } }
    const sseEvents = [
      `event: graph_action\ndata: ${JSON.stringify(action)}`,
      'event: done\ndata: [DONE]',
    ]
    globalThis.fetch = vi.fn().mockResolvedValue(buildSSEStream(sseEvents))

    const cbs = makeCallbacks()
    await streamChat('sess1', 'test', { nodes: [], edges: [] }, 'claude-sonnet-4-6', cbs)

    expect(cbs.actions).toHaveLength(1)
    expect(cbs.actions[0]).toMatchObject(action)
    expect(cbs.done).toBe(true)
  })

  it('calls onError for error events', async () => {
    const sseEvents = [
      'event: error\ndata: Something went wrong',
      'event: done\ndata: [DONE]',
    ]
    globalThis.fetch = vi.fn().mockResolvedValue(buildSSEStream(sseEvents))

    const cbs = makeCallbacks()
    await streamChat('sess1', 'test', { nodes: [], edges: [] }, 'claude-sonnet-4-6', cbs)

    expect(cbs.errors).toEqual(['Something went wrong'])
  })

  it('skips ping events', async () => {
    const sseEvents = [
      'event: ping\ndata: ',
      'event: token\ndata: "ok"',
      'event: done\ndata: [DONE]',
    ]
    globalThis.fetch = vi.fn().mockResolvedValue(buildSSEStream(sseEvents))

    const cbs = makeCallbacks()
    await streamChat('sess1', 'test', { nodes: [], edges: [] }, 'claude-sonnet-4-6', cbs)

    expect(cbs.tokens).toEqual(['ok'])
    expect(cbs.errors).toHaveLength(0)
  })

  it('handles missing response body', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(null))

    const cbs = makeCallbacks()
    await streamChat('sess1', 'test', { nodes: [], edges: [] }, 'claude-sonnet-4-6', cbs)

    expect(cbs.errors).toHaveLength(1)
    expect(cbs.done).toBe(true)
  })

  it('handles malformed JSON in graph_action gracefully', async () => {
    const sseEvents = [
      'event: graph_action\ndata: not-valid-json',
      'event: done\ndata: [DONE]',
    ]
    globalThis.fetch = vi.fn().mockResolvedValue(buildSSEStream(sseEvents))

    const cbs = makeCallbacks()
    await streamChat('sess1', 'test', { nodes: [], edges: [] }, 'claude-sonnet-4-6', cbs)

    expect(cbs.actions).toHaveLength(0)
    expect(cbs.done).toBe(true)
  })

  it('handles token data without JSON encoding', async () => {
    const sseEvents = [
      'event: token\ndata: plain text',
      'event: done\ndata: [DONE]',
    ]
    globalThis.fetch = vi.fn().mockResolvedValue(buildSSEStream(sseEvents))

    const cbs = makeCallbacks()
    await streamChat('sess1', 'test', { nodes: [], edges: [] }, 'claude-sonnet-4-6', cbs)

    expect(cbs.tokens).toEqual(['plain text'])
  })

  it('includes Last-Event-ID header when provided', async () => {
    const sseEvents = ['event: done\ndata: [DONE]']
    const mockFetch = vi.fn().mockResolvedValue(buildSSEStream(sseEvents))
    globalThis.fetch = mockFetch

    const cbs = makeCallbacks()
    await streamChat('sess1', 'test', { nodes: [], edges: [] }, 'claude-sonnet-4-6', cbs, 'last-id-123')

    const headers = mockFetch.mock.calls[0][1].headers as Record<string, string>
    expect(headers['Last-Event-ID']).toBe('last-id-123')
  })
})
