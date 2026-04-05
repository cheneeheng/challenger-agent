<script lang="ts">
  import { goto } from '$app/navigation'
  import { authStore } from '$lib/stores/authStore'
  import { sessionStore } from '$lib/stores/sessionStore'
  import { updateSession } from '$lib/services/sessionService'
  import { toast } from 'svelte-sonner'

  const session = $derived($sessionStore.currentSession)

  let editingName = $state(false)
  let nameInput = $state('')

  function startEdit() {
    nameInput = session?.name ?? ''
    editingName = true
  }

  async function saveName() {
    if (!session || !nameInput.trim()) { editingName = false; return }
    try {
      await updateSession(session.id, { name: nameInput.trim() })
      sessionStore.updateCurrentSession({ name: nameInput.trim() })
    } catch {
      toast.error('Failed to rename session')
    }
    editingName = false
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') saveName()
    if (e.key === 'Escape') editingName = false
  }
</script>

<header class="border-b border-gray-800 px-4 py-3 flex items-center justify-between bg-gray-950 shrink-0">
  <div class="flex items-center gap-4">
    <button
      onclick={() => goto('/')}
      class="text-indigo-400 font-bold text-lg hover:text-indigo-300 transition-colors"
    >
      IdeaLens
    </button>

    {#if session}
      <span class="text-gray-600">/</span>
      {#if editingName}
        <!-- svelte-ignore a11y_autofocus -->
        <input
          type="text"
          bind:value={nameInput}
          onblur={saveName}
          onkeydown={handleKeydown}
          class="bg-gray-800 border border-indigo-500 rounded px-2 py-0.5 text-white text-sm w-64 focus:outline-none"
          autofocus
        />
      {:else}
        <button
          onclick={startEdit}
          class="text-gray-300 text-sm hover:text-white transition-colors truncate max-w-xs"
          title="Click to rename"
        >
          {session.name}
        </button>
      {/if}
    {/if}
  </div>

  <a href="/settings" class="text-sm text-gray-500 hover:text-white transition-colors">Settings</a>
</header>
