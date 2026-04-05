import { z } from 'zod'

export const dimensionTypeSchema = z.enum([
  'root',
  'concept',
  'requirement',
  'gap',
  'benefit',
  'drawback',
  'feasibility',
  'flaw',
  'alternative',
  'question',
])
export type DimensionType = z.infer<typeof dimensionTypeSchema>

export const nodePositionSchema = z.object({
  x: z.number(),
  y: z.number(),
})

export const analysisNodeSchema = z.object({
  id: z.string(),
  type: dimensionTypeSchema,
  label: z.string(),
  content: z.string(),
  score: z.number().nullable().optional(),
  parent_id: z.string().nullable().optional(),
  position: nodePositionSchema,
  userPositioned: z.boolean().default(false),
})
export type AnalysisNode = z.infer<typeof analysisNodeSchema>

export const analysisEdgeSchema = z.object({
  id: z.string(),
  source: z.string(),
  target: z.string(),
  label: z.string().optional(),
  type: z.string().optional(),
})
export type AnalysisEdge = z.infer<typeof analysisEdgeSchema>

export const analysisGraphSchema = z.object({
  nodes: z.array(analysisNodeSchema),
  edges: z.array(analysisEdgeSchema),
})
export type AnalysisGraph = z.infer<typeof analysisGraphSchema>

// LLM graph actions
export const nodePayloadSchema = z.object({
  id: z.string(),
  type: dimensionTypeSchema,
  label: z.string(),
  content: z.string(),
  score: z.number().nullable().optional(),
  parent_id: z.string().nullable().optional(),
})

export const addNodeActionSchema = z.object({
  action: z.literal('add'),
  payload: nodePayloadSchema,
})

export const updateNodeActionSchema = z.object({
  action: z.literal('update'),
  payload: z.object({
    id: z.string(),
    label: z.string().optional(),
    content: z.string().optional(),
  }),
})

export const deleteNodeActionSchema = z.object({
  action: z.literal('delete'),
  payload: z.object({ id: z.string() }),
})

export const connectActionSchema = z.object({
  action: z.literal('connect'),
  payload: z.object({
    source: z.string(),
    target: z.string(),
    label: z.string().optional(),
    type: z.string().optional(),
  }),
})

export const llmGraphActionSchema = z.discriminatedUnion('action', [
  addNodeActionSchema,
  updateNodeActionSchema,
  deleteNodeActionSchema,
  connectActionSchema,
])
export type LLMGraphAction = z.infer<typeof llmGraphActionSchema>
