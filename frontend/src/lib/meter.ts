import type { DocumentLevel, SegmentLevel } from './api'

export const SEGMENT_STYLE: Record<SegmentLevel, { color: string; glyph: string; short: string }> = {
  strong:     { color: '#4ade80', glyph: '●', short: 'Strong' },
  curious:    { color: '#5eb8ff', glyph: '◐', short: 'Wants more' },
  declining:  { color: '#f5b84a', glyph: '▼', short: 'Declining' },
  multi_stop: { color: '#ff6b57', glyph: '✕', short: 'Would stop' },
}

export const SEGMENT_ORDER: SegmentLevel[] = ['strong', 'curious', 'declining', 'multi_stop']

export const DOCUMENT_STYLE: Record<DocumentLevel, { color: string; glyph: string }> = {
  holds:  { color: '#4ade80', glyph: '●' },
  mixed:  { color: '#5eb8ff', glyph: '◐' },
  shaky:  { color: '#f5b84a', glyph: '▼' },
  brutal: { color: '#ff6b57', glyph: '✕' },
}
