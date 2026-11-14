import type { Reaction, Segment } from '../lib/api'
import { heat } from '../lib/heat'
import { PERSONAS } from '../lib/personas'

/** Segment text with the persona's quoted evidence highlighted (only if it truly appears). */
function HighlightedText({ text, evidence }: { text: string; evidence: string | null }) {
  const idx = evidence ? text.toLowerCase().indexOf(evidence.toLowerCase()) : -1
  if (!evidence || idx === -1) return <>{text}</>
  return (
    <>
      {text.slice(0, idx)}
      <mark className="rounded-[2px] bg-lab/25 px-0.5 text-bone-100">{text.slice(idx, idx + evidence.length)}</mark>
      {text.slice(idx + evidence.length)}
    </>
  )
}

export default function ReactionDetail({ reaction, segment }: { reaction: Reaction | null; segment: Segment | null }) {
  if (!reaction || !segment) {
    return (
      <div className="rounded-sm border border-dashed border-ink-500 p-8 text-center">
        <p className="font-display text-lg text-bone-300">Waiting for the first reaction…</p>
        <p className="mt-1 text-sm text-bone-500">Click any lit cell to read that persona’s reaction.</p>
      </div>
    )
  }
  const p = PERSONAS.find((x) => x.key === reaction.persona)!

  return (
    <article className="rounded-sm border border-ink-600 bg-ink-900" style={{ borderTopColor: p.color, borderTopWidth: 2 }}>
      <header className="flex items-center justify-between gap-3 border-b border-ink-700 px-4 py-3">
        <div className="flex items-center gap-2">
          <span style={{ color: p.color }} aria-hidden>{p.glyph}</span>
          <h3 className="font-display text-lg">{p.name}</h3>
          <span className="font-mono text-xs text-bone-500">· {segment.label}</span>
        </div>
        {reaction.status === 'ok' && (
          <div className="flex items-center gap-2">
            <span className="rounded-sm px-2 py-0.5 font-mono text-sm font-medium text-ink-950" style={{ background: heat(reaction.engagement_score ?? 0) }}>
              {reaction.engagement_score}/10
            </span>
            <span className="font-mono text-xs uppercase tracking-wider text-bone-300">{reaction.emotion}</span>
          </div>
        )}
      </header>

      <div className="space-y-4 p-4">
        {reaction.status === 'failed' ? (
          <p role="alert" className="text-sm text-persona-doom">
            No reaction was recorded for this segment: {reaction.error}
          </p>
        ) : (
          <>
            <p className="font-display text-lg italic leading-snug text-bone-100">“{reaction.inner_thought}”</p>
            <p className="text-sm text-bone-300">{reaction.reason}</p>
            <p className="font-mono text-[11px] uppercase tracking-wider text-bone-500">
              {reaction.would_continue ? 'Would keep reading' : 'Would stop reading here'}
              {reaction.attempts > 1 && ` · needed ${reaction.attempts} attempts`}
            </p>
            {reaction.evidence ? (
              <blockquote className="border-l-2 border-lab pl-3 text-sm text-bone-300">
                <span className="eyebrow block">Evidence (verbatim)</span>
                {reaction.evidence}
              </blockquote>
            ) : (
              <p className="text-xs text-bone-500">No verifiable quote was returned for this reaction, so none is shown.</p>
            )}
          </>
        )}

        <div>
          <p className="eyebrow">The passage they were reading</p>
          <p className="mt-1.5 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-sm bg-ink-950 p-3 font-mono text-[12.5px] leading-relaxed text-bone-300">
            <HighlightedText text={segment.text} evidence={reaction.evidence} />
          </p>
        </div>
      </div>
    </article>
  )
}
