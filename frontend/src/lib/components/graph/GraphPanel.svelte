<script lang="ts" module>
  // nodeTypes MUST be at module level — not inside reactive scope
  import AnalysisNodeComponent from './nodes/AnalysisNodeComponent.svelte'
  const nodeTypes = { analysisNode: AnalysisNodeComponent }
</script>

<script lang="ts">
  import {
    SvelteFlow,
    Background,
    Controls,
    MiniMap,
    type Node,
    type Edge,
  } from '@xyflow/svelte'
  import '@xyflow/svelte/dist/style.css'
  import { derived, get } from 'svelte/store'
  import { graphStore } from '$lib/stores/graphStore'
  import { sessionStore } from '$lib/stores/sessionStore'
  import { updateGraph } from '$lib/services/sessionService'
  import GraphToolbar from './GraphToolbar.svelte'
  import NodeDetailPanel from './NodeDetailPanel.svelte'

  const rfNodes = derived(graphStore, ($g) =>
    $g.nodes.map(
      (n) =>
        ({
          id: n.id,
          type: 'analysisNode',
          position: n.position,
          data: n,
          selected: n.id === $g.selectedNodeId,
        }) satisfies Node
    )
  )

  const rfEdges = derived(graphStore, ($g) =>
    $g.edges.map(
      (e) =>
        ({
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.label,
        }) satisfies Edge
    )
  )

  const selectedNodeId = $derived($graphStore.selectedNodeId)

  function onnodedragstop({
    targetNode,
  }: {
    targetNode: Node | null
    nodes: Node[]
    event: MouseEvent | TouchEvent
  }) {
    if (!targetNode) return
    graphStore.setNodePosition(targetNode.id, targetNode.position.x, targetNode.position.y)
    const { currentSessionId } = get(sessionStore)
    if (currentSessionId) {
      const { nodes, edges } = get(graphStore)
      updateGraph(currentSessionId, { nodes, edges } as Record<string, unknown>)
    }
  }

  function onnodeclick({ node }: { node: Node; event: MouseEvent | TouchEvent }) {
    graphStore.setSelectedNodeId(node.id)
  }

  function onpaneclick(_: { event: MouseEvent }) {
    graphStore.setSelectedNodeId(null)
  }

  function ondelete({ nodes, edges }: { nodes: Node[]; edges: Edge[] }) {
    for (const n of nodes) {
      if (n.id !== 'root') graphStore.deleteNode(n.id)
    }
    for (const e of edges) {
      graphStore.deleteEdge(e.id)
    }
  }
</script>

<div class="relative h-full w-full">
  <SvelteFlow
    nodes={$rfNodes}
    edges={$rfEdges}
    {nodeTypes}
    fitView
    colorMode="dark"
    {onnodedragstop}
    {onnodeclick}
    {onpaneclick}
    {ondelete}
  >
    <Background />
    <Controls />
    <MiniMap nodeColor="#4b5563" maskColor="rgba(0,0,0,0.7)" />
  </SvelteFlow>

  <GraphToolbar />

  {#if selectedNodeId}
    <NodeDetailPanel nodeId={selectedNodeId} />
  {/if}
</div>

<style>
  :global(.svelte-flow) {
    background-color: #0f172a;
  }
</style>
