import type { Reaction, Segment } from '../lib/api'
import { heat } from '../lib/heat'
import { PERSONAS } from '../lib/personas'

interface Props {
  segments: Segment[]
  reactions: Reaction[]
  selected: { persona: string; segmentId: number } | null
  onSelect: (persona: string, segmentId: number) => void
}

const CELL = 18 // px per segment column; the lanes scroll sideways for long works

/** One lane per persona; one cell per segment, filling in as that persona reads it. */
export default function PersonaLanes({ segments, reactions, selected, onSelect }: Props) {
  const byKey = new Map(reactions.map((r) => [`${r.persona}:${r.segment_id}`, r]))

  return (
    <div className="overflow-x-auto rounded-sm border border-ink-600 bg-ink-900/70 p-4">
      <div style={{ minWidth: `calc(9rem + ${segments.length * CELL}px)` }} className="space-y-3">
        {PERSONAS.map((p) => (
          <div key={p.key} className="flex items-center gap-3">
            <div className="sticky left-0 z-10 flex w-36 shrink-0 items-center gap-2 bg-ink-900 py-1 pr-2">
              <span style={{ color: p.color }} aria-hidden>{p.glyph}</span>
              <span className="truncate font-mono text-[11px] uppercase tracking-wider text-bone-300">
                {p.name.replace('The ', '')}
              </span>
            </div>
            <div className="grid flex-1 gap-1" style={{ gridTemplateColumns: `repeat(${segments.length}, minmax(${CELL - 4}px, 1fr))` }}>
              {segments.map((s) => {
                const r = byKey.get(`${p.key}:${s.id}`)
                const isSel = selected?.persona === p.key && selected.segmentId === s.id
                const label = !r
                  ? `${p.name}: segment ${s.id}, not read yet`
                  : r.status === 'failed'
                    ? `${p.name}: segment ${s.id}, no reaction (${r.error})`
                    : `${p.name}: segment ${s.id}, engagement ${r.engagement_score} of 10, ${r.emotion}`
                return (
                  <button
                    key={s.id}
                    type="button"
                    disabled={!r}
                    title={label}
                    aria-label={label}
                    aria-pressed={isSel}
                    onClick={() => onSelect(p.key, s.id)}
                    className="relative aspect-square rounded-[2px] text-[9px] font-medium leading-none transition-all duration-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-lab disabled:cursor-default"
                    style={{
                      background: !r ? '#171a20' : r.status === 'failed' ? '#2a1f22' : heat(r.engagement_score ?? 0),
                      color: r && r.status === 'ok' && (r.engagement_score ?? 0) > 6 ? '#08090b' : '#c9c5ba',
                      outline: isSel ? `2px solid ${p.color}` : 'none',
                      outlineOffset: 1,
                    }}
                  >
                    {r?.status === 'failed' ? '!' : r?.would_continue === false ? '✕' : ''}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
        <p className="pl-[9.75rem] font-mono text-[10px] uppercase tracking-widest text-bone-700">
          Brighter = more engaged · ✕ would stop reading · ! no reaction
        </p>
      </div>
    </div>
  )
}
