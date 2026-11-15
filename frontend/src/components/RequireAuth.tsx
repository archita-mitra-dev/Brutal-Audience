import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'

/** Renders children only for a logged-in user; otherwise sends them to /login and back afterwards. */
export default function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <main className="mx-auto max-w-xl px-5 py-24 text-center"><p className="eyebrow animate-blink">Checking your session…</p></main>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}
