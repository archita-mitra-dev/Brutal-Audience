import type { RunMode } from '../lib/api'

/** Makes it impossible to mistake demo output for real AI feedback. */
export default function ModeBanner({ mode, model }: { mode: RunMode; model: string }) {
  if (mode === 'demo') {
    return (
      <div role="note" className="rounded-sm border border-lab/60 bg-lab/10 p-4">
        <p className="font-mono text-xs font-medium uppercase tracking-widest text-lab">Demo mode · not AI</p>
        <p className="mt-1.5 text-sm text-bone-300">
          These reactions come from simple text statistics (sentence length, dialogue, stock phrases), not from an
          AI audience. Use them to explore the interface only, not as feedback on your work. Add{' '}
          <code className="font-mono text-bone-100">LLM_API_KEY</code> and{' '}
          <code className="font-mono text-bone-100">LLM_MODEL</code> to <code className="font-mono text-bone-100">backend/.env</code> for
          real AI personas.
        </p>
      </div>
    )
  }
  return (
    <p className="font-mono text-[11px] uppercase tracking-widest text-bone-500">
      Live simulation · <span className="text-bone-300">{model}</span> · simulated audience, not real readers
    </p>
  )
}
