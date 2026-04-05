<script lang="ts">
  import { graphStore } from '$lib/stores/graphStore'
  import { sessionStore } from '$lib/stores/sessionStore'
  import { applyDagreLayout } from '$lib/utils/graphLayout'
  import { get } from 'svelte/store'
  import { updateGraph } from '$lib/services/sessionService'

  async function autoLayout() {
    const { nodes, edges } = get(graphStore)
    // Force re-layout of all nodes (temporarily clear userPositioned)
    const resetNodes = nodes.map((n) => ({ ...n, userPositioned: false }))
    const laid = applyDagreLayout(resetNodes, edges)
    graphStore.setGraph({ nodes: laid, edges })
    const { currentSessionId } = get(sessionStore)
    if (currentSessionId) {
      await updateGraph(currentSessionId, { nodes: laid, edges } as Record<string, unknown>)
    }
  }
</script>

<div class="absolute top-4 left-4 z-10 flex gap-2">
  <button
    onclick={autoLayout}
    class="bg-gray-800/90 border border-gray-700 hover:border-gray-500 text-xs text-gray-300 px-3 py-1.5 rounded-lg transition-colors backdrop-blur-sm"
  >
    Auto-layout
  </button>
</div>
