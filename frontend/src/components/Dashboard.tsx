import { useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError, type Analysis, type RunDetail } from '../lib/api'
import CollisionPanel from './CollisionPanel'
import EngagementChart from './EngagementChart'
import Heatmap from './Heatmap'
import SegmentCompare from './SegmentCompare'
import VerdictPanel from './VerdictPanel'

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-sm border border-ink-600 bg-ink-900 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 font-display text-3xl">{value}</p>
      {sub && <p className="mt-1 text-xs text-bone-500">{sub}</p>}
    </div>
  )
}

/** The finished-run view: heatmap, trend, per-segment comparison, collisions and the verdict. */
export default function Dashboard({ run }: { run: RunDetail }) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [segId, setSegId] = useState<number | null>(null)
  const [persona, setPersona] = useState<string | null>(null)
  const compareRef = useRef<HTMLElement>(null)

  useEffect(() => {
    let alive = true
    api.getAnalysis(run.id)
      .then((a) => { if (alive) { setAnalysis(a); setError(null) } })
      .catch((e) => alive && setError(e instanceof ApiError ? e.message : 'Could not load the analysis.'))
    return () => { alive = false }
  }, [run.id])

  // Start on the most interesting segment: the biggest collision, else the weakest, else the first.
  const start = analysis ? (analysis.collisions[0]?.segment_id ?? analysis.weakest_segment_id ?? run.segments[0]?.id ?? null) : null
  const activeSeg = segId ?? start
  const segment = useMemo(() => run.segments.find((s) => s.id === activeSeg) ?? null, [run.segments, activeSeg])

  function select(id: number, p: string | null) {
    setSegId(id); setPersona(p)
  }
  function jump(id: number) {
    select(id, null)
    requestAnimationFrame(() => compareRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  if (error) return <p role="alert" className="mt-8 text-persona-doom">{error}</p>
  if (!analysis) return <p className="eyebrow mt-8 animate-blink">Crunching the reactions…</p>

  const label = (id: number | null) => run.segments.find((s) => s.id === id)?.label ?? '–'
  const stat = (id: number | null) => analysis.segments.find((s) => s.segment_id === id)?.mean

  return (
    <div className="mt-10 space-y-14">
      {analysis.partial && (
        <p role="note" className="rounded-sm border border-ink-500 p-3 text-sm text-bone-500">
          This run did not finish every reaction, so the numbers below cover only what was recorded.
        </p>
      )}

      <section aria-label="Summary" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Panel average" value={analysis.overall_mean === null ? '–' : `${analysis.overall_mean.toFixed(1)}/10`} sub="mean engagement across all reactions" />
        <Stat label="Strongest" value={label(analysis.strongest_segment_id)} sub={stat(analysis.strongest_segment_id) != null ? `panel avg ${stat(analysis.strongest_segment_id)!.toFixed(1)}` : undefined} />
        <Stat label="Weakest" value={label(analysis.weakest_segment_id)} sub={stat(analysis.weakest_segment_id) != null ? `panel avg ${stat(analysis.weakest_segment_id)!.toFixed(1)}` : undefined} />
        <Stat label="Collisions" value={String(analysis.collisions.length)} sub={`${analysis.drop_offs.length} drop-off point${analysis.drop_offs.length === 1 ? '' : 's'}`} />
      </section>

      <section aria-labelledby="heat-h">
        <h2 id="heat-h" className="font-display text-2xl">Engagement heatmap</h2>
        <p className="mt-1 mb-4 max-w-2xl text-sm text-bone-500">Click a cell for one reader’s reaction, or a number at the top for every reader on that segment.</p>
        <Heatmap segments={run.segments} reactions={run.reactions} analysis={analysis} selectedSegment={activeSeg} selectedPersona={persona} onSelect={select} />
        <div className="mt-6"><EngagementChart analysis={analysis} selectedSegment={activeSeg} onSelect={(id) => select(id, null)} /></div>
      </section>

      <section ref={compareRef} aria-labelledby="cmp-h" className="scroll-mt-20">
        <h2 id="cmp-h" className="mb-4 font-display text-2xl">Segment by segment</h2>
        <SegmentCompare segment={segment} reactions={run.reactions} focus={persona} />
      </section>

      <section aria-labelledby="col-h">
        <h2 id="col-h" className="mb-4 font-display text-2xl">Where the audience splits</h2>
        <CollisionPanel analysis={analysis} onJump={jump} />
      </section>

      <section aria-labelledby="ver-h">
        <h2 id="ver-h" className="mb-4 font-display text-2xl">The Brutal Verdict</h2>
        <VerdictPanel runId={run.id} segments={run.segments} onJump={jump} />
      </section>
    </div>
  )
}
