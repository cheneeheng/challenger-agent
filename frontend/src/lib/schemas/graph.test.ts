import { describe, it, expect } from 'vitest'
import {
  dimensionTypeSchema,
  analysisNodeSchema,
  analysisEdgeSchema,
  analysisGraphSchema,
  llmGraphActionSchema,
} from './graph'

describe('dimensionTypeSchema', () => {
  it('accepts all valid types', () => {
    const types = ['root', 'concept', 'requirement', 'gap', 'benefit', 'drawback', 'feasibility', 'flaw', 'alternative', 'question']
    for (const t of types) {
      expect(dimensionTypeSchema.safeParse(t).success).toBe(true)
    }
  })

  it('rejects unknown type', () => {
    expect(dimensionTypeSchema.safeParse('unknown').success).toBe(false)
  })
})

describe('analysisNodeSchema', () => {
  const valid = {
    id: 'n1',
    type: 'concept',
    label: 'Label',
    content: 'Content',
    score: null,
    parent_id: null,
    position: { x: 10, y: 20 },
    userPositioned: false,
  }

  it('accepts a valid node', () => {
    expect(analysisNodeSchema.safeParse(valid).success).toBe(true)
  })

  it('userPositioned defaults to false when omitted', () => {
    const { userPositioned: _, ...without } = valid
    const result = analysisNodeSchema.safeParse(without)
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.userPositioned).toBe(false)
  })

  it('rejects missing required fields', () => {
    expect(analysisNodeSchema.safeParse({ id: 'n1' }).success).toBe(false)
  })

  it('rejects invalid type', () => {
    expect(analysisNodeSchema.safeParse({ ...valid, type: 'bad' }).success).toBe(false)
  })

  it('accepts numeric score', () => {
    expect(analysisNodeSchema.safeParse({ ...valid, score: 0.75 }).success).toBe(true)
  })
})

describe('analysisEdgeSchema', () => {
  const valid = { id: 'e1', source: 'a', target: 'b' }

  it('accepts a minimal edge', () => {
    expect(analysisEdgeSchema.safeParse(valid).success).toBe(true)
  })

  it('accepts edge with optional label and type', () => {
    expect(analysisEdgeSchema.safeParse({ ...valid, label: 'causes', type: 'causal' }).success).toBe(true)
  })

  it('rejects missing source or target', () => {
    expect(analysisEdgeSchema.safeParse({ id: 'e1', source: 'a' }).success).toBe(false)
    expect(analysisEdgeSchema.safeParse({ id: 'e1', target: 'b' }).success).toBe(false)
  })
})

describe('analysisGraphSchema', () => {
  it('accepts empty graph', () => {
    expect(analysisGraphSchema.safeParse({ nodes: [], edges: [] }).success).toBe(true)
  })

  it('rejects missing edges array', () => {
    expect(analysisGraphSchema.safeParse({ nodes: [] }).success).toBe(false)
  })
})

describe('llmGraphActionSchema', () => {
  it('accepts add action', () => {
    const action = {
      action: 'add',
      payload: { id: 'c1', type: 'concept', label: 'L', content: 'C', score: null, parent_id: null },
    }
    expect(llmGraphActionSchema.safeParse(action).success).toBe(true)
  })

  it('accepts update action', () => {
    expect(llmGraphActionSchema.safeParse({ action: 'update', payload: { id: 'c1', label: 'New' } }).success).toBe(true)
  })

  it('accepts delete action', () => {
    expect(llmGraphActionSchema.safeParse({ action: 'delete', payload: { id: 'c1' } }).success).toBe(true)
  })

  it('accepts connect action', () => {
    expect(llmGraphActionSchema.safeParse({ action: 'connect', payload: { source: 'a', target: 'b' } }).success).toBe(true)
  })

  it('accepts connect action with optional label and type', () => {
    expect(
      llmGraphActionSchema.safeParse({ action: 'connect', payload: { source: 'a', target: 'b', label: 'l', type: 't' } }).success
    ).toBe(true)
  })

  it('rejects unknown action type', () => {
    expect(llmGraphActionSchema.safeParse({ action: 'unknown', payload: {} }).success).toBe(false)
  })

  it('rejects add action with invalid node type', () => {
    const action = {
      action: 'add',
      payload: { id: 'c1', type: 'invalid', label: 'L', content: 'C', score: null, parent_id: null },
    }
    expect(llmGraphActionSchema.safeParse(action).success).toBe(false)
  })
})
