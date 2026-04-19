<script lang="ts">
  import { graphStore } from '$lib/stores/graphStore'
  import { sessionStore } from '$lib/stores/sessionStore'
  import { applyDagreLayout } from '$lib/utils/graphLayout'
  import { get } from 'svelte/store'
  import { updateGraph } from '$lib/services/sessionService'
  import AddNodeModal from './AddNodeModal.svelte'

  let { onSystemMessage }: { onSystemMessage?: (msg: string) => void } = $props()

  let showAddModal = $state(false)

  async function autoLayout() {
    const { nodes, edges } = get(graphStore)
    const resetNodes = nodes.map((n) => ({ ...n, userPositioned: false }))
    const laid = applyDagreLayout(resetNodes, edges)
    graphStore.setGraph({ nodes: laid, edges })
    const { currentSessionId } = get(sessionStore)
    if (currentSessionId) {
      await updateGraph(currentSessionId, { nodes: laid, edges } as Record<string, unknown>)
    }
  }

  async function deleteSelected() {
    const { nodes, edges, selectedNodeId } = get(graphStore)
    if (!selectedNodeId || selectedNodeId === 'root') return
    graphStore.deleteNode(selectedNodeId)
    onSystemMessage?.(`[User action: deleted node "${nodes.find((n) => n.id === selectedNodeId)?.label ?? selectedNodeId}"]`)
    const updated = get(graphStore)
    const { currentSessionId } = get(sessionStore)
    if (currentSessionId) {
      await updateGraph(currentSessionId, { nodes: updated.nodes, edges: updated.edges } as Record<string, unknown>)
    }
  }

  const hasSelected = $derived($graphStore.selectedNodeId !== null && $graphStore.selectedNodeId !== 'root')
</script>

<div class="absolute top-4 left-4 z-10 flex gap-2">
  <button
    onclick={autoLayout}
    class="bg-gray-800/90 border border-gray-700 hover:border-gray-500 text-xs text-gray-300 px-3 py-1.5 rounded-lg transition-colors backdrop-blur-sm"
  >
    Auto-layout
  </button>
  <button
    onclick={() => (showAddModal = true)}
    class="bg-gray-800/90 border border-gray-700 hover:border-indigo-500 text-xs text-gray-300 px-3 py-1.5 rounded-lg transition-colors backdrop-blur-sm"
  >
    + Add Node
  </button>
  {#if hasSelected}
    <button
      onclick={deleteSelected}
      class="bg-gray-800/90 border border-red-800 hover:border-red-500 text-xs text-red-400 px-3 py-1.5 rounded-lg transition-colors backdrop-blur-sm"
    >
      Delete Selected
    </button>
  {/if}
</div>

{#if showAddModal}
  <AddNodeModal
    onClose={() => (showAddModal = false)}
    onSystemMessage={(msg) => onSystemMessage?.(msg)}
  />
{/if}
