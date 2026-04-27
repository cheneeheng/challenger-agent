import { describe, it, expect, beforeEach } from 'vitest'
import { get } from 'svelte/store'

// Re-import fresh instance per test via factory pattern
import { graphStore } from './graphStore'

import type { AnalysisNode, AnalysisEdge } from '$lib/schemas/graph'

const ROOT: AnalysisNode = {
  id: 'root',
  type: 'root',
  label: 'My Idea',
  content: 'Root content',
  score: null,
  parent_id: null,
  position: { x: 400, y: 300 },
  userPositioned: false,
}

const CONCEPT: AnalysisNode = {
  id: 'c1',
  type: 'concept',
  label: 'Concept One',
  content: 'A concept',
  score: 0.8,
  parent_id: 'root',
  position: { x: 620, y: 400 },
  userPositioned: false,
}

const EDGE: AnalysisEdge = {
  id: 'edge-root-c1',
  source: 'root',
  target: 'c1',
}

beforeEach(() => {
  graphStore.clearGraph()
})

describe('graphStore — basic mutations', () => {
  it('starts empty', () => {
    const state = get(graphStore)
    expect(state.nodes).toHaveLength(0)
    expect(state.edges).toHaveLength(0)
    expect(state.selectedNodeId).toBeNull()
  })

  it('setGraph replaces nodes and edges', () => {
    graphStore.setGraph({ nodes: [ROOT], edges: [EDGE] })
    const { nodes, edges } = get(graphStore)
    expect(nodes).toHaveLength(1)
    expect(edges).toHaveLength(1)
    expect(nodes[0].id).toBe('root')
  })

  it('addNode appends a node', () => {
    graphStore.addNode(ROOT)
    graphStore.addNode(CONCEPT)
    expect(get(graphStore).nodes).toHaveLength(2)
  })

  it('updateNode patches fields', () => {
    graphStore.addNode(ROOT)
    graphStore.updateNode('root', { label: 'Updated' })
    const node = get(graphStore).nodes.find((n) => n.id === 'root')
    expect(node?.label).toBe('Updated')
    expect(node?.type).toBe('root') // unchanged
  })

  it('updateNode on missing id is a no-op', () => {
    graphStore.addNode(ROOT)
    graphStore.updateNode('nonexistent', { label: 'x' })
    expect(get(graphStore).nodes[0].label).toBe('My Idea')
  })

  it('deleteNode removes node and connected edges', () => {
    graphStore.setGraph({ nodes: [ROOT, CONCEPT], edges: [EDGE] })
    graphStore.deleteNode('c1')
    const { nodes, edges } = get(graphStore)
    expect(nodes).toHaveLength(1)
    expect(edges).toHaveLength(0)
  })

  it('deleteNode clears selectedNodeId if it matches', () => {
    graphStore.addNode(ROOT)
    graphStore.setSelectedNodeId('root')
    graphStore.deleteNode('root')
    expect(get(graphStore).selectedNodeId).toBeNull()
  })

  it('deleteNode preserves selectedNodeId when different node deleted', () => {
    graphStore.setGraph({ nodes: [ROOT, CONCEPT], edges: [] })
    graphStore.setSelectedNodeId('root')
    graphStore.deleteNode('c1')
    expect(get(graphStore).selectedNodeId).toBe('root')
  })

  it('addEdge and deleteEdge', () => {
    graphStore.setGraph({ nodes: [ROOT, CONCEPT], edges: [] })
    graphStore.addEdge(EDGE)
    expect(get(graphStore).edges).toHaveLength(1)
    graphStore.deleteEdge(EDGE.id)
    expect(get(graphStore).edges).toHaveLength(0)
  })

  it('setNodePosition marks userPositioned=true', () => {
    graphStore.addNode(ROOT)
    graphStore.setNodePosition('root', 10, 20)
    const node = get(graphStore).nodes[0]
    expect(node.position).toEqual({ x: 10, y: 20 })
    expect(node.userPositioned).toBe(true)
  })

  it('getSnapshot returns current state', () => {
    graphStore.addNode(ROOT)
    const snap = graphStore.getSnapshot()
    expect(snap.nodes).toHaveLength(1)
  })
})

describe('graphStore — applyGraphActions', () => {
  beforeEach(() => {
    graphStore.addNode(ROOT)
  })

  it('add action creates a node near parent', () => {
    graphStore.applyGraphActions([
      { action: 'add', payload: { id: 'c1', type: 'concept', label: 'L', content: 'C', score: null, parent_id: 'root' } },
    ])
    const { nodes } = get(graphStore)
    const node = nodes.find((n) => n.id === 'c1')
    expect(node).toBeDefined()
    expect(node?.type).toBe('concept')
    // Position should be offset from root
    expect(node?.position.x).toBeGreaterThan(ROOT.position.x)
  })

  it('add action with no parent uses random position', () => {
    graphStore.applyGraphActions([
      { action: 'add', payload: { id: 'orphan', type: 'gap', label: 'G', content: 'C', score: null, parent_id: null } },
    ])
    const node = get(graphStore).nodes.find((n) => n.id === 'orphan')
    expect(node).toBeDefined()
    expect(node?.position.x).toBeGreaterThan(0)
  })

  it('add action skips duplicate IDs', () => {
    graphStore.applyGraphActions([
      { action: 'add', payload: { id: 'root', type: 'concept', label: 'Dupe', content: 'C', score: null, parent_id: null } },
    ])
    expect(get(graphStore).nodes).toHaveLength(1)
    expect(get(graphStore).nodes[0].label).toBe('My Idea') // unchanged
  })

  it('update action patches label and content', () => {
    graphStore.applyGraphActions([
      { action: 'update', payload: { id: 'root', label: 'New Label', content: 'New Content' } },
    ])
    const node = get(graphStore).nodes.find((n) => n.id === 'root')
    expect(node?.label).toBe('New Label')
    expect(node?.content).toBe('New Content')
  })

  it('update action with partial fields only changes provided keys', () => {
    graphStore.applyGraphActions([
      { action: 'update', payload: { id: 'root', label: 'Only Label' } },
    ])
    const node = get(graphStore).nodes.find((n) => n.id === 'root')
    expect(node?.label).toBe('Only Label')
    expect(node?.content).toBe('Root content') // unchanged
  })

  it('delete action removes non-root node', () => {
    graphStore.addNode(CONCEPT)
    graphStore.applyGraphActions([{ action: 'delete', payload: { id: 'c1' } }])
    expect(get(graphStore).nodes.find((n) => n.id === 'c1')).toBeUndefined()
  })

  it('delete action refuses to remove root', () => {
    graphStore.applyGraphActions([{ action: 'delete', payload: { id: 'root' } }])
    expect(get(graphStore).nodes.find((n) => n.id === 'root')).toBeDefined()
  })

  it('connect action adds an edge', () => {
    graphStore.addNode(CONCEPT)
    graphStore.applyGraphActions([
      { action: 'connect', payload: { source: 'root', target: 'c1' } },
    ])
    const { edges } = get(graphStore)
    expect(edges).toHaveLength(1)
    expect(edges[0].source).toBe('root')
    expect(edges[0].target).toBe('c1')
  })

  it('connect action skips duplicate edges', () => {
    graphStore.addNode(CONCEPT)
    graphStore.applyGraphActions([
      { action: 'connect', payload: { source: 'root', target: 'c1' } },
      { action: 'connect', payload: { source: 'root', target: 'c1' } },
    ])
    expect(get(graphStore).edges).toHaveLength(1)
  })

  it('connect action stores optional label and type', () => {
    graphStore.addNode(CONCEPT)
    graphStore.applyGraphActions([
      { action: 'connect', payload: { source: 'root', target: 'c1', label: 'causes', type: 'causal' } },
    ])
    const edge = get(graphStore).edges[0]
    expect(edge.label).toBe('causes')
    expect(edge.type).toBe('causal')
  })

  it('silently drops invalid actions that fail Zod validation', () => {
    graphStore.applyGraphActions([
      { action: 'unknown', payload: {} },         // unknown action type
      'not-an-object',                             // wrong type entirely
      { action: 'add' },                           // missing payload
      null,
    ])
    // Root node is still the only node
    expect(get(graphStore).nodes).toHaveLength(1)
    expect(get(graphStore).edges).toHaveLength(0)
  })
})
