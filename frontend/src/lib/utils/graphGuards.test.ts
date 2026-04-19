import { describe, it, expect } from 'vitest'
import { checkGraphSize, GRAPH_WARN_NODES, GRAPH_MAX_NODES, GRAPH_MAX_EDGES } from './graphGuards'
import type { AnalysisGraph } from '$lib/schemas/graph'

function makeGraph(nodeCount: number, edgeCount = 0): AnalysisGraph {
  const nodes = Array.from({ length: nodeCount }, (_, i) => ({
    id: `n${i}`,
    type: 'concept' as const,
    label: `Node ${i}`,
    content: 'content',
    score: null,
    parent_id: null,
    position: { x: i * 10, y: 0 },
    userPositioned: false,
  }))
  const edges = Array.from({ length: edgeCount }, (_, i) => ({
    id: `e${i}`,
    source: `n${i % nodeCount}`,
    target: `n${(i + 1) % nodeCount}`,
  }))
  return { nodes, edges }
}

describe('checkGraphSize', () => {
  it('allows an empty graph', () => {
    const result = checkGraphSize({ nodes: [], edges: [] })
    expect(result.allowed).toBe(true)
    expect(result.warning).toBeNull()
  })

  it('allows a small graph with no warning', () => {
    const result = checkGraphSize(makeGraph(10))
    expect(result.allowed).toBe(true)
    expect(result.warning).toBeNull()
  })

  it('warns when node count reaches the warning threshold', () => {
    const result = checkGraphSize(makeGraph(GRAPH_WARN_NODES))
    expect(result.allowed).toBe(true)
    expect(result.warning).not.toBeNull()
    expect(result.warning).toMatch(/150/)
  })

  it('blocks when node count exceeds the hard limit', () => {
    const result = checkGraphSize(makeGraph(GRAPH_MAX_NODES + 1))
    expect(result.allowed).toBe(false)
    expect(result.warning).toMatch(/maximum/)
  })

  it('blocks when edge count exceeds the hard limit', () => {
    const result = checkGraphSize(makeGraph(10, GRAPH_MAX_EDGES + 1))
    expect(result.allowed).toBe(false)
    expect(result.warning).toMatch(/edges/)
  })

  it('allows exactly at the hard limit (> not >=)', () => {
    // GRAPH_MAX_NODES = 200: condition is nodeCount > 200, so 200 exactly is allowed (with warning)
    const result = checkGraphSize(makeGraph(GRAPH_MAX_NODES))
    expect(result.allowed).toBe(true)
    expect(result.warning).not.toBeNull() // warns because >= GRAPH_WARN_NODES
  })
})
