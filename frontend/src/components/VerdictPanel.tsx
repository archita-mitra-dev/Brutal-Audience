import { useEffect, useState } from 'react'
import { api, ApiError, type Segment, type Verdict } from '../lib/api'
import { PERSONAS } from '../lib/personas'

function toText(v: Verdict, segs: Map<number, Segment>): string {
  const label = (id: number) => segs.get(id)?.label ?? `Segment ${id}`
  const lines = [
    `BRUTAL VERDICT (${v.mode === 'demo' ? 'DEMO, not AI' : `simulated audience · ${v.model}`})`,
    '', v.overall, '',
    v.strongest ? `Strongest: ${v.strongest.label} (${v.strongest.mean?.toFixed(1)}/10). ${v.strongest.why}` : null,
    v.weakest ? `Weakest: ${v.weakest.label} (${v.weakest.mean?.toFixed(1)}/10). ${v.weakest.why}` : null,
    '', 'Drop-off points:',
    ...(v.drop_offs.length ? v.drop_offs.map((d) => `- ${d.label}: ${d.persona_names.join(', ')}`) : ['- none']),
    '', 'By persona:',
    ...v.persona_takes.flatMap((t) => [`${t.persona_name}`, `  Liked: ${t.liked}`, `  Disliked: ${t.disliked}`]),
    v.polarising_note ? `\nSplit audience: ${v.polarising_note}` : null,
    '', 'Suggestions:',
    ...v.suggestions.flatMap((s, i) => [
      `${i + 1}. ${s.title} (${s.segment_ids.map(label).join(', ')})`,
      `   Problem: ${s.problem}`, `   Consider: ${s.action}`, s.evidence ? `   Evidence: "${s.evidence}"` : null,
    ]),
  ]
  return lines.filter((l): l is string => typeof l === 'string').join('\n')
}

export default function VerdictPanel({
  runId, segments, onJump,
}: { runId: string; segments: Segment[]; onJump: (segId: number) => void }) {
  const [verdict, setVerdict] = useState<Verdict | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const segMap = new Map(segments.map((s) => [s.id, s]))

  useEffect(() => {
    let alive = true
    api.getVerdict(runId)
      .then((v) => alive && setVerdict(v))
      .catch((e) => { if (alive && !(e instanceof ApiError && e.status === 404)) setError(e instanceof ApiError ? e.message : 'Could not load the verdict.') })
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [runId])

  async function generate() {
    setBusy(true); setError(null)
    try { setVerdict(await api.createVerdict(runId)) }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Could not generate the verdict.') }
    finally { setBusy(false) }
  }

  async function copy() {
    if (!verdict) return
    try { await navigator.clipboard.writeText(toText(verdict, segMap)); setCopied(true); setTimeout(() => setCopied(false), 1800) }
    catch { setError('Copy failed. Your browser blocked clipboard access.') }
  }

  const Ref = ({ id }: { id: number }) => (
    <button className="rounded-sm border border-ink-500 px-1.5 py-0.5 font-mono text-[11px] text-bone-300 hover:border-lab hover:text-lab" onClick={() => onJump(id)}>
      {segMap.get(id)?.label ?? `Segment ${id}`}
    </button>
  )

  if (loading) return <p className="eyebrow animate-blink">Checking for a saved verdict…</p>

  if (!verdict) {
    return (
      <div className="rounded-sm border border-dashed border-ink-500 p-8 text-center">
        <p className="font-display text-xl">Ready for the verdict?</p>
        <p className="mx-auto mt-2 max-w-md text-sm text-bone-500">
          A short report with the strongest and weakest moments, what each reader liked and disliked, and three specific suggestions linked to exact passages. It recommends; it never edits your draft.
        </p>
        <button className="btn-primary mt-6" onClick={generate} disabled={busy}>{busy ? 'Writing the verdict…' : 'Deliver the Brutal Verdict →'}</button>
        {error && <p role="alert" className="mt-4 text-sm text-persona-doom">{error}</p>}
      </div>
    )
  }

  return (
    <article className="space-y-8">
      {verdict.mode === 'demo' ? (
        <div role="note" className="rounded-sm border border-lab/60 bg-lab/10 p-3 font-mono text-xs uppercase tracking-widest text-lab">
          Demo verdict · assembled from text statistics, not an AI audience
        </div>
      ) : (
        <p className="font-mono text-[11px] uppercase tracking-widest text-bone-500">Simulated audience, not real readers · {verdict.model}</p>
      )}

      <p className="max-w-3xl font-display text-2xl leading-snug">{verdict.overall}</p>

      <div className="grid gap-4 md:grid-cols-2">
        {([['Strongest moment', verdict.strongest, 'text-persona-fan'], ['Weakest moment', verdict.weakest, 'text-persona-doom']] as const).map(([title, n, cls]) => n && (
          <section key={title} className="rounded-sm border border-ink-600 bg-ink-900 p-4">
            <p className={`eyebrow ${cls}`}>{title}</p>
            <p className="mt-2 flex items-center gap-3"><Ref id={n.segment_id} /><span className="font-mono text-xs text-bone-500">panel avg {n.mean?.toFixed(1)}/10</span></p>
            <p className="mt-2 text-sm text-bone-300">{n.why}</p>
          </section>
        ))}
      </div>

      <section>
        <p className="eyebrow">Predicted drop-off points</p>
        {verdict.drop_offs.length === 0 ? <p className="mt-2 text-sm text-bone-500">No reader wanted to stop.</p> : (
          <ul className="mt-3 flex flex-wrap gap-3">
            {verdict.drop_offs.map((d) => (
              <li key={d.segment_id} className="flex items-center gap-2 text-sm text-bone-500"><Ref id={d.segment_id} />{d.persona_names.map((n) => n.replace('The ', '')).join(', ')}</li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <p className="eyebrow">What each reader made of it</p>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {verdict.persona_takes.map((t) => {
            const p = PERSONAS.find((x) => x.key === t.persona)
            return (
              <div key={t.persona} className="rounded-sm border border-ink-600 bg-ink-900 p-4" style={{ borderLeftColor: p?.color, borderLeftWidth: 2 }}>
                <p className="font-display">{t.persona_name}</p>
                <p className="mt-2 text-sm text-bone-300"><span className="font-mono text-[10px] uppercase tracking-wider text-persona-fan">Liked </span>{t.liked}</p>
                <p className="mt-2 text-sm text-bone-300"><span className="font-mono text-[10px] uppercase tracking-wider text-persona-doom">Disliked </span>{t.disliked}</p>
              </div>
            )
          })}
        </div>
        {verdict.polarising_note && <p className="mt-4 max-w-3xl text-sm text-bone-500">{verdict.polarising_note}</p>}
      </section>

      <section>
        <p className="eyebrow">Suggestions, in order of importance</p>
        <ol className="mt-3 space-y-4">
          {verdict.suggestions.map((s, i) => (
            <li key={i} className="rounded-sm border border-ink-600 bg-ink-900 p-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-mono text-lab">{String(i + 1).padStart(2, '0')}</span>
                <h4 className="font-display text-lg">{s.title}</h4>
                {s.segment_ids.map((id) => <Ref key={id} id={id} />)}
              </div>
              <p className="mt-2 text-sm text-bone-300"><span className="font-mono text-[10px] uppercase tracking-wider text-bone-500">What happened </span>{s.problem}</p>
              <p className="mt-2 text-sm text-bone-300"><span className="font-mono text-[10px] uppercase tracking-wider text-bone-500">Consider </span>{s.action}</p>
              {s.evidence && <blockquote className="mt-3 border-l-2 border-lab pl-3 text-sm text-bone-500">“{s.evidence}”</blockquote>}
            </li>
          ))}
        </ol>
        <p className="mt-3 text-xs text-bone-700">These are recommendations. Nothing here changes your draft, and the decisions are yours.</p>
      </section>

      <div className="flex flex-wrap items-center gap-3">
        <button className="btn-ghost" onClick={copy}>{copied ? 'Copied ✓' : 'Copy report as text'}</button>
        <button className="btn-ghost" onClick={generate} disabled={busy}>{busy ? 'Regenerating…' : 'Regenerate verdict'}</button>
        {error && <span role="alert" className="text-sm text-persona-doom">{error}</span>}
      </div>
    </article>
  )
}
