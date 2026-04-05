<script lang="ts">
  import { goto } from '$app/navigation'
  import { onMount } from 'svelte'
  import { toast } from 'svelte-sonner'
  import { authStore } from '$lib/stores/authStore'
  import { sessionStore } from '$lib/stores/sessionStore'
  import { listSessions, createSession, deleteSession } from '$lib/services/sessionService'
  import { formatDistanceToNow } from 'date-fns'

  const user = $derived($authStore.user)

  let sessions = $state<Awaited<ReturnType<typeof listSessions>>['items']>([])
  let isLoading = $state(true)
  let showNewModal = $state(false)

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
      const data = await listSessions()
      sessions = data.items
    } catch {
      toast.error('Failed to load sessions')
    } finally {
      isLoading = false
    }
  })

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

  async function handleDelete(id: string, e: MouseEvent) {
    e.stopPropagation()
    try {
      await deleteSession(id)
      sessions = sessions.filter((s) => s.id !== id)
      toast.success('Session deleted')
    } catch {
      toast.error('Failed to delete session')
    }
  }

  function formatDate(dateStr: string) {
    try {
      return formatDistanceToNow(new Date(dateStr), { addSuffix: true })
    } catch {
      return dateStr
    }
  }
</script>

<svelte:head>
  <title>Dashboard — IdeaLens</title>
</svelte:head>

<div class="min-h-screen bg-gray-950 text-white">
  <!-- Header -->
  <header class="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
    <h1 class="text-xl font-bold text-indigo-400">IdeaLens</h1>
    <div class="flex items-center gap-4">
      <a href="/settings" class="text-sm text-gray-400 hover:text-white transition-colors">Settings</a>
      <span class="text-gray-600 text-sm">{user?.name ?? ''}</span>
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
      <div class="text-center py-20 text-gray-500">Loading…</div>
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
          <!-- Use div+role instead of button to allow nested interactive elements -->
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
    {/if}
  </main>
</div>

<!-- New Analysis Modal -->
{#if showNewModal}
  <div
    class="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4"
    role="dialog"
    aria-modal="true"
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
