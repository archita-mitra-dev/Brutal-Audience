import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import AudienceTheatre from '../components/AudienceTheatre'
import BlindBadge from '../components/BlindBadge'
import Dashboard from '../components/Dashboard'
import ModeBanner from '../components/ModeBanner'
import PersonaLanes from '../components/PersonaLanes'
import ReactionDetail from '../components/ReactionDetail'
import { api, ApiError, TERMINAL, type Reaction } from '../lib/api'
import { PERSONAS } from '../lib/personas'
import { useRun } from '../lib/useRun'

export default function RunPage() {
  const { runId } = useParams()
  const { run, error } = useRun(runId)
  const [pinned, setPinned] = useState<{ persona: string; segmentId: number } | null>(null)
  const [cancelError, setCancelError] = useState<string | null>(null)

  const reactions = run?.reactions ?? []
  const segments = run?.segments ?? []

  // Default view: follow the most recently read segment until the user picks a cell.
  const latest = useMemo<Reaction | null>(() => {
    const ok = reactions.filter((r) => r.status === 'ok')
    if (!ok.length) return null
    return [...ok].sort((a, b) => b.segment_id - a.segment_id || PERSONAS.findIndex(p => p.key === a.persona) - PERSONAS.findIndex(p => p.key === b.persona))[0]
  }, [reactions])

  const selectedReaction =
    (pinned && reactions.find((r) => r.persona === pinned.persona && r.segment_id === pinned.segmentId)) || latest
  const selectedSegment = selectedReaction ? segments.find((s) => s.id === selectedReaction.segment_id) ?? null : null
  const selection = selectedReaction ? { persona: selectedReaction.persona, segmentId: selectedReaction.segment_id } : null

  if (error && !run) {
    return (
      <main className="mx-auto max-w-xl px-5 py-24 text-center">
        <p role="alert" className="text-persona-doom">{error}</p>
        <Link to="/workspace" className="btn-ghost mt-6">Back to the workspace</Link>
      </main>
    )
  }
  if (!run) {
    return (
      <main className="mx-auto max-w-xl px-5 py-24 text-center">
        <p className="eyebrow animate-blink">Seating the audience…</p>
      </main>
    )
  }

  const finished = TERMINAL.includes(run.status)
  const showDashboard = finished && reactions.some((r) => r.status === 'ok')
  const pct = run.total_steps ? Math.round((run.done_steps / run.total_steps) * 100) : 0

  async function cancel() {
    setCancelError(null)
    try { await api.cancelRun(run!.id) } catch (e) { setCancelError(e instanceof ApiError ? e.message : 'Could not cancel.') }
  }

  return (
    <main className="mx-auto max-w-6xl px-5 py-10">
      <p className="eyebrow">Step 3 of 3 · {finished ? 'Results' : 'The reading room'}</p>
      <h1 className="mt-2 font-display text-3xl sm:text-4xl">“{run.title}”</h1>
      <div className="mt-4 space-y-3"><ModeBanner mode={run.mode} model={run.model} /><BlindBadge blind={run.blind} /></div>

      {/* progress */}
      <section aria-label="Simulation progress" className="mt-6">
        <div className="flex items-center justify-between gap-4">
          <p className="font-mono text-xs uppercase tracking-wider text-bone-300" aria-live="polite">
            {run.status === 'running' || run.status === 'queued'
              ? <span className="animate-blink">Audience reading… {run.done_steps}/{run.total_steps} reactions</span>
              : run.status === 'completed' ? `Finished · ${run.done_steps} reactions`
              : run.status === 'cancelled' ? `Stopped · ${run.done_steps} of ${run.total_steps} reactions`
              : `Failed · ${run.done_steps} of ${run.total_steps} reactions`}
          </p>
          {!finished && <button className="btn-ghost" onClick={cancel}>Stop</button>}
        </div>
        <div className="mt-2 h-1.5 w-full overflow-hidden bg-ink-700" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div className="h-full bg-lab transition-all duration-500" style={{ width: `${pct}%` }} />
        </div>
        {cancelError && <p role="alert" className="mt-2 text-sm text-persona-doom">{cancelError}</p>}
        {error && <p className="mt-2 text-xs text-persona-doom">{error} Retrying…</p>}
      </section>

      {run.status === 'failed' && run.error && (
        <p role="alert" className="mt-6 rounded-sm border border-persona-doom/50 bg-persona-doom/10 p-4 text-sm text-persona-doom">
          The simulation stopped: {run.error}
        </p>
      )}

      {showDashboard ? (
        <>
          <Dashboard run={run} />
          <Link to="/workspace" className="btn-ghost mt-14">Test another draft</Link>
        </>
      ) : (
        <>
      {/* theatre */}
      <section className="mt-8" aria-label="Live audience theatre">
        <p className="eyebrow mb-3">The audience, live</p>
        <AudienceTheatre segments={segments} reactions={reactions} mode="live" running={!finished} />
      </section>

      {/* lanes */}
      <section className="mt-10" aria-label="Audience lanes">
        <p className="eyebrow mb-3">Reading progress</p>
        <PersonaLanes
          segments={segments}
          reactions={reactions}
          selected={selection}
          onSelect={(persona, segmentId) => setPinned({ persona, segmentId })}
        />
      </section>

      {/* detail + feed */}
      <div className="mt-8 grid gap-8 lg:grid-cols-[1.2fr_1fr]">
        <section aria-label="Selected reaction">
          <ReactionDetail reaction={selectedReaction} segment={selectedSegment} />
        </section>

        <section aria-label="Per-persona summary">
          <p className="eyebrow mb-3">Where each reader is at</p>
          <ul className="space-y-2">
            {PERSONAS.map((p) => {
              const mine = reactions.filter((r) => r.persona === p.key)
              const ok = mine.filter((r) => r.status === 'ok')
              const avg = ok.length ? ok.reduce((n, r) => n + (r.engagement_score ?? 0), 0) / ok.length : null
              const firstQuit = ok.filter((r) => r.would_continue === false).sort((a, b) => a.segment_id - b.segment_id)[0]
              const failed = mine.length - ok.length
              return (
                <li key={p.key} className="rounded-sm border border-ink-600 bg-ink-900 p-3" style={{ borderLeftColor: p.color, borderLeftWidth: 2 }}>
                  <div className="flex items-baseline justify-between">
                    <span className="font-display">{p.name}</span>
                    <span className="font-mono text-xs text-bone-500">{mine.length}/{segments.length} read</span>
                  </div>
                  <p className="mt-1 font-mono text-[11px] uppercase tracking-wider text-bone-500">
                    {avg === null ? 'no reactions yet' : `avg ${avg.toFixed(1)}/10`}
                    {firstQuit && <span className="text-persona-doom"> · first wanted to stop at segment {firstQuit.segment_id}</span>}
                    {failed > 0 && <span className="text-persona-doom"> · {failed} without reaction</span>}
                  </p>
                </li>
              )
            })}
          </ul>
          <Link to="/workspace" className="btn-ghost mt-5">Test another draft</Link>
        </section>
      </div>
        </>
      )}
    </main>
  )
}
