import { Link } from 'react-router-dom'
import SimulationPreview from '../components/SimulationPreview'
import { PERSONAS } from '../lib/personas'

const STEPS = [
  { n: '01', title: 'Submit your draft', body: 'Paste it or upload a .txt / .docx. It is stored exactly as written — never edited.' },
  { n: '02', title: 'We split it into segments', body: 'Paragraphs, scenes or stanzas — each with an ID and its exact original text. You can inspect them first.' },
  { n: '03', title: 'The audience reads, in order', body: 'Each persona meets one segment at a time and reacts before seeing the next. No peeking at the ending.' },
  { n: '04', title: 'You get the verdict', body: 'A heatmap of attention, where the audience splits, and three specific, evidence-linked notes.' },
]

export default function Landing() {
  return (
    <main>
      {/* HERO */}
      <section className="relative overflow-hidden border-b border-ink-700/70">
        <div className="mx-auto max-w-6xl px-5 pb-20 pt-16 sm:pt-24">
          <p className="eyebrow animate-rise">Creative testing laboratory</p>
          <h1 className="mt-5 max-w-4xl animate-rise font-display text-5xl font-semibold leading-[1.02] tracking-tight [animation-delay:80ms] sm:text-7xl">
            Rehearse your audience <em className="font-normal italic text-lab">before</em> you meet them.
          </h1>
          <p className="mt-7 max-w-2xl animate-rise text-lg leading-relaxed text-bone-300 [animation-delay:160ms]">
            Brutal Audience puts your draft in front of a panel of simulated readers. They react as they go,
            paragraph by paragraph, and tell you where they leaned in, got lost, or walked out.
            <span className="text-bone-100"> They never rewrite a word of it.</span>
          </p>
          <div className="mt-10 flex animate-rise flex-wrap items-center gap-4 [animation-delay:240ms]">
            <Link to="/workspace" className="btn-primary">Test your work →</Link>
            <a href="#how" className="btn-ghost">See how it works</a>
          </div>
        </div>
      </section>

      {/* PROBLEM / SOLUTION */}
      <section className="mx-auto grid max-w-6xl gap-px bg-ink-700/60 px-0 sm:grid-cols-2 sm:px-5 sm:py-0">
        <div className="bg-ink-950 p-7 sm:p-10">
          <p className="eyebrow text-persona-doom">The problem</p>
          <h2 className="mt-3 font-display text-2xl leading-snug">Honest feedback arrives too late — or never.</h2>
          <ul className="mt-5 space-y-3 text-bone-300">
            <li>Friends are kind, so their notes are soft.</li>
            <li>Professional critics show up after you have published.</li>
            <li>Most AI writing tools quietly turn your draft into <em>their</em> draft.</li>
          </ul>
        </div>
        <div className="bg-ink-950 p-7 sm:p-10">
          <p className="eyebrow text-persona-fan">The experiment</p>
          <h2 className="mt-3 font-display text-2xl leading-snug">An audience, not a co-writer.</h2>
          <ul className="mt-5 space-y-3 text-bone-300">
            <li>Four distinct personas read your work progressively, like real people do.</li>
            <li>Every reaction points at the exact passage that caused it.</li>
            <li>Where they disagree is shown, not smoothed over. A divisive draft can still be a good one.</li>
          </ul>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how" className="mx-auto max-w-6xl scroll-mt-16 px-5 py-20">
        <p className="eyebrow">How a test runs</p>
        <h2 className="mt-3 max-w-2xl font-display text-3xl leading-tight sm:text-4xl">
          Watch attention move through your draft.
        </h2>
        <div className="mt-10"><SimulationPreview /></div>

        <ol className="mt-12 grid gap-px bg-ink-700/60 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s) => (
            <li key={s.n} className="bg-ink-950 p-6">
              <span className="font-mono text-xs text-lab">{s.n}</span>
              <h3 className="mt-3 font-display text-lg">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-bone-500">{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* PERSONAS */}
      <section className="border-y border-ink-700/70 bg-ink-900/50">
        <div className="mx-auto max-w-6xl px-5 py-20">
          <p className="eyebrow">The panel</p>
          <h2 className="mt-3 font-display text-3xl sm:text-4xl">Four readers. Four different problems.</h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {PERSONAS.map((p) => (
              <article key={p.key} className="rounded-sm border border-ink-600 bg-ink-900 p-5 transition hover:-translate-y-0.5" style={{ borderTopColor: p.color, borderTopWidth: 2 }}>
                <div className="flex items-center gap-2">
                  <span className="text-xl" style={{ color: p.color }} aria-hidden>{p.glyph}</span>
                  <h3 className="font-display text-lg">{p.name}</h3>
                </div>
                <p className="mt-3 text-sm italic text-bone-300">{p.tagline}</p>
                <p className="mt-4 font-mono text-[11px] uppercase tracking-wider text-bone-500">Watches for</p>
                <p className="mt-1 text-sm text-bone-300">{p.watchesFor}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* PRINCIPLE + CTA */}
      <section className="mx-auto max-w-4xl px-5 py-24 text-center">
        <p className="font-display text-2xl italic leading-snug text-bone-300 sm:text-3xl">
          “It does not create the art. It helps creators understand the people who experience it.”
        </p>
        <p className="mx-auto mt-6 max-w-xl text-sm text-bone-500">
          Simulated personas are an informed guess, not a guarantee. Treat scores as a conversation starter, not a measurement.
        </p>
        <Link to="/workspace" className="btn-primary mt-10">Test your work →</Link>
      </section>

      <footer className="border-t border-ink-700/70 py-8 text-center font-mono text-[11px] uppercase tracking-widest text-bone-700">
        Brutal Audience · your work stays yours
      </footer>
    </main>
  )
}
