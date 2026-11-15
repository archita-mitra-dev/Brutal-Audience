import { Link, Route, Routes } from 'react-router-dom'
import RequireAuth from './components/RequireAuth'
import { useAuth } from './lib/auth'
import Account from './pages/Account'
import Login from './pages/Login'
import Register from './pages/Register'
import Landing from './pages/Landing'
import RunPage from './pages/RunPage'
import Workspace from './pages/Workspace'

function Header() {
  const { user, loading } = useAuth()
  return (
    <header className="sticky top-0 z-30 border-b border-ink-700/70 bg-ink-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3.5">
        <Link to="/" className="flex items-baseline gap-2">
          <span className="font-display text-lg font-semibold tracking-tight">Brutal Audience</span>
          <span className="eyebrow hidden sm:inline">lab / v0.8</span>
        </Link>
        <nav className="flex items-center gap-2 sm:gap-3">
          {loading ? null : user ? (
            <>
              <Link to="/workspace" className="btn-ghost">Test your work</Link>
              <Link to="/account" className="btn-ghost max-w-[9rem] truncate" title={user.email}>{user.display_name}</Link>
            </>
          ) : (
            <>
              <Link to="/login" className="btn-ghost">Log in</Link>
              <Link to="/register" className="btn-primary !px-4 !py-2 !text-xs">Sign up</Link>
            </>
          )}
        </nav>
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
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/account" element={<RequireAuth><Account /></RequireAuth>} />
        <Route path="/workspace" element={<RequireAuth><Workspace /></RequireAuth>} />
        <Route path="/run/:runId" element={<RequireAuth><RunPage /></RequireAuth>} />
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
