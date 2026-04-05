<script lang="ts">
  import { Handle, Position } from '@xyflow/svelte'
  import { getNodeStyle } from '$lib/utils/graphStyles'
  import type { AnalysisNode } from '$lib/schemas/graph'

  let { data }: { data: AnalysisNode } = $props()

  const style = $derived(getNodeStyle(data.type))
</script>

<div
  class="rounded-lg border-2 px-3 py-2 min-w-[160px] max-w-[200px] text-left shadow-lg {style.bg} {style.border} {style.text}"
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
