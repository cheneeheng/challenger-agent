import type { AnalysisGraph } from '$lib/schemas/graph'

export const GRAPH_WARN_NODES = 150
export const GRAPH_MAX_NODES = 200
export const GRAPH_MAX_EDGES = 400

export interface GraphGuardResult {
  allowed: boolean
  warning: string | null
}

/**
 * Validates graph size before sending to backend.
 * Returns { allowed: false } when over the hard limit; warns between 150-200 nodes.
 */
export function checkGraphSize(graph: AnalysisGraph): GraphGuardResult {
  const nodeCount = graph.nodes.length
  const edgeCount = graph.edges.length

  if (nodeCount > GRAPH_MAX_NODES) {
    return {
      allowed: false,
      warning: `Graph has ${nodeCount} nodes — maximum is ${GRAPH_MAX_NODES}. Delete some nodes before continuing.`,
    }
  }

  if (edgeCount > GRAPH_MAX_EDGES) {
    return {
      allowed: false,
      warning: `Graph has ${edgeCount} edges — maximum is ${GRAPH_MAX_EDGES}. Remove some connections before continuing.`,
    }
  }

  if (nodeCount >= GRAPH_WARN_NODES) {
    return {
      allowed: true,
      warning: `Graph is getting large (${nodeCount} nodes). Consider deleting unused nodes to keep responses fast.`,
    }
  }

  return { allowed: true, warning: null }
}
