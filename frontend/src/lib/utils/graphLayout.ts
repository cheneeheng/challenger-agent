import dagre from '@dagrejs/dagre'
import type { AnalysisNode, AnalysisEdge } from '$lib/schemas/graph'

const NODE_WIDTH = 200
const NODE_HEIGHT = 80

export function applyDagreLayout(
  nodes: AnalysisNode[],
  edges: AnalysisEdge[]
): AnalysisNode[] {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'LR', nodesep: 60, ranksep: 100 })

  // Only layout nodes that have not been manually positioned
  const toLayout = nodes.filter((n) => !n.userPositioned)
  const positioned = nodes.filter((n) => n.userPositioned)

  for (const node of toLayout) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  }

  for (const edge of edges) {
    // Only add edges where both nodes are in the layout set
    const sourceInLayout = toLayout.some((n) => n.id === edge.source)
    const targetInLayout = toLayout.some((n) => n.id === edge.target)
    if (sourceInLayout && targetInLayout) {
      g.setEdge(edge.source, edge.target)
    }
  }

  dagre.layout(g)

  const layouted = toLayout.map((node) => {
    const pos = g.node(node.id)
    return pos
      ? {
          ...node,
          position: {
            x: pos.x - NODE_WIDTH / 2,
            y: pos.y - NODE_HEIGHT / 2,
          },
        }
      : node
  })

  return [...positioned, ...layouted]
}
