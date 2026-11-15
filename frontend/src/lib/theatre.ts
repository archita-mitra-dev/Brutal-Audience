import type { Reaction } from './api'
import { PERSONAS } from './personas'

const order = (key: string) => PERSONAS.findIndex((p) => p.key === key)

/** Reactions in the order they were stored. Older runs without `seq` fall back to reading order. */
export function arrivalOrder(reactions: Reaction[]): Reaction[] {
  return [...reactions].sort(
    (a, b) =>
      (a.seq ?? Number.MAX_SAFE_INTEGER) - (b.seq ?? Number.MAX_SAFE_INTEGER) ||
      a.segment_id - b.segment_id ||
      order(a.persona) - order(b.persona),
  )
}

export type FlagKind = 'stop' | 'drop' | 'hooked' | 'failed'
export interface Flag { kind: FlagKind; text: string }

export const DROP_POINTS = 3   // a fall of this many points from the persona's previous segment is flagged
export const HOOKED_SCORE = 8

/**
 * Flags are plain rules over the recorded numbers, never model output, so the theatre can
 * only say things the reaction data actually supports.
 */
export function flagsFor(r: Reaction, previous: Reaction | undefined): Flag[] {
  if (r.status === 'failed') return [{ kind: 'failed', text: 'No reaction recorded' }]
  const out: Flag[] = []
  if (r.would_continue === false) out.push({ kind: 'stop', text: 'Would stop reading here' })
  const prev = previous?.status === 'ok' ? previous.engagement_score : null
  if (prev != null && r.engagement_score != null && prev - r.engagement_score >= DROP_POINTS) {
    out.push({ kind: 'drop', text: `Fell ${prev - r.engagement_score} points (${prev} → ${r.engagement_score})` })
  }
  if ((r.engagement_score ?? 0) >= HOOKED_SCORE) out.push({ kind: 'hooked', text: 'Hooked' })
  return out
}

/** The reaction this persona had to the segment just before `r`, if there is one. */
export function previousFor(r: Reaction, all: Reaction[]): Reaction | undefined {
  return all.find((x) => x.persona === r.persona && x.segment_id === r.segment_id - 1)
}
