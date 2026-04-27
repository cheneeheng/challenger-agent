<script lang="ts">
  import { graphStore } from '$lib/stores/graphStore'
  import { sessionStore } from '$lib/stores/sessionStore'
  import { getIncrementalPosition } from '$lib/utils/graphLayout'
  import { updateGraph } from '$lib/services/sessionService'
  import { dimensionTypeSchema, type DimensionType } from '$lib/schemas/graph'
  import { get } from 'svelte/store'
  import { v4 as uuidv4 } from 'uuid'

  let { onClose, onSystemMessage }: {
    onClose: () => void
    onSystemMessage: (msg: string) => void
  } = $props()

  const DIMENSION_TYPES: { value: DimensionType; label: string }[] = [
    { value: 'concept', label: 'Core Concept' },
    { value: 'requirement', label: 'Requirement' },
    { value: 'benefit', label: 'Benefit' },
    { value: 'drawback', label: 'Drawback' },
    { value: 'gap', label: 'Gap' },
    { value: 'feasibility', label: 'Feasibility' },
    { value: 'flaw', label: 'Flaw' },
    { value: 'alternative', label: 'Alternative' },
    { value: 'question', label: 'Open Question' },
  ]

  let selectedType = $state<DimensionType>('concept')
  let label = $state('')
  let content = $state('')
  let saving = $state(false)

  async function handleAdd() {
    if (!label.trim() || !content.trim() || saving) return
    saving = true
    try {
      const { nodes, edges } = get(graphStore)
      const position = getIncrementalPosition(null, nodes)
      const newNode = {
        id: uuidv4(),
        type: selectedType,
        label: label.trim(),
        content: content.trim(),
        score: null,
        parent_id: null,
        position,
        userPositioned: false,
      }
      graphStore.addNode(newNode)
      const { currentSessionId } = get(sessionStore)
      if (currentSessionId) {
        const updated = get(graphStore)
        await updateGraph(currentSessionId, { nodes: updated.nodes, edges: updated.edges } as Record<string, unknown>)
      }
      onSystemMessage(`[User action: added node "${label.trim()}" (${selectedType})]`)
      onClose()
    } finally {
      saving = false
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onClose()
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- Backdrop -->
<div
  class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center"
  onclick={onClose}
  onkeydown={(e) => e.key === 'Escape' && onClose()}
  role="dialog"
  aria-modal="true"
  aria-label="Add node"
  tabindex="-1"
>
  <!-- Modal -->
  <div
    class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md shadow-2xl"
    onclick={(e) => e.stopPropagation()}
    role="none"
  >
    <h2 class="text-white font-semibold text-base mb-4">Add Node</h2>

    <div class="space-y-4">
      <div>
        <label class="text-xs text-gray-400 block mb-1" for="node-type">Type</label>
        <select
          id="node-type"
          bind:value={selectedType}
          class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
        >
          {#each DIMENSION_TYPES as dt}
            <option value={dt.value}>{dt.label}</option>
          {/each}
        </select>
      </div>

      <div>
        <label class="text-xs text-gray-400 block mb-1" for="node-label">Label</label>
        <input
          id="node-label"
          bind:value={label}
          type="text"
          placeholder="Short title…"
          class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
        />
      </div>

      <div>
        <label class="text-xs text-gray-400 block mb-1" for="node-content">Content</label>
        <textarea
          id="node-content"
          bind:value={content}
          rows={3}
          placeholder="Describe this node…"
          class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 resize-none"
        ></textarea>
      </div>
    </div>

    <div class="flex justify-end gap-3 mt-6">
      <button
        onclick={onClose}
        class="text-sm text-gray-400 hover:text-white px-4 py-2 transition-colors"
      >
        Cancel
      </button>
      <button
        onclick={handleAdd}
        disabled={!label.trim() || !content.trim() || saving}
        class="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-sm px-4 py-2 rounded-lg transition-colors"
      >
        {saving ? 'Adding…' : 'Add Node'}
      </button>
    </div>
  </div>
</div>
