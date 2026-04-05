<script lang="ts">
  import { sessionStore } from '$lib/stores/sessionStore'
  import { updateSession } from '$lib/services/sessionService'

  const session = $derived($sessionStore.currentSession)
  const selectedModel = $derived($sessionStore.selectedModel)

  const MODELS = [
    { id: 'claude-haiku-4-5', label: 'Haiku' },
    { id: 'claude-sonnet-4-6', label: 'Sonnet' },
    { id: 'claude-opus-4-6', label: 'Opus' },
  ]

  async function handleChange(e: Event) {
    const model = (e.target as HTMLSelectElement).value
    sessionStore.setSelectedModel(model)
    if (session) {
      try {
        await updateSession(session.id, { selected_model: model })
      } catch {
        // ignore
      }
    }
  }
</script>

<select
  value={selectedModel}
  onchange={handleChange}
  class="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-300 focus:outline-none focus:border-indigo-500"
>
  {#each MODELS as m}
    <option value={m.id}>{m.label}</option>
  {/each}
</select>
