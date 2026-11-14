import { Link, Route, Routes } from 'react-router-dom'
import Landing from './pages/Landing'
import RunPage from './pages/RunPage'
import Workspace from './pages/Workspace'

function Header() {
  return (
    <header className="sticky top-0 z-30 border-b border-ink-700/70 bg-ink-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3.5">
        <Link to="/" className="flex items-baseline gap-2">
          <span className="font-display text-lg font-semibold tracking-tight">Brutal Audience</span>
          <span className="eyebrow hidden sm:inline">lab / v0.4</span>
        </Link>
        <Link to="/workspace" className="btn-ghost">Test your work</Link>
      </div>
    </header>
  )
}

export default function App() {
  return (
    <>
      <Header />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/workspace" element={<Workspace />} />
        <Route path="/run/:runId" element={<RunPage />} />
        <Route
          path="*"
          element={
            <main className="mx-auto max-w-xl px-5 py-24 text-center">
              <p className="eyebrow">404</p>
              <h1 className="mt-3 font-display text-3xl">Nothing in this room.</h1>
              <Link to="/" className="btn-ghost mt-8">Back to the lab</Link>
            </main>
          }
        />
      </Routes>
    </>
  )
}
