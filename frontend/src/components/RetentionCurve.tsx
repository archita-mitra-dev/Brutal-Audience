import type { DropoffPrediction, DropState } from '../lib/api'
import { PERSONAS } from '../lib/personas'

const W = 640, H = 220, PAD = { l: 40, r: 16, t: 14, b: 30 }

const CELL: Record<DropState, { text: string; cls: string }> = {
  continue: { text: 'Continues', cls: 'text-persona-fan' },
  drop_off: { text: 'Drops off', cls: 'font-medium text-persona-doom' },
  already_left: { text: 'Already left', cls: 'text-bone-700' },
  unread: { text: 'No reaction', cls: 'text-bone-700' },
}

interface Props { data: DropoffPrediction; onJump: (segmentId: number) => void }

/** Share of simulated readers still reading after each segment, the table behind it, and the exit triggers. */
export default function RetentionCurve({ data, onJump }: Props) {
  if (!data.reader_count) return <p className="text-sm text-bone-500">No reactions to predict drop-off from yet.</p>
  const pts = data.curve
  const x = (i: number) => PAD.l + (pts.length < 2 ? 0 : (i / (pts.length - 1)) * (W - PAD.l - PAD.r))
  const y = (pct: number) => PAD.t + (1 - pct / 100) * (H - PAD.t - PAD.b)
  // step line: retention only changes when a reader leaves
  const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i)},${y(pts[Math.max(i - 1, 0)].pct)} L${x(i)},${y(p.pct)}`).join(' ')
  const area = `${path} L${x(pts.length - 1)},${y(0)} L${x(0)},${y(0)} Z`
  const last = pts[pts.length - 1]
  const shownTicks = pts.length > 14 ? pts.filter((_, i) => i % Math.ceil(pts.length / 12) === 0) : pts

  return (
    <div className="space-y-8">
      <figure>
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
          aria-label={`Retention curve: ${last.still_reading} of ${data.reader_count} simulated readers are still reading at the end`}>
          {[0, 25, 50, 75, 100].map((g) => (
            <g key={g}>
              <line x1={PAD.l} x2={W - PAD.r} y1={y(g)} y2={y(g)} stroke="#262b34" strokeWidth={1} />
              <text x={PAD.l - 6} y={y(g) + 3} textAnchor="end" fontSize={10} fill="#8d8a82" fontFamily="IBM Plex Mono, monospace">{g}%</text>
            </g>
          ))}
          <path d={area} fill="#f5b84a" opacity={0.12} />
          <path d={path} fill="none" stroke="#f5b84a" strokeWidth={2} />
          {pts.map((p, i) => (
            <g key={p.segment_id} onClick={() => p.segment_id > 0 && onJump(p.segment_id)} style={{ cursor: p.segment_id > 0 ? 'pointer' : 'default' }}>
              <circle cx={x(i)} cy={y(p.pct)} r={p.segment_id === data.steepest_segment_id ? 6 : 3.5}
                fill={p.segment_id === data.steepest_segment_id ? '#ff6b57' : '#f5b84a'} stroke="#08090b" strokeWidth={1.5}>
                <title>{`${p.label}: ${p.still_reading} of ${data.reader_count} readers still going (${p.pct}%)`}</title>
              </circle>
            </g>
          ))}
          {shownTicks.map((p) => (
            <text key={p.segment_id} x={x(pts.indexOf(p))} y={H - 10} textAnchor="middle" fontSize={10} fill="#8d8a82" fontFamily="IBM Plex Mono, monospace">
              {p.segment_id === 0 ? 'start' : p.segment_id}
            </text>
          ))}
        </svg>
        <figcaption className="mt-1 font-mono text-[11px] text-bone-500">
          {data.steepest_segment_id
            ? `Steepest fall: segment ${data.steepest_segment_id} (red dot). `
            : 'Nobody dropped off. '}
          {data.reached_end.length > 0 && `Reached the end: ${data.reached_end.map((n) => n.replace('The ', '')).join(', ')}. `}
          Predicted from simulated reactions, not measured retention.
        </figcaption>
      </figure>

      <div className="overflow-x-auto rounded-sm border border-ink-600">
        <table className="w-full min-w-[32rem] text-left text-sm">
          <caption className="sr-only">Where each simulated reader continues, drops off, or has already left</caption>
          <thead>
            <tr className="border-b border-ink-600 bg-ink-900 font-mono text-[11px] uppercase tracking-wider text-bone-500">
              <th scope="col" className="px-3 py-2">Segment</th>
              {PERSONAS.map((p) => <th key={p.key} scope="col" className="px-3 py-2" style={{ color: p.color }}>{p.name.replace('The ', '')}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.segment_id} className="border-b border-ink-700 last:border-0">
                <th scope="row" className="px-3 py-1.5 font-normal">
                  <button type="button" className="text-bone-300 underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-lab" onClick={() => onJump(row.segment_id)}>{row.label}</button>
                </th>
                {PERSONAS.map((p) => {
                  const st = row.states[p.key]
                  return <td key={p.key} className={`px-3 py-1.5 font-mono text-xs ${st ? CELL[st].cls : 'text-bone-700'}`}>{st ? CELL[st].text : '–'}</td>
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.triggers.length > 0 && (
        <div>
          <p className="eyebrow mb-3">What likely triggered each exit</p>
          <ul className="space-y-3">
            {data.triggers.map((t) => {
              const p = PERSONAS.find((x) => x.key === t.persona)!
              return (
                <li key={t.persona} className="rounded-sm border border-ink-600 bg-ink-900 p-4" style={{ borderLeftColor: p.color, borderLeftWidth: 2 }}>
                  <p className="font-display">
                    {t.persona_name} <span className="font-mono text-xs text-bone-500">· first wanted to stop at</span>{' '}
                    <button type="button" className="underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-lab" onClick={() => onJump(t.segment_id)}>{t.label}</button>
                    <span className="font-mono text-xs text-bone-500"> · {t.score}/10</span>
                  </p>
                  {t.sentence
                    ? <blockquote className="mt-2 border-l-2 border-lab pl-3 text-sm text-bone-100">{t.sentence}</blockquote>
                    : <p className="mt-2 text-xs text-bone-500">No verifiable quote came with this reaction, so no trigger sentence is shown.</p>}
                  {t.reason && <p className="mt-2 text-sm text-bone-300">{t.reason}</p>}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
