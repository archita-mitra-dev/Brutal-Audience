import type { Analysis, Reaction, Segment } from '../lib/api'
import { heat } from '../lib/heat'
import { PERSONAS } from '../lib/personas'

interface Props {
  segments: Segment[]
  reactions: Reaction[]
  analysis: Analysis
  selectedSegment: number | null
  selectedPersona: string | null
  onSelect: (segmentId: number, persona: string | null) => void
}

const CELL = 26 // px; long works scroll sideways

/**
 * Rows = personas, columns = segments, colour = engagement.
 * Column headers carry the markers: ◆ audience collision, ▾ somebody stops here.
 */
export default function Heatmap({ segments, reactions, analysis, selectedSegment, selectedPersona, onSelect }: Props) {
  const byKey = new Map(reactions.map((r) => [`${r.persona}:${r.segment_id}`, r]))
  const stat = new Map(analysis.segments.map((s) => [s.segment_id, s]))
  const collisions = new Set(analysis.collisions.map((c) => c.segment_id))
  const dropOffs = new Set(analysis.drop_offs.map((d) => d.segment_id))
  const lost = new Set(analysis.lost_attention)
  const cols = { gridTemplateColumns: `repeat(${segments.length}, minmax(${CELL}px, 1fr))` }

  return (
    <div className="overflow-x-auto rounded-sm border border-ink-600 bg-ink-900/70 p-4">
      <div style={{ minWidth: `calc(9.5rem + ${segments.length * (CELL + 4)}px)` }}>
        {/* header: segment numbers + markers */}
        <div className="flex items-end gap-3">
          <div className="w-36 shrink-0" />
          <div className="grid flex-1 gap-1" style={cols} role="row">
            {segments.map((s) => {
              const sel = selectedSegment === s.id
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => onSelect(s.id, null)}
                  aria-label={`${s.label}${collisions.has(s.id) ? ', audience collision' : ''}${dropOffs.has(s.id) ? ', a reader would stop here' : ''}`}
                  aria-pressed={sel}
                  className={`flex flex-col items-center gap-0.5 rounded-[2px] pb-1 font-mono text-[9px] leading-none focus:outline-none focus-visible:ring-2 focus-visible:ring-lab ${sel ? 'bg-ink-600 text-bone-100' : 'text-bone-500 hover:text-bone-100'}`}
                >
                  <span className="h-2.5 text-[9px] text-lab">{collisions.has(s.id) ? '◆' : ''}</span>
                  <span className="h-2.5 text-[9px] text-persona-doom">{dropOffs.has(s.id) ? '▾' : ''}</span>
                  <span>{s.id}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* persona rows */}
        <div className="mt-1 space-y-1">
          {PERSONAS.map((p) => (
            <div key={p.key} className="flex items-center gap-3">
              <div className="sticky left-0 z-10 flex w-36 shrink-0 items-center gap-2 bg-ink-900 py-0.5 pr-2">
                <span style={{ color: p.color }} aria-hidden>{p.glyph}</span>
                <span className="truncate font-mono text-[11px] uppercase tracking-wider text-bone-300">{p.name.replace('The ', '')}</span>
              </div>
              <div className="grid flex-1 gap-1" style={cols}>
                {segments.map((s) => {
                  const r = byKey.get(`${p.key}:${s.id}`)
                  const isSel = selectedSegment === s.id && selectedPersona === p.key
                  const label = !r ? `${p.name}, segment ${s.id}: not read` : r.status === 'failed'
                    ? `${p.name}, segment ${s.id}: no reaction`
                    : `${p.name}, segment ${s.id}: ${r.engagement_score} of 10, ${r.emotion}`
                  return (
                    <button
                      key={s.id}
                      type="button"
                      disabled={!r}
                      title={label}
                      aria-label={label}
                      aria-pressed={isSel}
                      onClick={() => onSelect(s.id, p.key)}
                      className="flex items-center justify-center rounded-[2px] text-[9px] font-medium leading-none focus:outline-none focus-visible:ring-2 focus-visible:ring-lab disabled:cursor-default"
                      style={{
                        height: CELL,
                        background: !r ? '#171a20' : r.status === 'failed' ? '#2a1f22' : heat(r.engagement_score ?? 0),
                        color: r && r.status === 'ok' && (r.engagement_score ?? 0) > 6 ? '#08090b' : '#c9c5ba',
                        outline: isSel ? `2px solid ${p.color}` : selectedSegment === s.id ? '1px solid #5c5a55' : 'none',
                        outlineOffset: 1,
                      }}
                    >
                      {r?.status === 'failed' ? '!' : r ? r.engagement_score : ''}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}

          {/* panel average */}
          <div className="flex items-center gap-3 border-t border-ink-700 pt-1.5">
            <div className="sticky left-0 z-10 w-36 shrink-0 bg-ink-900 pr-2 font-mono text-[11px] uppercase tracking-wider text-bone-100">Panel avg</div>
            <div className="grid flex-1 gap-1" style={cols}>
              {segments.map((s) => {
                const m = stat.get(s.id)?.mean ?? null
                return (
                  <div
                    key={s.id}
                    title={m === null ? `Segment ${s.id}: no data` : `Segment ${s.id}: panel average ${m.toFixed(1)} of 10${lost.has(s.id) ? ' (several readers lost interest)' : ''}`}
                    className="flex items-center justify-center rounded-[2px] text-[9px] font-medium"
                    style={{
                      height: CELL - 6,
                      background: m === null ? '#171a20' : heat(m),
                      color: m !== null && m > 6 ? '#08090b' : '#c9c5ba',
                      outline: lost.has(s.id) ? '1px dashed #ff6b57' : 'none',
                      outlineOffset: 1,
                    }}
                  >
                    {m === null ? '' : Math.round(m)}
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* legend */}
        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 pl-[9.75rem] font-mono text-[10px] uppercase tracking-widest text-bone-500">
          <span className="flex items-center gap-2">
            0
            <span className="flex h-2 w-24" aria-hidden>
              <i className="flex-1" style={{ background: heat(0) }} />
              <i className="flex-1" style={{ background: heat(5) }} />
              <i className="flex-1" style={{ background: heat(10) }} />
            </span>
            10 engagement
          </span>
          <span><span className="text-lab">◆</span> audience collision</span>
          <span><span className="text-persona-doom">▾</span> a reader would stop</span>
          <span><span className="text-persona-doom">┄</span> several lost interest</span>
        </div>
      </div>
    </div>
  )
}
