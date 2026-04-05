import type { DimensionType } from '$lib/schemas/graph'

export interface NodeStyle {
  bg: string
  border: string
  text: string
  label: string
}

export const NODE_STYLES: Record<DimensionType, NodeStyle> = {
  root: {
    bg: 'bg-indigo-900',
    border: 'border-indigo-400',
    text: 'text-indigo-100',
    label: 'Idea',
  },
  concept: {
    bg: 'bg-blue-900',
    border: 'border-blue-400',
    text: 'text-blue-100',
    label: 'Core Concept',
  },
  requirement: {
    bg: 'bg-purple-900',
    border: 'border-purple-400',
    text: 'text-purple-100',
    label: 'Requirement',
  },
  gap: {
    bg: 'bg-yellow-900',
    border: 'border-yellow-400',
    text: 'text-yellow-100',
    label: 'Gap',
  },
  benefit: {
    bg: 'bg-green-900',
    border: 'border-green-400',
    text: 'text-green-100',
    label: 'Benefit',
  },
  drawback: {
    bg: 'bg-red-900',
    border: 'border-red-400',
    text: 'text-red-100',
    label: 'Drawback',
  },
  feasibility: {
    bg: 'bg-cyan-900',
    border: 'border-cyan-400',
    text: 'text-cyan-100',
    label: 'Feasibility',
  },
  flaw: {
    bg: 'bg-orange-900',
    border: 'border-orange-400',
    text: 'text-orange-100',
    label: 'Flaw',
  },
  alternative: {
    bg: 'bg-teal-900',
    border: 'border-teal-400',
    text: 'text-teal-100',
    label: 'Alternative',
  },
  question: {
    bg: 'bg-pink-900',
    border: 'border-pink-400',
    text: 'text-pink-100',
    label: 'Open Question',
  },
}

export function getNodeStyle(type: DimensionType): NodeStyle {
  return NODE_STYLES[type] ?? NODE_STYLES.concept
}
