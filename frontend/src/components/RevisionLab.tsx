import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError, type ChildRun, type RunDetail } from '../lib/api'

type Tab = 'revision' | 'whatif'

/** Submit version 2 (Revision Impact Tracker) or test a hypothetical edit (What If?) against a finished run. */
export default function RevisionLab({ run }: { run: RunDetail }) {
  const nav = useNavigate()
  const [tab, setTab] = useState<Tab>('revision')
  const [original, setOriginal] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [hypothesis, setHypothesis] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [children, setChildren] = useState<ChildRun[]>([])

  useEffect(() => {
    let alive = true
    api.getSubmission(run.submission_id).then((s) => { if (alive) { setOriginal(s.content); setText(s.content) } }).catch(() => {})
    api.getChildren(run.id).then((c) => alive && setChildren(c)).catch(() => {})
    return () => { alive = false }
  }, [run.id, run.submission_id])

  const unchanged = original !== null && text.trim() === original.trim()
  const canSend = !busy && original !== null && !unchanged && text.trim().length > 0 && (tab === 'revision' || hypothesis.trim().length >= 3)

  async function submit() {
    setBusy(true); setError(null)
    try {
      const r = tab === 'revision' ? await api.startRevision(run.id, text) : await api.startWhatIf(run.id, hypothesis.trim(), text)
      nav(`/run/${r.id}`)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start the simulation.')
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <div role="tablist" aria-label="Kind of test" className="flex gap-2">
        {([['revision', 'Submit version 2'], ['whatif', 'What if…?']] as const).map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`rounded-sm border px-3 py-1.5 font-mono text-xs uppercase tracking-wider ${tab === k ? 'border-lab text-lab' : 'border-ink-500 text-bone-300 hover:border-bone-500'}`}>
            {label}
          </button>
        ))}
      </div>

      <p className="max-w-2xl text-sm text-bone-300">
        {tab === 'revision'
          ? 'Edit the text below into your next draft. The same four readers read it the same way, then you see which segments improved, whether each earlier drop-off was resolved, and whether an edit hurt something else.'
          : 'Try a change without touching your draft: shorten the opening, move the reveal, clarify a motive. You write the changed text; Brutal Audience never rewrites it. The result is a hypothetical simulation, not a guaranteed improvement.'}
      </p>

      {tab === 'whatif' && (
        <label className="block">
          <span className="eyebrow">The question</span>
          <input value={hypothesis} onChange={(e) => setHypothesis(e.target.value)} maxLength={200}
            placeholder="What if the opening were shorter?"
            className="mt-2 w-full rounded-sm border border-ink-500 bg-ink-900 px-3 py-2 text-sm focus:border-lab focus:outline-none" />
        </label>
      )}

      <label className="block">
        <span className="eyebrow">{tab === 'revision' ? 'Version 2' : 'The draft with that change applied'}</span>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={12} spellCheck={false}
          className="mt-2 w-full rounded-sm border border-ink-500 bg-ink-900 p-3 font-mono text-sm leading-relaxed focus:border-lab focus:outline-none" />
      </label>

      {unchanged && <p className="text-xs text-bone-500">This is identical to the original. Change something to compare.</p>}
      {error && <p role="alert" className="text-sm text-persona-doom">{error}</p>}
      <div className="flex flex-wrap items-center gap-4">
        <button className="btn-primary" disabled={!canSend} onClick={submit}>{busy ? 'Seating the audience…' : tab === 'revision' ? 'Read version 2' : 'Run the experiment'}</button>
        <p className="text-xs text-bone-500">Uses the same mode ({run.mode}) and blind setting as this run, so the comparison is like for like.</p>
      </div>

      {children.length > 0 && (
        <div>
          <p className="eyebrow mb-2">Earlier experiments on this draft</p>
          <ul className="space-y-1.5 text-sm">
            {children.map((c) => (
              <li key={c.id} className="flex flex-wrap gap-x-3">
                <Link className="text-lab hover:underline" to={`/run/${c.id}`}>{c.kind === 'whatif' ? `What if: ${c.label ?? ''}` : 'Version 2'}</Link>
                <span className="font-mono text-xs text-bone-500">{c.status} · {c.created_at.slice(0, 16).replace('T', ' ')}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
