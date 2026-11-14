import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Analysis } from '../lib/api'
import { PERSONAS } from '../lib/personas'

/** Attention over the course of the piece. Click a point to inspect that segment. */
export default function EngagementChart({
  analysis, selectedSegment, onSelect,
}: { analysis: Analysis; selectedSegment: number | null; onSelect: (id: number) => void }) {
  const data = analysis.segments.map((s) => ({
    seg: s.segment_id,
    panel: s.mean,
    ...Object.fromEntries(PERSONAS.map((p) => [p.key, s.scores[p.key] ?? null])),
  }))

  return (
    <div className="h-72 rounded-sm border border-ink-600 bg-ink-900/70 p-3">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 8, right: 12, bottom: 4, left: -18 }}
          onClick={(s: { activeLabel?: string | number } | null) => { if (s?.activeLabel !== undefined) onSelect(Number(s.activeLabel)) }}
        >
          <CartesianGrid stroke="#1b1f26" vertical={false} />
          <XAxis dataKey="seg" tick={{ fill: '#8d8a82', fontSize: 11 }} stroke="#3a414d" label={{ value: 'segment', position: 'insideBottomRight', offset: -2, fill: '#5c5a55', fontSize: 10 }} />
          <YAxis domain={[0, 10]} ticks={[0, 2, 4, 6, 8, 10]} tick={{ fill: '#8d8a82', fontSize: 11 }} stroke="#3a414d" />
          <Tooltip
            contentStyle={{ background: '#0d0f12', border: '1px solid #3a414d', borderRadius: 2, fontSize: 12 }}
            labelFormatter={(l) => `Segment ${l}`}
            formatter={(v) => (typeof v === 'number' ? v.toFixed(1) : '–')}
          />
          <Legend wrapperStyle={{ fontSize: 11, color: '#c9c5ba' }} />
          {selectedSegment !== null && <ReferenceLine x={selectedSegment} stroke="#f5b84a" strokeDasharray="3 3" />}
          {PERSONAS.map((p) => (
            <Line key={p.key} type="monotone" dataKey={p.key} name={p.name.replace('The ', '')} stroke={p.color}
              strokeWidth={1.25} strokeOpacity={0.75} dot={false} connectNulls={false} isAnimationActive={false} />
          ))}
          <Line type="monotone" dataKey="panel" name="Panel avg" stroke="#f2efe8" strokeWidth={2.5} dot={{ r: 2 }} connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
