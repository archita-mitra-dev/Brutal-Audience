import type { Meter } from '../lib/api'
import { DOCUMENT_STYLE, SEGMENT_ORDER, SEGMENT_STYLE } from '../lib/meter'

interface Props { meter: Meter; onJump: (segmentId: number) => void }

/** Plain-rule classification of every segment and of the whole work. No model is involved. */
export default function BrutalityMeter({ meter, onJump }: Props) {
  const doc = meter.document
  const t = meter.thresholds
  if (!doc) return <p className="text-sm text-bone-500">There are no rated segments to classify yet.</p>
  const style = DOCUMENT_STYLE[doc.level]
  const n = meter.segments.length

  const ruleFor: Record<string, string> = {
    strong: `panel average ${t.strong_mean} or more, and nobody would stop`,
    curious: `panel average ${t.curious_mean} to ${t.strong_mean}, and nobody would stop`,
    declining: `panel average under ${t.curious_mean}, or one reader would stop`,
    multi_stop: `${t.multi_stop_readers}+ readers would stop, or scored ${t.low_score} or lower`,
  }

  return (
    <div className="space-y-6">
      <div className="rounded-sm border bg-ink-900 p-5" style={{ borderColor: style.color + '99', borderLeftWidth: 4 }}>
        <p className="eyebrow">Document verdict</p>
        <p className="mt-2 flex items-center gap-3 font-display text-3xl" style={{ color: style.color }}>
          <span aria-hidden>{style.glyph}</span>{doc.name}
        </p>
        <p className="mt-2 max-w-2xl text-sm text-bone-300">{doc.rule}</p>
        <p className="mt-2 font-mono text-[11px] uppercase tracking-wider text-bone-500">
          {doc.never_stopped.length === 0
            ? `No reader got through without wanting to stop at least once`
            : `${doc.never_stopped.length} of ${doc.persona_count} readers never wanted to stop: ${doc.never_stopped.map((x) => x.replace('The ', '')).join(', ')}`}
        </p>
      </div>

      <div>
        <p className="eyebrow mb-2">Segment by segment · click one to inspect it</p>
        <ol className="flex flex-wrap gap-1.5" aria-label="Brutality level of each segment">
          {meter.segments.map((m) => {
            const s = SEGMENT_STYLE[m.level]
            return (
              <li key={m.segment_id}>
                <button type="button" onClick={() => onJump(m.segment_id)}
                  title={`${m.label}: ${m.name}. ${m.rule}`} aria-label={`${m.label}: ${m.name}. ${m.rule}`}
                  className="flex h-9 min-w-[2.25rem] items-center justify-center gap-1 rounded-sm border px-1.5 font-mono text-[11px] transition hover:brightness-125 focus:outline-none focus-visible:ring-2 focus-visible:ring-lab"
                  style={{ borderColor: s.color + '99', background: s.color + '1f', color: s.color }}>
                  <span aria-hidden>{s.glyph}</span>{m.segment_id}
                </button>
              </li>
            )
          })}
        </ol>
      </div>

      <ul className="grid gap-2 sm:grid-cols-2">
        {SEGMENT_ORDER.map((lvl) => {
          const s = SEGMENT_STYLE[lvl]
          const count = doc.counts[lvl] ?? 0
          const name = meter.segments.find((m) => m.level === lvl)?.name
            ?? { strong: 'Strong engagement', curious: 'Audience wants to know more', declining: 'Engagement is declining', multi_stop: 'Multiple personas would stop reading' }[lvl]
          return (
            <li key={lvl} className="rounded-sm border border-ink-600 bg-ink-900 p-3">
              <p className="flex items-baseline justify-between gap-2">
                <span className="font-display" style={{ color: s.color }}><span aria-hidden>{s.glyph} </span>{name}</span>
                <span className="font-mono text-xs text-bone-300">{count} of {n}</span>
              </p>
              <p className="mt-1 font-mono text-[11px] text-bone-500">Rule: {ruleFor[lvl]}.</p>
            </li>
          )
        })}
      </ul>

      <details className="rounded-sm border border-ink-700 p-3 text-sm text-bone-500">
        <summary className="cursor-pointer font-mono text-[11px] uppercase tracking-wider text-bone-300">How the document verdict is decided</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li><b className="text-bone-300">Brutal:</b> {Math.round(t.brutal_multi_share * 100)}%+ of segments would lose multiple readers, or the panel average is under {t.brutal_mean}.</li>
          <li><b className="text-bone-300">Shaky:</b> {Math.round(t.shaky_weak_share * 100)}%+ of segments are declining or worse, or the average is under {t.shaky_mean}.</li>
          <li><b className="text-bone-300">Holds the room:</b> at most {Math.round(t.holds_weak_share * 100)}% declining or worse, and an average of {t.strong_mean}+.</li>
          <li><b className="text-bone-300">Mostly holds:</b> everything in between.</li>
        </ul>
        <p className="mt-2">These are fixed rules over the simulated reactions, not a model’s opinion. The thresholds are sensible defaults, not validated measures.</p>
      </details>
    </div>
  )
}
