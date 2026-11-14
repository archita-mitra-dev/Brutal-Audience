import type { Reaction, Segment } from '../lib/api'
import { heat } from '../lib/heat'
import { PERSONAS } from '../lib/personas'

/** Every persona's reaction to one segment, side by side, next to the passage itself. */
export default function SegmentCompare({
  segment, reactions, focus,
}: { segment: Segment | null; reactions: Reaction[]; focus: string | null }) {
  if (!segment) return <p className="text-sm text-bone-500">Select a segment in the heatmap to compare reactions.</p>
  const mine = new Map(reactions.filter((r) => r.segment_id === segment.id).map((r) => [r.persona, r]))
  const evidence = [...mine.values()].filter((r) => r.evidence).map((r) => r.evidence as string)

  // Highlight every verbatim quote the personas pointed at (only where it genuinely occurs).
  const ranges = evidence
    .map((e) => { const i = segment.text.toLowerCase().indexOf(e.toLowerCase()); return i < 0 ? null : [i, i + e.length] as const })
    .filter((x): x is readonly [number, number] => x !== null)
    .sort((a, b) => a[0] - b[0])
  const parts: React.ReactNode[] = []
  let at = 0
  ranges.forEach(([a, b], i) => {
    if (a < at) return // overlapping quote: skip
    parts.push(segment.text.slice(at, a))
    parts.push(<mark key={i} className="rounded-[2px] bg-lab/25 px-0.5 text-bone-100">{segment.text.slice(a, b)}</mark>)
    at = b
  })
  parts.push(segment.text.slice(at))

  return (
    <div>
      <p className="eyebrow">{segment.label} · the passage</p>
      <p className="mt-1.5 max-h-52 overflow-y-auto whitespace-pre-wrap rounded-sm bg-ink-950 p-3 font-mono text-[12.5px] leading-relaxed text-bone-300">{parts}</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {PERSONAS.map((p) => {
          const r = mine.get(p.key)
          return (
            <article key={p.key} className={`rounded-sm border bg-ink-900 p-3 ${focus === p.key ? 'border-bone-500' : 'border-ink-600'}`} style={{ borderTopColor: p.color, borderTopWidth: 2 }}>
              <header className="flex items-center justify-between gap-2">
                <span className="font-display"><span style={{ color: p.color }} aria-hidden>{p.glyph} </span>{p.name.replace('The ', '')}</span>
                {r?.status === 'ok' && (
                  <span className="rounded-sm px-1.5 py-0.5 font-mono text-xs font-medium text-ink-950" style={{ background: heat(r.engagement_score ?? 0) }}>{r.engagement_score}/10</span>
                )}
              </header>
              {!r ? <p className="mt-2 text-xs text-bone-500">Not read yet.</p>
                : r.status === 'failed' ? <p role="alert" className="mt-2 text-xs text-persona-doom">No reaction recorded: {r.error}</p>
                : (
                  <>
                    <p className="mt-2 font-display italic leading-snug text-bone-100">“{r.inner_thought}”</p>
                    <p className="mt-1.5 text-sm text-bone-300">{r.reason}</p>
                    <p className="mt-2 font-mono text-[10px] uppercase tracking-wider text-bone-500">
                      {r.emotion} · {r.would_continue ? 'would keep reading' : <span className="text-persona-doom">would stop here</span>}
                    </p>
                    {r.evidence && <p className="mt-2 border-l-2 border-lab pl-2 text-xs text-bone-500">“{r.evidence}”</p>}
                  </>
                )}
            </article>
          )
        })}
      </div>
    </div>
  )
}
