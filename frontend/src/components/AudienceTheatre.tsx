import { useEffect, useMemo, useState } from 'react'
import type { Reaction, Segment } from '../lib/api'
import { heat } from '../lib/heat'
import { PERSONAS } from '../lib/personas'
import { arrivalOrder, flagsFor, previousFor, type FlagKind } from '../lib/theatre'

interface Props {
  segments: Segment[]
  reactions: Reaction[]
  /** live: show reactions as they arrive. replay: step through a finished run on a timer. */
  mode: 'live' | 'replay'
  /** live mode: is the run still going? (drives the "reading…" state) */
  running?: boolean
}

const STEP_MS = 600
const FLAG_STYLE: Record<FlagKind, string> = {
  stop: 'border-persona-doom/60 text-persona-doom',
  drop: 'border-lab/60 text-lab',
  hooked: 'border-persona-fan/60 text-persona-fan',
  failed: 'border-ink-500 text-bone-500',
}

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** Steps `shown` from 0 to `total` on a timer. Starts finished when motion is reduced. */
function useReplay(total: number, enabled: boolean) {
  const [shown, setShown] = useState(total)
  const [playing, setPlaying] = useState(false)

  useEffect(() => { if (!playing) setShown(total) }, [total, playing])
  useEffect(() => {
    if (!enabled || !playing) return
    if (shown >= total) { setPlaying(false); return }
    const t = setTimeout(() => setShown((s) => s + 1), STEP_MS)
    return () => clearTimeout(t)
  }, [enabled, playing, shown, total])

  return {
    shown, playing,
    start: () => { setShown(0); setPlaying(true) },
    pause: () => setPlaying(false),
    resume: () => setPlaying(true),
    finish: () => { setShown(total); setPlaying(false) },
  }
}

/**
 * The audience, seated. Each persona shows what they are reading and how the last segment
 * landed; a feed underneath lists every reaction in the order it happened.
 *
 * Everything shown is recorded reaction data. Flags such as "would stop" or "fell 4 points"
 * are computed from the stored numbers, so the theatre never claims anything the data does not.
 */
export default function AudienceTheatre({ segments, reactions, mode, running = false }: Props) {
  const events = useMemo(() => arrivalOrder(reactions), [reactions])
  const replay = useReplay(events.length, mode === 'replay')
  const [autoNote] = useState(prefersReducedMotion)

  const visible = mode === 'live' ? events : events.slice(0, replay.shown)
  const active = mode === 'live' ? running : replay.playing

  const seats = PERSONAS.map((p) => {
    const mine = visible.filter((r) => r.persona === p.key)
    const last = [...mine].sort((a, b) => b.segment_id - a.segment_id)[0]
    const stoppedAt = mine.filter((r) => r.would_continue === false).sort((a, b) => a.segment_id - b.segment_id)[0]
    const next = segments[mine.length]
    return { p, mine, last, stoppedAt, next, done: mine.length >= segments.length }
  })
  const labelOf = (id: number) => segments.find((s) => s.id === id)?.label ?? `Segment ${id}`
  const feed = [...visible].reverse()

  return (
    <div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {seats.map(({ p, mine, last, stoppedAt, next, done }) => {
          const reading = active && !done && !!next
          return (
            <article key={p.key} aria-label={p.name} className="flex min-h-[188px] flex-col rounded-sm border border-ink-600 bg-ink-900 p-3"
              style={{ borderTopColor: p.color, borderTopWidth: 2 }}>
              <header className="flex items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-2">
                  <span style={{ color: p.color }} aria-hidden>{p.glyph}</span>
                  <span className="truncate font-display">{p.name.replace('The ', '')}</span>
                </span>
                <span className="font-mono text-[11px] text-bone-500">{mine.length}/{segments.length}</span>
              </header>

              <p className="mt-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-bone-500">
                {reading && <span aria-hidden className="inline-block h-1.5 w-1.5 animate-blink rounded-full" style={{ background: p.color }} />}
                {reading ? `Reading ${next!.label}…` : done ? 'Finished reading' : mine.length ? 'Paused' : 'Waiting for the first segment'}
              </p>

              {last && last.status === 'ok' ? (
                <div key={`${last.persona}:${last.segment_id}`} className="mt-3 animate-rise">
                  <div className="flex items-center gap-2">
                    <span className="rounded-sm px-1.5 py-0.5 font-mono text-xs font-medium text-ink-950" style={{ background: heat(last.engagement_score ?? 0) }}>
                      {last.engagement_score}/10
                    </span>
                    <span className="font-mono text-[10px] uppercase tracking-wider text-bone-300">{last.emotion}</span>
                  </div>
                  <p className="mt-2 font-display text-[15px] italic leading-snug text-bone-100">“{last.inner_thought}”</p>
                </div>
              ) : last ? (
                <p className="mt-3 text-xs text-bone-500">No reaction recorded for {labelOf(last.segment_id)}.</p>
              ) : null}

              {stoppedAt && (
                <p className="mt-auto pt-3 font-mono text-[10px] uppercase tracking-wider text-persona-doom">
                  ✕ First wanted to stop at {labelOf(stoppedAt.segment_id)}
                </p>
              )}
            </article>
          )
        })}
      </div>

      {mode === 'replay' && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {replay.playing
            ? <button className="btn-ghost" onClick={replay.pause}>Pause</button>
            : replay.shown > 0 && replay.shown < events.length
              ? <button className="btn-ghost" onClick={replay.resume}>Resume</button>
              : null}
          <button className="btn-primary !px-4 !py-2 !text-xs" onClick={replay.start} disabled={events.length === 0}>
            {replay.shown === events.length && !replay.playing ? '▶ Watch the audience read it' : '↺ Restart'}
          </button>
          {replay.playing && <button className="btn-ghost" onClick={replay.finish}>Skip to end</button>}
          <span className="font-mono text-[11px] text-bone-500" aria-live="off">{replay.shown}/{events.length} reactions</span>
          {autoNote && <span className="font-mono text-[11px] text-bone-700">Reduced motion is on, so the replay does not start by itself.</span>}
        </div>
      )}

      <div className="mt-6">
        <p className="eyebrow mb-2">Reaction feed · newest first</p>
        {feed.length === 0 ? (
          <p className="rounded-sm border border-dashed border-ink-500 p-4 text-sm text-bone-500">
            {mode === 'live' ? 'Waiting for the first reaction…' : 'Press “Watch the audience read it” to replay the reading.'}
          </p>
        ) : (
          <ol className="max-h-[22rem] space-y-1.5 overflow-y-auto pr-1" role={mode === 'live' ? 'log' : undefined} aria-live={mode === 'live' ? 'polite' : undefined}>
            {feed.map((r, i) => {
              const p = PERSONAS.find((x) => x.key === r.persona)!
              const flags = flagsFor(r, previousFor(r, events))
              return (
                <li key={`${r.persona}:${r.segment_id}`} className={`rounded-sm border border-ink-700 bg-ink-900/70 p-2.5 text-sm ${i === 0 ? 'animate-rise' : ''}`}
                  style={{ borderLeftColor: p.color, borderLeftWidth: 2 }}>
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                    <span className="font-display">{p.name.replace('The ', '')}</span>
                    <span className="font-mono text-[11px] text-bone-500">on {labelOf(r.segment_id)}</span>
                    {r.status === 'ok' && (
                      <span className="font-mono text-[11px] text-bone-300">felt {r.emotion} · {r.engagement_score}/10</span>
                    )}
                    {flags.map((f) => (
                      <span key={f.kind} className={`rounded-sm border px-1.5 py-px font-mono text-[10px] uppercase tracking-wider ${FLAG_STYLE[f.kind]}`}>{f.text}</span>
                    ))}
                  </div>
                  {r.status === 'ok' && r.inner_thought && <p className="mt-1 italic text-bone-300">“{r.inner_thought}”</p>}
                </li>
              )
            })}
          </ol>
        )}
      </div>
      <p className="mt-3 font-mono text-[10px] uppercase tracking-widest text-bone-700">
        Simulated reactions, not measured audience data.
      </p>
    </div>
  )
}
