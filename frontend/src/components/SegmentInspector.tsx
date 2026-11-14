import { useState } from 'react'
import type { Segment } from '../lib/api'

interface Props {
  segments: Segment[]
  loading: boolean
  truncated: boolean
  error: string | null
}

/** Proportional strip: one block per segment, width ∝ length. Click to jump. */
function DocumentMap({ segments, active, onPick }: { segments: Segment[]; active: number | null; onPick: (id: number) => void }) {
  const total = segments.reduce((n, s) => n + Math.max(s.text.length, 1), 0)
  return (
    <div className="flex h-3 w-full gap-px overflow-hidden rounded-sm" aria-label="Document map">
      {segments.map((s) => (
        <button
          key={s.id}
          type="button"
          title={`${s.label} · ${s.word_count} words`}
          onClick={() => onPick(s.id)}
          style={{ width: `${(Math.max(s.text.length, 1) / total) * 100}%` }}
          className={`h-full min-w-[3px] transition ${active === s.id ? 'bg-lab' : 'bg-ink-500 hover:bg-bone-500'}`}
        />
      ))}
    </div>
  )
}

export default function SegmentInspector({ segments, loading, truncated, error }: Props) {
  const [open, setOpen] = useState<number | null>(null)

  const pick = (id: number) => {
    setOpen(id)
    document.getElementById(`seg-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }

  if (error) {
    return <p role="alert" className="rounded-sm border border-persona-doom/50 bg-persona-doom/10 p-4 text-sm text-persona-doom">{error}</p>
  }

  if (segments.length === 0) {
    return (
      <div className="rounded-sm border border-dashed border-ink-500 p-8 text-center">
        <p className="font-display text-lg text-bone-300">No segments yet.</p>
        <p className="mt-1 text-sm text-bone-500">Paste or upload some writing and it will be split here, live.</p>
      </div>
    )
  }

  return (
    <div className={loading ? 'opacity-60 transition' : 'transition'}>
      <DocumentMap segments={segments} active={open} onPick={pick} />
      <ol className="mt-4 max-h-[520px] space-y-1.5 overflow-y-auto pr-1">
        {segments.map((s) => {
          const isOpen = open === s.id
          return (
            <li key={s.id} id={`seg-${s.id}`} className="rounded-sm border border-ink-600 bg-ink-900">
              <button
                type="button"
                aria-expanded={isOpen}
                onClick={() => setOpen(isOpen ? null : s.id)}
                className="flex w-full items-start gap-3 px-3 py-2.5 text-left"
              >
                <span className="mt-0.5 w-9 shrink-0 font-mono text-xs text-lab">#{s.id}</span>
                <span className={`flex-1 text-sm text-bone-300 ${isOpen ? '' : 'line-clamp-2'}`}>
                  {isOpen ? s.text : s.text.replace(/\s+/g, ' ')}
                </span>
                <span className="shrink-0 font-mono text-[10px] uppercase tracking-wider text-bone-700">{s.word_count}w</span>
              </button>
              {isOpen && (
                <div className="flex flex-wrap gap-x-5 gap-y-1 border-t border-ink-600 px-3 py-2 font-mono text-[10px] uppercase tracking-wider text-bone-500">
                  <span>{s.label}</span>
                  <span>chars {s.char_start}–{s.char_end}</span>
                </div>
              )}
            </li>
          )
        })}
      </ol>
      {truncated && (
        <p className="mt-3 text-xs text-persona-doom">
          This work has more segments than a single test can cover; the audience will read the first {segments.length}.
        </p>
      )}
    </div>
  )
}
