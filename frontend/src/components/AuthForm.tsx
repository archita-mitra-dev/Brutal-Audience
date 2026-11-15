import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'

export default function AuthForm({ mode }: { mode: 'login' | 'register' }) {
  const { user, login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/workspace'
  const isRegister = mode === 'register'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (user && !busy) return <Navigate to={from} replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (busy) return
    setBusy(true); setError(null)
    try {
      if (isRegister) await register(email.trim(), password, name.trim())
      else await login(email.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
      setBusy(false)
    }
  }

  return (
    <main className="mx-auto max-w-md px-5 py-16 sm:py-24">
      <p className="eyebrow">{isRegister ? 'Create your lab account' : 'Welcome back'}</p>
      <h1 className="mt-3 font-display text-4xl leading-tight">{isRegister ? 'Get an audience.' : 'Log in.'}</h1>
      <p className="mt-3 text-sm text-bone-500">
        {isRegister
          ? 'Your drafts and results are private to your account, and you can delete them, or the account, at any time.'
          : 'Pick up where you left off.'}
      </p>

      <form onSubmit={submit} className="mt-8 space-y-5" noValidate>
        {isRegister && (
          <div>
            <label htmlFor="name" className="eyebrow">Name <span className="text-bone-700">(optional)</span></label>
            <input id="name" className="field mt-1.5" value={name} maxLength={60} autoComplete="name" onChange={(e) => setName(e.target.value)} />
          </div>
        )}
        <div>
          <label htmlFor="email" className="eyebrow">Email</label>
          <input id="email" type="email" required className="field mt-1.5" value={email} maxLength={254}
            autoComplete="email" inputMode="email" onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <div className="flex items-baseline justify-between">
            <label htmlFor="password" className="eyebrow">Password</label>
            <button type="button" className="font-mono text-[11px] uppercase tracking-wider text-bone-500 hover:text-bone-100" onClick={() => setShow((v) => !v)}>
              {show ? 'Hide' : 'Show'}
            </button>
          </div>
          <input id="password" type={show ? 'text' : 'password'} required className="field mt-1.5" value={password} maxLength={128}
            minLength={isRegister ? 8 : undefined} autoComplete={isRegister ? 'new-password' : 'current-password'}
            aria-describedby={isRegister ? 'pw-hint' : undefined} onChange={(e) => setPassword(e.target.value)} />
          {isRegister && <p id="pw-hint" className="mt-1.5 text-xs text-bone-500">At least 8 characters. A few random words works well.</p>}
        </div>

        {error && <p role="alert" className="rounded-sm border border-persona-doom/50 bg-persona-doom/10 p-3 text-sm text-persona-doom">{error}</p>}

        <button type="submit" className="btn-primary w-full" disabled={busy || !email || !password}>
          {busy ? (isRegister ? 'Creating account…' : 'Logging in…') : (isRegister ? 'Create account →' : 'Log in →')}
        </button>
      </form>

      <p className="mt-8 text-sm text-bone-500">
        {isRegister ? 'Already have an account? ' : 'New here? '}
        <Link to={isRegister ? '/login' : '/register'} state={location.state} className="text-lab underline-offset-4 hover:underline">
          {isRegister ? 'Log in' : 'Create an account'}
        </Link>
      </p>
    </main>
  )
}
