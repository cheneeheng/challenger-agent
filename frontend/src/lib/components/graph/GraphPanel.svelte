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
    type Connection,
  } from '@xyflow/svelte'
  import '@xyflow/svelte/dist/style.css'
  import { derived, get } from 'svelte/store'
  import { v4 as uuidv4 } from 'uuid'
  import { graphStore } from '$lib/stores/graphStore'
  import { sessionStore } from '$lib/stores/sessionStore'
  import { updateGraph } from '$lib/services/sessionService'
  import GraphToolbar from './GraphToolbar.svelte'
  import NodeDetailPanel from './NodeDetailPanel.svelte'
  import FitViewEffect from './FitViewEffect.svelte'

  let {
    onSystemMessage,
    handleAskClaude,
  }: {
    onSystemMessage?: (msg: string) => void
    handleAskClaude?: (text: string) => void
  } = $props()

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

  // Context menu state
  let contextMenu = $state<{ nodeId: string; label: string; x: number; y: number } | null>(null)

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
    contextMenu = null
    graphStore.setSelectedNodeId(node.id)
  }

  function onpaneclick(_: { event: MouseEvent }) {
    contextMenu = null
    graphStore.setSelectedNodeId(null)
  }

  function ondelete({ nodes, edges }: { nodes: Node[]; edges: Edge[] }) {
    for (const n of nodes) {
      if (n.id !== 'root') {
        onSystemMessage?.(`[User action: deleted node "${n.data?.label ?? n.id}"]`)
        graphStore.deleteNode(n.id)
      }
    }
    for (const e of edges) {
      graphStore.deleteEdge(e.id)
    }
    const { currentSessionId } = get(sessionStore)
    if (currentSessionId) {
      const { nodes: gn, edges: ge } = get(graphStore)
      updateGraph(currentSessionId, { nodes: gn, edges: ge } as Record<string, unknown>)
    }
  }

  function onconnect(connection: Connection) {
    const { source, target } = connection
    if (!source || !target) return
    const edgeId = `edge-${source}-${target}-${uuidv4().slice(0, 8)}`
    graphStore.addEdge({ id: edgeId, source, target })
    const { currentSessionId } = get(sessionStore)
    if (currentSessionId) {
      const { nodes, edges } = get(graphStore)
      updateGraph(currentSessionId, { nodes, edges } as Record<string, unknown>)
    }
  }

  function onnodecontextmenu({ node, event }: { node: Node; event: MouseEvent }) {
    event.preventDefault()
    contextMenu = {
      nodeId: node.id,
      label: (node.data as { label?: string })?.label ?? node.id,
      x: event.clientX,
      y: event.clientY,
    }
  }

  function closeContextMenu() {
    contextMenu = null
  }

  function contextMenuEdit() {
    if (!contextMenu) return
    graphStore.setSelectedNodeId(contextMenu.nodeId)
    contextMenu = null
  }

  function contextMenuDelete() {
    if (!contextMenu) return
    const { nodeId, label } = contextMenu
    if (nodeId === 'root') { contextMenu = null; return }
    onSystemMessage?.(`[User action: deleted node "${label}"]`)
    graphStore.deleteNode(nodeId)
    const { currentSessionId } = get(sessionStore)
    if (currentSessionId) {
      const { nodes, edges } = get(graphStore)
      updateGraph(currentSessionId, { nodes, edges } as Record<string, unknown>)
    }
    contextMenu = null
  }

  function contextMenuAskClaude() {
    if (!contextMenu) return
    handleAskClaude?.(`Tell me more about: ${contextMenu.label}`)
    contextMenu = null
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') contextMenu = null
  }
</script>

<svelte:window onkeydown={handleKeydown} />

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
    {onconnect}
    {onnodecontextmenu}
  >
    <FitViewEffect />
    <Background />
    <Controls />
    <MiniMap nodeColor="#4b5563" maskColor="rgba(0,0,0,0.7)" />
  </SvelteFlow>

  <GraphToolbar {onSystemMessage} />

  {#if selectedNodeId}
    <NodeDetailPanel
      nodeId={selectedNodeId}
      {onSystemMessage}
      {handleAskClaude}
    />
  {/if}

  <!-- Right-click context menu -->
  {#if contextMenu}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="fixed z-50 bg-gray-800 border border-gray-600 rounded-lg shadow-xl py-1 min-w-[160px] text-sm"
      style="top: {contextMenu.y}px; left: {contextMenu.x}px"
      onmouseleave={closeContextMenu}
    >
      <button
        onclick={contextMenuEdit}
        class="w-full text-left px-4 py-2 text-gray-200 hover:bg-gray-700 transition-colors"
      >
        Edit
      </button>
      {#if handleAskClaude}
        <button
          onclick={contextMenuAskClaude}
          class="w-full text-left px-4 py-2 text-gray-200 hover:bg-gray-700 transition-colors"
        >
          Ask Claude about this
        </button>
      {/if}
      {#if contextMenu.nodeId !== 'root'}
        <div class="border-t border-gray-700 my-1"></div>
        <button
          onclick={contextMenuDelete}
          class="w-full text-left px-4 py-2 text-red-400 hover:bg-gray-700 transition-colors"
        >
          Delete
        </button>
      {/if}
    </div>
  {/if}
</div>

<style>
  :global(.svelte-flow) {
    background-color: #0f172a;
  }
</style>
