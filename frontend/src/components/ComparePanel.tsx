import { useEffect, useState } from 'react'
import { api, ApiError, type Comparison, type SegmentDelta } from '../lib/api'
import { PERSONAS } from '../lib/personas'

const VERDICT: Record<Comparison['verdict'], { text: string; color: string }> = {
  better: { text: 'Simulated readers responded better', color: '#4ade80' },
  worse: { text: 'Simulated readers responded worse', color: '#ff6b57' },
  mixed: { text: 'Mixed: some parts improved, some weakened', color: '#fbbf24' },
  about_the_same: { text: 'About the same', color: '#a3a3a3' },
  unrated: { text: 'Not enough rated reactions to compare', color: '#a3a3a3' },
}
const STATUS: Record<SegmentDelta['status'], { glyph: string; color: string; word: string }> = {
  improved: { glyph: '▲', color: '#4ade80', word: 'Improved' },
  weakened: { glyph: '▼', color: '#ff6b57', word: 'Weakened' },
  unchanged: { glyph: '＝', color: '#a3a3a3', word: 'About the same' },
  new: { glyph: '＋', color: '#5eb8ff', word: 'New' },
  removed: { glyph: '－', color: '#a3a3a3', word: 'Removed' },
  unrated: { glyph: '?', color: '#a3a3a3', word: 'Not rated' },
}
const sign = (n: number | null, d = 1) => (n === null ? '–' : `${n > 0 ? '+' : ''}${n.toFixed(d)}`)
const num = (n: number | null) => (n === null ? '–' : n.toFixed(1))

/** Before / after for a revision or what-if: segments, readers, earlier drop-offs and side effects. */
export default function ComparePanel({ runId }: { runId: string }) {
  const [c, setC] = useState<Comparison | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    api.getComparison(runId)
      .then((x) => alive && setC(x))
      .catch((e) => alive && setError(e instanceof ApiError ? e.message : 'Could not load the comparison.'))
    return () => { alive = false }
  }, [runId])

  if (error) return <p role="alert" className="text-persona-doom">{error}</p>
  if (!c) return <p className="eyebrow animate-blink">Comparing the two readings…</p>
  const v = VERDICT[c.verdict]
  const whatIf = c.kind === 'whatif'

  return (
    <div className="space-y-6">
      <div className="rounded-sm border bg-ink-900 p-5" style={{ borderColor: v.color + '99', borderLeftWidth: 4 }}>
        <p className="eyebrow">{whatIf ? 'Hypothetical simulation' : 'Revision impact'}{c.label ? ` · ${c.label}` : ''}</p>
        <p className="mt-2 font-display text-3xl" style={{ color: v.color }}>{v.text}</p>
        <p className="mt-2 font-mono text-sm text-bone-300">
          Panel average {num(c.overall_before)} → {num(c.overall_after)} ({sign(c.overall_delta)})
          {c.retention_before !== null && c.retention_after !== null && <> · still reading at the end {Math.round(c.retention_before)}% → {Math.round(c.retention_after)}%</>}
          {c.meter_before && c.meter_after && <> · meter {c.meter_before} → {c.meter_after}</>}
        </p>
        <p className="mt-1 font-mono text-[11px] uppercase tracking-wider text-bone-500">
          {c.improved} improved · {c.weakened} weakened{c.collateral > 0 ? ` · ${c.collateral} untouched segment${c.collateral === 1 ? '' : 's'} got worse` : ''}
        </p>
        <p role="note" className="mt-3 max-w-2xl text-xs text-bone-500">
          {whatIf ? 'This is a hypothetical simulation, not a guaranteed improvement. ' : ''}{c.noise_note}
        </p>
      </div>

      {c.highlights.length > 0 && (
        <ul className="space-y-2 text-sm text-bone-100">
          {c.highlights.map((h, i) => <li key={i} className="rounded-sm border border-ink-600 bg-ink-900 p-3">{h}</li>)}
        </ul>
      )}

      <div>
        <p className="eyebrow mb-2">Readers</p>
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {c.personas.map((p) => {
            const meta = PERSONAS.find((m) => m.key === p.persona)
            const st = STATUS[p.status === 'unrated' ? 'unrated' : p.status]
            return (
              <li key={p.persona} className="rounded-sm border border-ink-600 bg-ink-900 p-3" style={{ borderLeftColor: meta?.color, borderLeftWidth: 2 }}>
                <p className="font-display">{p.persona_name}</p>
                <p className="mt-1 font-mono text-sm">{num(p.before)} → {num(p.after)}</p>
                <p className="font-mono text-[11px] uppercase tracking-wider" style={{ color: st.color }}>{st.glyph} {st.word} ({sign(p.delta)})</p>
              </li>
            )
          })}
        </ul>
      </div>

      <div>
        <p className="eyebrow mb-2">Earlier drop-offs</p>
        {c.dropoffs.length === 0
          ? <p className="text-sm text-bone-500">Nobody wanted to stop in either version.</p>
          : <ul className="space-y-1.5 text-sm">
              {c.dropoffs.map((d) => (
                <li key={d.persona + d.status} className="flex gap-2">
                  <span className="font-mono text-[11px] uppercase tracking-wider" style={{ color: d.status === 'resolved' ? '#4ade80' : '#ff6b57' }}>{d.status === 'resolved' ? 'Resolved' : d.status === 'still' ? 'Still there' : d.status === 'moved' ? 'Moved' : 'New'}</span>
                  <span className="text-bone-300">{d.text}</span>
                </li>
              ))}
            </ul>}
      </div>

      <div>
        <p className="eyebrow mb-2">Segment by segment</p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] text-left text-sm">
            <thead className="font-mono text-[11px] uppercase tracking-wider text-bone-500">
              <tr><th className="py-1 pr-3 font-normal">Segment</th><th className="font-normal">Text</th><th className="font-normal">Panel avg</th><th className="font-normal">Result</th></tr>
            </thead>
            <tbody>
              {c.segments.map((s, i) => {
                const st = STATUS[s.status]
                const moved = Object.entries(s.personas).filter(([, p]) => Math.abs(p.delta) >= 2)
                return (
                  <tr key={i} className="border-t border-ink-700 align-top">
                    <td className="py-2 pr-3">{s.rev_label ?? s.base_label}</td>
                    <td className="pr-3 text-bone-500">{s.change === 'unchanged' ? 'unchanged' : s.change === 'edited' ? 'edited' : s.change === 'new' ? 'new in this version' : 'removed'}</td>
                    <td className="pr-3 font-mono">{num(s.base_mean)} → {num(s.rev_mean)}</td>
                    <td>
                      <span style={{ color: st.color }}>{st.glyph} {st.word}{s.delta !== null ? ` (${sign(s.delta)})` : ''}</span>
                      {s.collateral && <span className="ml-2 text-xs text-persona-doom">text not edited: an earlier change may have affected it</span>}
                      {moved.length > 0 && (
                        <span className="block text-xs text-bone-500">
                          {moved.map(([k, p]) => `${PERSONAS.find((m) => m.key === k)?.name.replace('The ', '')} ${p.before}→${p.after}`).join(' · ')}
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
