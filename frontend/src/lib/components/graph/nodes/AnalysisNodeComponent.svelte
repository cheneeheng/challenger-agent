<script lang="ts">
  import { Handle, Position } from '@xyflow/svelte'
  import { scale } from 'svelte/transition'
  import { getNodeStyle } from '$lib/utils/graphStyles'
  import { highlightedNodeIds } from '$lib/stores/graphStore'
  import type { AnalysisNode } from '$lib/schemas/graph'

  let { data }: { data: AnalysisNode } = $props()

  const style = $derived(getNodeStyle(data.type))
  const isHighlighted = $derived($highlightedNodeIds.has(data.id))
</script>

<div
  in:scale={{ duration: 200, start: 0.85 }}
  class="rounded-lg border-2 px-3 py-2 min-w-[160px] max-w-[200px] text-left shadow-lg {style.bg} {style.border} {style.text} {isHighlighted ? 'node-pulse' : ''}"
>
  <Handle type="target" position={Position.Left} class="!bg-gray-500" />

  <div class="text-[10px] font-semibold uppercase tracking-wider opacity-60 mb-1">
    {style.label}
  </div>
  <div class="text-xs font-medium leading-snug line-clamp-2">
    {data.label}
  </div>
  {#if data.score != null}
    <div class="mt-1 text-[10px] opacity-75 font-mono">
      Score: {data.score}/10
    </div>
  {/if}

  <Handle type="source" position={Position.Right} class="!bg-gray-500" />
</div>

<style>
  @keyframes node-pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(99, 102, 241, 0); }
    50% { box-shadow: 0 0 0 6px rgba(99, 102, 241, 0.4); }
  }

  :global(.node-pulse) {
    animation: node-pulse 1s ease-in-out 2;
  }
</style>
