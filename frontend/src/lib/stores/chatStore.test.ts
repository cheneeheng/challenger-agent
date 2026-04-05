import { describe, it, expect, beforeEach } from 'vitest'
import { get } from 'svelte/store'
import { chatStore } from './chatStore'
import type { ChatMessage } from './chatStore'

const MSG_USER: ChatMessage = { id: 'u1', role: 'user', content: 'Hello' }
const MSG_STREAMING: ChatMessage = { id: 'a1', role: 'assistant', content: '', isStreaming: true }

beforeEach(() => {
  chatStore.clear()
})

describe('chatStore', () => {
  it('starts empty and not streaming', () => {
    const state = get(chatStore)
    expect(state.messages).toHaveLength(0)
    expect(state.isStreaming).toBe(false)
    expect(state.error).toBeNull()
  })

  it('addMessage appends', () => {
    chatStore.addMessage(MSG_USER)
    expect(get(chatStore).messages).toHaveLength(1)
    expect(get(chatStore).messages[0].content).toBe('Hello')
  })

  it('setMessages replaces all', () => {
    chatStore.addMessage(MSG_USER)
    chatStore.setMessages([MSG_STREAMING])
    expect(get(chatStore).messages).toHaveLength(1)
    expect(get(chatStore).messages[0].id).toBe('a1')
  })

  it('appendToken adds to last streaming message', () => {
    chatStore.addMessage(MSG_USER)
    chatStore.addMessage(MSG_STREAMING)
    chatStore.appendToken('Hel')
    chatStore.appendToken('lo')
    expect(get(chatStore).messages[1].content).toBe('Hello')
  })

  it('appendToken is a no-op when last message is not streaming', () => {
    chatStore.addMessage(MSG_USER)
    chatStore.appendToken('should not append')
    expect(get(chatStore).messages[0].content).toBe('Hello')
  })

  it('appendToken is a no-op when no messages', () => {
    chatStore.appendToken('x')
    expect(get(chatStore).messages).toHaveLength(0)
  })

  it('finalizeMessage clears isStreaming on all messages', () => {
    chatStore.addMessage(MSG_USER)
    chatStore.addMessage(MSG_STREAMING)
    chatStore.finalizeMessage()
    const state = get(chatStore)
    expect(state.isStreaming).toBe(false)
    expect(state.messages.every((m) => !m.isStreaming)).toBe(true)
  })

  it('setStreaming toggles streaming state', () => {
    chatStore.setStreaming(true)
    expect(get(chatStore).isStreaming).toBe(true)
    chatStore.setStreaming(false)
    expect(get(chatStore).isStreaming).toBe(false)
  })

  it('setError sets error and clears streaming', () => {
    chatStore.setStreaming(true)
    chatStore.setError('Something went wrong')
    const state = get(chatStore)
    expect(state.error).toBe('Something went wrong')
    expect(state.isStreaming).toBe(false)
  })

  it('setError with null clears error', () => {
    chatStore.setError('err')
    chatStore.setError(null)
    expect(get(chatStore).error).toBeNull()
  })

  it('clear resets everything', () => {
    chatStore.addMessage(MSG_USER)
    chatStore.setError('e')
    chatStore.setStreaming(true)
    chatStore.clear()
    const state = get(chatStore)
    expect(state.messages).toHaveLength(0)
    expect(state.error).toBeNull()
    expect(state.isStreaming).toBe(false)
  })
})
