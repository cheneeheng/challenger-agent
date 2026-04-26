<script lang="ts">
  import { goto } from '$app/navigation'
  import { onMount } from 'svelte'
  import { toast } from 'svelte-sonner'
  import { authStore } from '$lib/stores/authStore'
  import { listSessions, createSession, deleteSession } from '$lib/services/sessionService'
  import { logout as apiLogout } from '$lib/services/authService'
  import { formatDistanceToNow } from 'date-fns'

  const user = $derived($authStore.user)

  let sessions = $state<Awaited<ReturnType<typeof listSessions>>['items']>([])
  let isLoading = $state(true)
  let isLoadingMore = $state(false)
  let currentPage = $state(1)
  let totalSessions = $state(0)
  let showNewModal = $state(false)

  const hasMore = $derived(sessions.length < totalSessions)

  let newIdea = $state('')
  let newModel = $state('claude-sonnet-4-6')
  let creating = $state(false)

  const MODELS = [
    { id: 'claude-haiku-4-5', label: 'Claude Haiku (Fast)' },
    { id: 'claude-sonnet-4-6', label: 'Claude Sonnet (Default)' },
    { id: 'claude-opus-4-6', label: 'Claude Opus (Most thorough)' },
  ]

  onMount(async () => {
    try {
      const data = await listSessions(1, 20)
      sessions = data.items
      totalSessions = data.total
      currentPage = 1
    } catch {
      toast.error('Failed to load sessions')
    } finally {
      isLoading = false
    }
  })

  async function loadMore() {
    if (isLoadingMore || !hasMore) return
    isLoadingMore = true
    try {
      const nextPage = currentPage + 1
      const data = await listSessions(nextPage, 20)
      sessions = [...sessions, ...data.items]
      totalSessions = data.total
      currentPage = nextPage
    } catch {
      toast.error('Failed to load more sessions')
    } finally {
      isLoadingMore = false
    }
  }

  async function handleCreate() {
    if (!newIdea.trim() || creating) return
    creating = true
    try {
      const session = await createSession(newIdea.trim(), newModel)
      goto(`/session/${session.id}`)
    } catch {
      toast.error('Failed to create session')
      creating = false
    }
  }

  function handleDelete(id: string, e: MouseEvent) {
    e.stopPropagation()
    // Optimistic removal with 5s undo window
    const target = sessions.find((s) => s.id === id)
    if (!target) return
    sessions = sessions.filter((s) => s.id !== id)

    let undone = false
    const undoId = toast('Session deleted', {
      action: {
        label: 'Undo',
        onClick: () => {
          undone = true
          sessions = [target, ...sessions].sort(
            (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
          )
        },
      },
      duration: 5000,
      onDismiss: async () => {
        if (!undone) {
          try {
            await deleteSession(id)
          } catch {
            sessions = [target, ...sessions].sort(
              (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
            )
            toast.error('Failed to delete session')
          }
        }
      },
      onAutoClose: async () => {
        if (!undone) {
          try {
            await deleteSession(id)
          } catch {
            sessions = [target, ...sessions].sort(
              (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
            )
            toast.error('Failed to delete session')
          }
        }
      },
    })
  }

  function formatDate(dateStr: string) {
    try {
      return formatDistanceToNow(new Date(dateStr), { addSuffix: true })
    } catch {
      return dateStr
    }
  }

  async function handleLogout() {
    try { await apiLogout() } catch { /* ignore */ }
    authStore.logout()
    goto('/login')
  }

  function handleGlobalKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && showNewModal) {
      showNewModal = false
      newIdea = ''
    }
  }
</script>

<svelte:head>
  <title>Dashboard — IdeaLens</title>
</svelte:head>

<svelte:window onkeydown={handleGlobalKeydown} />

<div class="min-h-screen bg-gray-950 text-white">
  <!-- Header -->
  <header class="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
    <h1 class="text-xl font-bold text-indigo-400">IdeaLens</h1>
    <div class="flex items-center gap-4">
      <a href="/settings" class="text-sm text-gray-400 hover:text-white transition-colors">Settings</a>
      <span class="text-gray-600 text-sm">{user?.name ?? ''}</span>
      <button
        onclick={handleLogout}
        class="text-sm text-gray-500 hover:text-red-400 transition-colors"
      >
        Logout
      </button>
    </div>
  </header>

  <main class="max-w-4xl mx-auto px-6 py-10">
    <!-- API key banner -->
    {#if !user?.has_api_key}
      <a
        href="/settings?prompt=api-key"
        class="block mb-6 bg-yellow-900/40 border border-yellow-600 rounded-lg p-4 text-yellow-200 text-sm hover:bg-yellow-900/60 transition-colors"
      >
        Set your Anthropic API key to start analyzing ideas →
      </a>
    {/if}

    <div class="flex items-center justify-between mb-8">
      <h2 class="text-2xl font-semibold">Your Analyses</h2>
      <button
        onclick={() => (showNewModal = true)}
        class="bg-indigo-600 hover:bg-indigo-700 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
      >
        New Analysis
      </button>
    </div>

    {#if isLoading}
      <!-- Loading skeletons -->
      <div class="grid gap-4">
        {#each [1, 2, 3] as _}
          <div class="bg-gray-900 border border-gray-800 rounded-xl p-5 animate-pulse">
            <div class="flex items-start justify-between gap-4">
              <div class="flex-1 space-y-2">
                <div class="h-4 bg-gray-700 rounded w-1/3"></div>
                <div class="h-3 bg-gray-800 rounded w-2/3"></div>
              </div>
              <div class="flex gap-2">
                <div class="h-5 w-12 bg-gray-800 rounded"></div>
                <div class="h-5 w-20 bg-gray-800 rounded"></div>
              </div>
            </div>
          </div>
        {/each}
      </div>
    {:else if sessions.length === 0}
      <div class="text-center py-20">
        <p class="text-gray-400 text-lg mb-2">No analyses yet.</p>
        <p class="text-gray-600 text-sm">
          Click <strong class="text-gray-400">New Analysis</strong> to get started.
        </p>
      </div>
    {:else}
      <div class="grid gap-4">
        {#each sessions as session (session.id)}
          <div
            role="button"
            tabindex="0"
            onclick={() => goto(`/session/${session.id}`)}
            onkeydown={(e) => e.key === 'Enter' && goto(`/session/${session.id}`)}
            class="group relative bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-5 text-left transition-colors cursor-pointer"
          >
            <div class="flex items-start justify-between gap-4">
              <div class="flex-1 min-w-0">
                <h3 class="font-medium text-white truncate">{session.name}</h3>
                <p class="text-sm text-gray-500 mt-1 line-clamp-2">{session.idea}</p>
              </div>
              <div class="flex items-center gap-3 shrink-0">
                <span class="text-xs text-gray-600 bg-gray-800 px-2 py-1 rounded">
                  {session.selected_model.replace('claude-', '').split('-')[0]}
                </span>
                <span class="text-xs text-gray-600">{formatDate(session.updated_at)}</span>
                <button
                  onclick={(e) => handleDelete(session.id, e)}
                  class="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-400 transition-opacity text-xs px-2 py-1 rounded border border-red-800 hover:border-red-600"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        {/each}
      </div>

      {#if hasMore}
        <div class="mt-6 text-center">
          <button
            onclick={loadMore}
            disabled={isLoadingMore}
            class="text-sm text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 px-6 py-2 rounded-lg transition-colors disabled:opacity-50"
          >
            {isLoadingMore ? 'Loading…' : `Load more (${totalSessions - sessions.length} remaining)`}
          </button>
        </div>
      {/if}
    {/if}
  </main>
</div>

<!-- New Analysis Modal -->
{#if showNewModal}
  <div
    class="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4"
    role="dialog"
    aria-modal="true"
    aria-label="New analysis"
  >
    <div class="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg p-6">
      <h2 class="text-xl font-semibold mb-4">New Analysis</h2>

      <div class="space-y-4">
        <div>
          <label for="new-idea" class="block text-sm text-gray-400 mb-1">Your idea</label>
          <textarea
            id="new-idea"
            bind:value={newIdea}
            rows={4}
            placeholder="Describe your idea in as much detail as you'd like…"
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 resize-none"
          ></textarea>
        </div>

        <div>
          <label for="new-model" class="block text-sm text-gray-400 mb-1">Model</label>
          <select
            id="new-model"
            bind:value={newModel}
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
          >
            {#each MODELS as m}
              <option value={m.id}>{m.label}</option>
            {/each}
          </select>
        </div>
      </div>

      <div class="flex gap-3 mt-6">
        <button
          onclick={handleCreate}
          disabled={creating || !newIdea.trim()}
          class="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {creating ? 'Creating…' : 'Analyze'}
        </button>
        <button
          onclick={() => { showNewModal = false; newIdea = '' }}
          class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  </div>
{/if}
