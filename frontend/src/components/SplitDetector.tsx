import type { SplitReader, SplitReport } from '../lib/api'
import { PERSONAS } from '../lib/personas'

const color = (key: string) => PERSONAS.find((p) => p.key === key)?.color ?? '#8d8a82'

function Readers({ title, readers }: { title: string; readers: SplitReader[] }) {
  return (
    <div>
      <p className="eyebrow">{title}</p>
      <ul className="mt-1.5 space-y-1">
        {readers.map((r) => (
          <li key={r.persona} className="flex items-baseline gap-2 text-sm">
            <span aria-hidden style={{ color: color(r.persona) }}>●</span>
            <span>{r.persona_name.replace('The ', '')}</span>
            <span className="font-mono text-xs text-bone-500">{r.score}/10</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

interface Props { data: SplitReport; onJump: (segmentId: number) => void }

/** Who the work is for, and where different kinds of reader part ways. */
export default function SplitDetector({ data, onJump }: Props) {
  const top = data.fit[0]?.avg ?? 10
  return (
    <div className="space-y-8">
      <div>
        <p className="eyebrow">Fit by audience</p>
        <ul className="mt-3 space-y-2">
          {data.fit.map((f) => (
            <li key={f.persona} className="grid grid-cols-[9rem_1fr_3rem] items-center gap-3 text-sm">
              <span className="truncate text-bone-300">{f.audience}</span>
              <span className="h-2 bg-ink-700" role="img" aria-label={`${f.persona_name} average ${f.avg} out of 10`}>
                <span className="block h-full" style={{ width: `${Math.max(2, (f.avg / 10) * 100)}%`, background: color(f.persona), opacity: f.avg === top ? 1 : 0.7 }} />
              </span>
              <span className="text-right font-mono text-xs text-bone-300">{f.avg.toFixed(1)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 max-w-2xl text-sm text-bone-300">{data.work_note}</p>
        {data.divides.length > 0 && (
          <p className="mt-2 font-mono text-[11px] uppercase tracking-wider text-bone-500">
            Most common divide: {data.divides[0].high.replace('The ', '')} above {data.divides[0].low.replace('The ', '')} in {data.divides[0].count} segment{data.divides[0].count === 1 ? '' : 's'}
          </p>
        )}
      </div>

      {data.segments.length === 0 ? (
        <p className="rounded-sm border border-ink-600 p-4 text-sm text-bone-500">
          No segment split the readers by {data.thresholds.split_gap} points or more.
        </p>
      ) : (
        <ul className="space-y-4">
          {data.segments.map((s) => (
            <li key={s.segment_id} className="rounded-sm border border-ink-600 bg-ink-900 p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <button type="button" onClick={() => onJump(s.segment_id)} className="font-display text-lg underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-lab">{s.label}</button>
                <span className="font-mono text-xs text-bone-500">{s.gap}-point gap</span>
              </div>
              <p className="mt-2 text-bone-100">{s.headline}</p>
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <Readers title="Responded strongly" readers={s.appeals_to} />
                <Readers title="Lost them" readers={s.loses} />
              </div>
              <p className="mt-3 text-sm text-bone-500">{s.why}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
