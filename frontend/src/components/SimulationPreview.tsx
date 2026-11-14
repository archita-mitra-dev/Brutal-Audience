import { useEffect, useState } from 'react'
import { heat } from '../lib/heat'
import { PERSONAS } from '../lib/personas'

/**
 * ILLUSTRATIVE ONLY — a looping animation that shows *how* the simulation reads:
 * each persona moves through the segments in order and a heat cell lights up.
 * The values below are fixed decoration, not AI output, and the component says so.
 */
const COLS = 12
const DEMO: number[][] = [
  [8, 6, 3, 2, 2, 4, 7, 8, 6, 4, 3, 5], // doom
  [5, 6, 4, 3, 5, 7, 6, 4, 3, 6, 8, 7], // critic
  [4, 5, 7, 8, 9, 7, 6, 8, 9, 8, 7, 8], // fan
  [6, 4, 2, 3, 4, 5, 3, 4, 6, 7, 6, 6], // newbie
]

export default function SimulationPreview() {
  const [cursor, setCursor] = useState(0)

  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) { setCursor(COLS); return }
    const id = setInterval(() => setCursor((c) => (c >= COLS + 3 ? 0 : c + 1)), 520)
    return () => clearInterval(id)
  }, [])

  return (
    <figure className="rounded-sm border border-ink-600 bg-ink-900/80 p-4 sm:p-6">
      <figcaption className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <span className="eyebrow">Sequential read-through</span>
        <span className="rounded-sm border border-lab/40 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-lab">
          Illustration · not real results
        </span>
      </figcaption>

      <div className="space-y-2.5" role="img" aria-label="Illustration: four personas reading twelve segments in order, with engagement shown as colour intensity">
        {PERSONAS.map((p, row) => (
          <div key={p.key} className="flex items-center gap-3">
            <div className="flex w-28 shrink-0 items-center gap-2 sm:w-40">
              <span style={{ color: p.color }} aria-hidden>{p.glyph}</span>
              <span className="truncate font-mono text-[11px] uppercase tracking-wider text-bone-300">
                {p.name.replace('The ', '')}
              </span>
            </div>
            <div className="grid flex-1 grid-cols-12 gap-1">
              {DEMO[row].map((v, col) => {
                const read = col < cursor
                const current = col === cursor - 1 && cursor <= COLS
                return (
                  <div
                    key={col}
                    className="relative aspect-square rounded-[2px] transition-all duration-500"
                    style={{
                      background: read ? heat(v) : '#171a20',
                      outline: current ? `1px solid ${p.color}` : 'none',
                      outlineOffset: 2,
                      opacity: read ? 1 : 0.7,
                    }}
                  />
                )
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex items-center justify-between font-mono text-[10px] uppercase tracking-widest text-bone-700">
        <span>Segment 1</span>
        <span className="hidden sm:inline">← each persona only sees what came before →</span>
        <span>Segment 12</span>
      </div>
    </figure>
  )
}
