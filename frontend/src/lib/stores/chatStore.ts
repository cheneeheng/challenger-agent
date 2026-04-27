import { writable } from 'svelte/store'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  isStreaming?: boolean
}

interface ChatState {
  messages: ChatMessage[]
  isStreaming: boolean
  error: string | null
}

function createChatStore() {
  const { subscribe, set, update } = writable<ChatState>({
    messages: [],
    isStreaming: false,
    error: null,
  })

  return {
    subscribe,

    clear() {
      set({ messages: [], isStreaming: false, error: null })
    },

    setMessages(messages: ChatMessage[]) {
      update((s) => ({ ...s, messages }))
    },

    addMessage(msg: ChatMessage) {
      update((s) => ({ ...s, messages: [...s.messages, msg] }))
    },

    appendToken(token: string) {
      update((s) => {
        const msgs = [...s.messages]
        const last = msgs[msgs.length - 1]
        if (last && last.isStreaming) {
          msgs[msgs.length - 1] = { ...last, content: last.content + token }
        }
        return { ...s, messages: msgs }
      })
    },

    finalizeMessage() {
      update((s) => {
        const msgs = s.messages.map((m) =>
          m.isStreaming ? { ...m, isStreaming: false } : m
        )
        return { ...s, messages: msgs, isStreaming: false }
      })
    },

    setError(err: string | null) {
      update((s) => ({ ...s, error: err, isStreaming: false }))
    },

    setStreaming(streaming: boolean) {
      update((s) => ({ ...s, isStreaming: streaming }))
    },
  }
}

export const chatStore = createChatStore()
