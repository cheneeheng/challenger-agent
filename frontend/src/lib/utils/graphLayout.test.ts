import { describe, it, expect } from 'vitest'
import { applyDagreLayout } from './graphLayout'
import type { AnalysisNode, AnalysisEdge } from '$lib/schemas/graph'

function node(id: string, userPositioned = false): AnalysisNode {
  return {
    id,
    type: 'concept',
    label: id,
    content: '',
    score: null,
    parent_id: null,
    position: { x: 0, y: 0 },
    userPositioned,
  }
}

describe('applyDagreLayout', () => {
  it('returns same count of nodes', () => {
    const nodes = [node('a'), node('b'), node('c')]
    const edges: AnalysisEdge[] = [
      { id: 'e1', source: 'a', target: 'b' },
      { id: 'e2', source: 'b', target: 'c' },
    ]
    const result = applyDagreLayout(nodes, edges)
    expect(result).toHaveLength(3)
  })

  it('assigns non-zero positions to nodes without userPositioned=true', () => {
    const nodes = [node('root'), node('child')]
    const edges: AnalysisEdge[] = [{ id: 'e1', source: 'root', target: 'child' }]
    const result = applyDagreLayout(nodes, edges)
    // Dagre should assign distinct x positions for a horizontal layout
    const rootNode = result.find((n) => n.id === 'root')!
    const childNode = result.find((n) => n.id === 'child')!
    expect(rootNode.position.x).not.toBe(childNode.position.x)
  })

  it('preserves userPositioned nodes positions', () => {
    const manualNode: AnalysisNode = { ...node('manual', true), position: { x: 999, y: 888 } }
    const autoNode = node('auto')
    const result = applyDagreLayout([manualNode, autoNode], [])
    const manual = result.find((n) => n.id === 'manual')!
    expect(manual.position).toEqual({ x: 999, y: 888 })
    expect(manual.userPositioned).toBe(true)
  })

  it('handles empty graph', () => {
    const result = applyDagreLayout([], [])
    expect(result).toHaveLength(0)
  })

  it('handles single node with no edges', () => {
    const result = applyDagreLayout([node('solo')], [])
    expect(result).toHaveLength(1)
    // Position should be set (dagre assigns some coordinate even for isolated nodes)
    expect(typeof result[0].position.x).toBe('number')
    expect(typeof result[0].position.y).toBe('number')
  })

  it('skips edges where one endpoint is userPositioned (not in layout set)', () => {
    const manualNode: AnalysisNode = { ...node('manual', true), position: { x: 500, y: 500 } }
    const autoNode = node('auto')
    // Edge from manual (userPositioned) to auto — should still layout auto node
    const edges: AnalysisEdge[] = [{ id: 'e1', source: 'manual', target: 'auto' }]
    const result = applyDagreLayout([manualNode, autoNode], edges)
    expect(result).toHaveLength(2)
    const manual = result.find((n) => n.id === 'manual')!
    expect(manual.position).toEqual({ x: 500, y: 500 }) // unchanged
  })
})
