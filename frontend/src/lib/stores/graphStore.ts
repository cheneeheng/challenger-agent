import { writable, get } from 'svelte/store'
import { v4 as uuidv4 } from 'uuid'
import type { LLMGraphAction, AnalysisGraph, AnalysisNode, AnalysisEdge } from '$lib/schemas/graph'

interface GraphState {
  nodes: AnalysisNode[]
  edges: AnalysisEdge[]
  selectedNodeId: string | null
}

function createGraphStore() {
  const { subscribe, set, update } = writable<GraphState>({
    nodes: [],
    edges: [],
    selectedNodeId: null,
  })

  return {
    subscribe,

    clearGraph() {
      set({ nodes: [], edges: [], selectedNodeId: null })
    },

    setGraph(graph: AnalysisGraph) {
      update((s) => ({ ...s, nodes: graph.nodes, edges: graph.edges }))
    },

    setSelectedNodeId(id: string | null) {
      update((s) => ({ ...s, selectedNodeId: id }))
    },

    addNode(node: AnalysisNode) {
      update((s) => ({ ...s, nodes: [...s.nodes, node] }))
    },

    updateNode(id: string, changes: Partial<AnalysisNode>) {
      update((s) => ({
        ...s,
        nodes: s.nodes.map((n) => (n.id === id ? { ...n, ...changes } : n)),
      }))
    },

    deleteNode(id: string) {
      update((s) => ({
        ...s,
        nodes: s.nodes.filter((n) => n.id !== id),
        edges: s.edges.filter((e) => e.source !== id && e.target !== id),
        selectedNodeId: s.selectedNodeId === id ? null : s.selectedNodeId,
      }))
    },

    addEdge(edge: AnalysisEdge) {
      update((s) => ({ ...s, edges: [...s.edges, edge] }))
    },

    deleteEdge(id: string) {
      update((s) => ({ ...s, edges: s.edges.filter((e) => e.id !== id) }))
    },

    setNodePosition(id: string, x: number, y: number) {
      update((s) => ({
        ...s,
        nodes: s.nodes.map((n) =>
          n.id === id
            ? { ...n, position: { x, y }, userPositioned: true }
            : n
        ),
      }))
    },

    applyGraphActions(actions: LLMGraphAction[]) {
      update((s) => {
        let { nodes, edges } = s

        for (const action of actions) {
          if (action.action === 'add') {
            const p = action.payload
            // Don't add if ID already exists
            if (nodes.find((n) => n.id === p.id)) continue

            const parent = p.parent_id ? nodes.find((n) => n.id === p.parent_id) : null
            const position = parent
              ? { x: parent.position.x + 220, y: parent.position.y + 100 }
              : { x: 200 + Math.random() * 400, y: 100 + Math.random() * 300 }

            nodes = [
              ...nodes,
              {
                id: p.id,
                type: p.type,
                label: p.label,
                content: p.content,
                score: p.score ?? null,
                parent_id: p.parent_id ?? null,
                position,
                userPositioned: false,
              },
            ]
          } else if (action.action === 'update') {
            const p = action.payload
            nodes = nodes.map((n) =>
              n.id === p.id
                ? {
                    ...n,
                    ...(p.label != null ? { label: p.label } : {}),
                    ...(p.content != null ? { content: p.content } : {}),
                  }
                : n
            )
          } else if (action.action === 'delete') {
            const { id } = action.payload
            if (id !== 'root') {
              nodes = nodes.filter((n) => n.id !== id)
              edges = edges.filter((e) => e.source !== id && e.target !== id)
            }
          } else if (action.action === 'connect') {
            const p = action.payload
            const edgeId = `edge-${p.source}-${p.target}-${uuidv4().slice(0, 8)}`
            if (!edges.find((e) => e.source === p.source && e.target === p.target)) {
              edges = [
                ...edges,
                {
                  id: edgeId,
                  source: p.source,
                  target: p.target,
                  label: p.label ?? undefined,
                  type: p.type ?? undefined,
                },
              ]
            }
          }
        }

        return { ...s, nodes, edges }
      })
    },

    getSnapshot(): GraphState {
      return get({ subscribe })
    },
  }
}

export const graphStore = createGraphStore()
