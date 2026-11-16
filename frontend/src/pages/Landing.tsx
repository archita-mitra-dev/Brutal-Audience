import { Link } from 'react-router-dom'
import SimulationPreview from '../components/SimulationPreview'
import { PERSONAS } from '../lib/personas'

const STEPS = [
  ['01', 'Submit the draft', 'Paste or upload a story, screenplay, lyrics, or article. It stays exactly as written.'],
  ['02', 'Seat the panel', 'Four distinct readers move through it in order, with no knowledge of the ending.'],
  ['03', 'Find the fracture', 'See the passages that pull attention forward, lose it, or divide the room.'],
  ['04', 'Take a second pass', 'Compare a revision or test a precise hypothetical before you change the work.'],
] as const

export default function Landing() {
  return (
    <main className="landing-shell">
      <section className="landing-hero">
        <div className="landing-kicker">
          <span>Brutal Audience / issue 01</span>
          <span>For writers who want the real notes</span>
        </div>

        <div className="landing-headline">
          <div>
            <p className="eyebrow !text-bone-500">A private reading room</p>
            <h1>Before you send it out,<br /><em>hear the room.</em></h1>
          </div>
          <div className="landing-intro">
            <p>Put a draft in front of a simulated audience and follow their response, passage by passage. No rewrite button. No polite blur. Just an honest reading experience.</p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to="/workspace" className="btn-primary">Run a reading <span aria-hidden>→</span></Link>
              <a href="#method" className="btn-ghost">The method</a>
            </div>
          </div>
        </div>

        <div className="landing-manifesto">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-bone-500">The premise</p>
          <p>Good work deserves a first audience before it meets its permanent one.</p>
          <dl>
            <div><dt>04</dt><dd>reader perspectives</dd></div>
            <div><dt>01</dt><dd>draft, never rewritten</dd></div>
            <div><dt>∞</dt><dd>revisions to examine</dd></div>
          </dl>
        </div>
      </section>

      <section id="method" className="landing-method">
        <div className="landing-section-heading">
          <p className="eyebrow !text-bone-500">The method</p>
          <h2>A reader is not a co-writer.</h2>
        </div>
        <div className="landing-method-copy">
          <p>Most feedback is either too kind, too late, or quietly turns into a rewrite. This is a place to observe a reading, not outsource your voice.</p>
          <p className="text-bone-500">The panel flags its evidence, keeps disagreements visible, and marks every result as a simulation—not measured audience data.</p>
        </div>
      </section>

      <section className="landing-readthrough" aria-labelledby="readthrough-heading">
        <div className="landing-readthrough-copy">
          <p className="eyebrow !text-bone-500">Inside a reading</p>
          <h2 id="readthrough-heading">Attention has a trail.</h2>
          <p>Follow four readings across the same twelve segments. A warm cell marks engagement; the outline marks the passage currently being read.</p>
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-bone-500">Illustration only · not a promise of results</p>
        </div>
        <SimulationPreview />
      </section>

      <section className="landing-steps" aria-labelledby="steps-heading">
        <div className="landing-section-heading">
          <p className="eyebrow !text-bone-500">A complete pass</p>
          <h2 id="steps-heading">Four moves. No theatre.</h2>
        </div>
        <ol>
          {STEPS.map(([number, title, description]) => (
            <li key={number}>
              <span>{number}</span><h3>{title}</h3><p>{description}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="landing-panel" aria-labelledby="panel-heading">
        <div className="landing-section-heading">
          <p className="eyebrow !text-bone-500">The panel</p>
          <h2 id="panel-heading">Four readers, four blind spots.</h2>
        </div>
        <div className="persona-ledger">
          {PERSONAS.map((persona, index) => (
            <article key={persona.key}>
              <span className="persona-index">0{index + 1}</span>
              <span className="persona-mark" style={{ color: persona.color }} aria-hidden>{persona.glyph}</span>
              <div><h3>{persona.name}</h3><p>{persona.tagline}</p></div>
              <p className="persona-watch"><span>Watches for</span>{persona.watchesFor}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-close">
        <p className="eyebrow !text-bone-500">Open the reading room</p>
        <h2>Your work. Their unvarnished attention.</h2>
        <Link to="/workspace" className="btn-primary">Test a draft <span aria-hidden>→</span></Link>
        <p>Simulated reactions are a thinking tool, not a replacement for real readers.</p>
      </section>

      <footer className="landing-footer"><span>Brutal Audience</span><span>Your work stays yours</span><span>© 2026</span></footer>
    </main>
  )
}
