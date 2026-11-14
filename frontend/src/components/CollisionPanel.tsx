import type { Analysis } from '../lib/api'
import { heat } from '../lib/heat'
import { PERSONAS } from '../lib/personas'

const color = (key: string) => PERSONAS.find((p) => p.key === key)?.color ?? '#8d8a82'

function Pill({ score }: { score: number }) {
  return <span className="rounded-sm px-1.5 py-0.5 font-mono text-xs font-medium text-ink-950" style={{ background: heat(score) }}>{score}/10</span>
}

/** Audience Collision: where the panel disagrees, and why both sides can be right. */
export default function CollisionPanel({ analysis, onJump }: { analysis: Analysis; onJump: (segId: number) => void }) {
  const { collisions, agreements, drop_offs } = analysis
  return (
    <div className="space-y-8">
      <div>
        <p className="eyebrow">Audience collisions</p>
        <p className="mt-1 max-w-2xl text-sm text-bone-500">
          Segments where readers reacted very differently. A split audience is not automatically a problem: some work is meant to divide people.
        </p>
        {collisions.length === 0 ? (
          <p className="mt-4 rounded-sm border border-dashed border-ink-500 p-4 text-sm text-bone-500">
            No strong disagreements. The panel reacted similarly throughout, which can mean consistency or that nothing here is divisive.
          </p>
        ) : (
          <ul className="mt-4 space-y-3">
            {collisions.map((c) => (
              <li key={`${c.segment_id}`} className="rounded-sm border border-ink-600 bg-ink-900 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <button className="font-display text-lg hover:text-lab" onClick={() => onJump(c.segment_id)}>{c.label}</button>
                  <span className="font-mono text-[11px] uppercase tracking-wider text-bone-500">
                    {c.spread}-point gap{c.kind === 'continue_split' ? ' · some would stop, some would not' : ''}
                  </span>
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {[c.high, c.low].map((x) => (
                    <div key={x.persona} className="border-l-2 pl-3" style={{ borderColor: color(x.persona) }}>
                      <p className="flex items-center gap-2 text-sm"><span className="font-display">{x.persona_name}</span><Pill score={x.score} /></p>
                      <p className="mt-1 text-sm text-bone-300">{x.reason}</p>
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-sm text-bone-500">{c.explanation}</p>
                {c.others.length > 0 && (
                  <p className="mt-2 font-mono text-[11px] uppercase tracking-wider text-bone-700">
                    In between: {c.others.map((o) => `${o.persona_name.replace('The ', '')} ${o.score}`).join(' · ')}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="grid gap-8 md:grid-cols-2">
        <div>
          <p className="eyebrow">Where readers would stop</p>
          {drop_offs.length === 0 ? <p className="mt-3 text-sm text-bone-500">Nobody wanted to stop reading.</p> : (
            <ul className="mt-3 space-y-2">
              {drop_offs.map((d) => (
                <li key={d.segment_id} className="text-sm">
                  <button className="font-display text-bone-100 hover:text-lab" onClick={() => onJump(d.segment_id)}>{d.label}</button>
                  <span className="text-bone-500"> · {d.persona_names.map((n) => n.replace('The ', '')).join(', ')}{d.consensus ? ' (shared drop-off)' : ''}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-xs text-bone-700">Each reader's first stop only; later stops by the same reader are not repeated.</p>
        </div>
        <div>
          <p className="eyebrow">Where they agree</p>
          {agreements.length === 0 ? <p className="mt-3 text-sm text-bone-500">No segments where the whole panel clearly agreed.</p> : (
            <ul className="mt-3 space-y-2">
              {agreements.map((a) => (
                <li key={a.segment_id} className="text-sm">
                  <button className="font-display text-bone-100 hover:text-lab" onClick={() => onJump(a.segment_id)}>{a.label}</button>
                  <span className="text-bone-500"> · {a.kind === 'shared_high' ? 'everyone engaged' : 'everyone disengaged'} (avg {a.mean.toFixed(1)})</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
