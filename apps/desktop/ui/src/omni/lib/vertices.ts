import type { VertexDef } from './types';

// ----------------------------------------------------------------------------
// VERTEX_PRESETS — swappable 8-slot vertex sets for the octagon.
// Swap synthesis/logic for safety/speed without touching component code by
// selecting OPS_PRESET. Order is clockwise from the top vertex.
// ----------------------------------------------------------------------------

export const DEFAULT_PRESET: VertexDef[] = [
  {
    key: 'reasoning',
    label: 'Reasoning',
    description: 'Higher token spend for chain-of-thought + math accuracy.',
    accent: '#FFB020',
  },
  {
    key: 'creativity',
    label: 'Creativity',
    description: 'Raises temperature + top-p for storytelling and human-like prose.',
    accent: '#C264FE',
  },
  {
    key: 'logic',
    label: 'Logic',
    description: 'Strict deductive structure, formal consistency.',
    accent: '#4FC3F7',
  },
  {
    key: 'contemplation',
    label: 'Contemplation',
    description: 'More internal deep-thinking tokens before final output.',
    accent: '#7C9EFF',
  },
  {
    key: 'coding',
    label: 'Coding',
    description: 'Maximizes syntax precision, logic formatting, language adherence.',
    accent: '#34E5C8',
  },
  {
    key: 'synthesis',
    label: 'Synthesis',
    description: 'Combines/condenses across sources into coherent output.',
    accent: '#3DD68C',
  },
  {
    key: 'empathy',
    label: 'Empathy',
    description: 'Persona shift from cold technical to empathetic conversational.',
    accent: '#FF6B8A',
  },
  {
    key: 'factuality',
    label: 'Factuality',
    description: 'Strict grounding, retrieval reliance, minimized hallucination.',
    accent: '#5EE6EB',
  },
];

export const OPS_PRESET: VertexDef[] = [
  { key: 'coding', label: 'Coding', description: 'Syntax precision and language adherence.', accent: '#34E5C8' },
  { key: 'reasoning', label: 'Reasoning', description: 'Chain-of-thought depth.', accent: '#FFB020' },
  { key: 'factuality', label: 'Factuality', description: 'Grounding and retrieval reliance.', accent: '#5EE6EB' },
  { key: 'safety', label: 'Safety', description: 'Guardrails and refusal calibration.', accent: '#FF5470' },
  { key: 'speed', label: 'Speed', description: 'Lower latency, fewer thinking tokens.', accent: '#9CFF57' },
  { key: 'tone', label: 'Tone', description: 'Persona warmth and conversational register.', accent: '#FF6B8A' },
  { key: 'contemplation', label: 'Contemplation', description: 'Internal deep-thinking budget.', accent: '#7C9EFF' },
  { key: 'creativity', label: 'Creativity', description: 'Temperature and top-p for novelty.', accent: '#C264FE' },
];

export const VERTEX_PRESETS: Record<string, VertexDef[]> = {
  default: DEFAULT_PRESET,
  ops: OPS_PRESET,
};
