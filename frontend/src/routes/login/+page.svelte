<script lang="ts">
  import { goto } from '$app/navigation'
  import { toast } from 'svelte-sonner'
  import { authStore } from '$lib/stores/authStore'
  import { login, getMe } from '$lib/services/authService'

  let email = $state('')
  let password = $state('')
  let isLoading = $state(false)

  async function handleSubmit(e: SubmitEvent) {
    e.preventDefault()
    if (isLoading) return
    isLoading = true

    try {
      const { access_token } = await login(email, password)
      authStore.setAccessToken(access_token)
      const user = await getMe()
      authStore.setUser(user)
      goto('/')
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? 'Login failed. Please try again.'
      toast.error(msg)
    } finally {
      isLoading = false
    }
  }
</script>

<svelte:head>
  <title>Login — IdeaLens</title>
</svelte:head>

<div class="min-h-screen bg-gray-950 flex items-center justify-center px-4">
  <div class="w-full max-w-md">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold text-white">IdeaLens</h1>
      <p class="text-gray-400 mt-2">Analyze your ideas with AI</p>
    </div>

    <div class="bg-gray-900 rounded-xl border border-gray-800 p-8">
      <h2 class="text-xl font-semibold text-white mb-6">Sign in</h2>

      <form onsubmit={handleSubmit} class="space-y-4">
        <div>
          <label for="email" class="block text-sm text-gray-400 mb-1">Email</label>
          <input
            id="email"
            type="email"
            bind:value={email}
            required
            autocomplete="email"
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label for="password" class="block text-sm text-gray-400 mb-1">Password</label>
          <input
            id="password"
            type="password"
            bind:value={password}
            required
            autocomplete="current-password"
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
            placeholder="••••••••"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading}
          class="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium py-2 rounded-lg transition-colors"
        >
          {isLoading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      <p class="text-center text-gray-500 text-sm mt-6">
        No account?
        <a href="/register" class="text-indigo-400 hover:text-indigo-300">Register</a>
      </p>
    </div>
  </div>
</div>
