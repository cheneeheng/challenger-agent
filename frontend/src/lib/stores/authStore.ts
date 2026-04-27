import { writable } from 'svelte/store'

export interface AuthUser {
  id: string
  email: string
  name: string
  has_api_key: boolean
}

interface AuthState {
  user: AuthUser | null
  accessToken: string | null
}

function createAuthStore() {
  const { subscribe, set, update } = writable<AuthState>({
    user: null,
    accessToken: null,
  })

  return {
    subscribe,

    init() {
      if (typeof localStorage === 'undefined') return
      try {
        const stored = localStorage.getItem('auth')
        if (stored) {
          const parsed = JSON.parse(stored) as AuthState
          set(parsed)
        }
      } catch {
        // ignore
      }
    },

    setUser(user: AuthUser | null) {
      update((s) => {
        const next = { ...s, user }
        if (typeof localStorage !== 'undefined') {
          localStorage.setItem('auth', JSON.stringify(next))
        }
        return next
      })
    },

    setAccessToken(token: string | null) {
      update((s) => {
        const next = { ...s, accessToken: token }
        if (typeof localStorage !== 'undefined') {
          localStorage.setItem('auth', JSON.stringify(next))
        }
        return next
      })
    },

    updateUser(partial: Partial<AuthUser>) {
      update((s) => {
        const next = { ...s, user: s.user ? { ...s.user, ...partial } : null }
        if (typeof localStorage !== 'undefined') {
          localStorage.setItem('auth', JSON.stringify(next))
        }
        return next
      })
    },

    logout() {
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('auth')
      }
      set({ user: null, accessToken: null })
    },
  }
}

export const authStore = createAuthStore()
