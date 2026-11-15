import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'

export default function Account() {
  const { user, logout, deleteAccount } = useAuth()
  const navigate = useNavigate()
  const [confirming, setConfirming] = useState(false)
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (!user) return null

  async function remove() {
    setBusy(true); setError(null)
    try { await deleteAccount(); navigate('/', { replace: true }) }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Could not delete the account.'); setBusy(false) }
  }

  return (
    <main className="mx-auto max-w-xl px-5 py-16">
      <p className="eyebrow">Account</p>
      <h1 className="mt-3 font-display text-4xl">{user.display_name}</h1>
      <dl className="mt-8 space-y-3 text-sm">
        <div className="flex gap-4"><dt className="w-24 text-bone-500">Email</dt><dd>{user.email}</dd></div>
        <div className="flex gap-4"><dt className="w-24 text-bone-500">Joined</dt><dd>{new Date(user.created_at).toLocaleDateString()}</dd></div>
      </dl>
      <button className="btn-ghost mt-8" onClick={() => { logout(); navigate('/', { replace: true }) }}>Log out</button>

      <section className="mt-16 rounded-sm border border-persona-doom/40 p-5">
        <h2 className="font-display text-xl">Delete account</h2>
        <p className="mt-2 text-sm text-bone-500">
          Permanently deletes your account and every draft, simulation, reaction and verdict you have made. This cannot be undone.
        </p>
        {!confirming ? (
          <button className="btn-ghost mt-4 !border-persona-doom/60 !text-persona-doom" onClick={() => setConfirming(true)}>Delete my account…</button>
        ) : (
          <div className="mt-4 space-y-3">
            <label htmlFor="confirm" className="text-sm text-bone-300">Type your email (<span className="font-mono">{user.email}</span>) to confirm</label>
            <input id="confirm" className="field" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
            <div className="flex gap-3">
              <button className="btn-ghost !border-persona-doom/60 !text-persona-doom" disabled={busy || typed.trim().toLowerCase() !== user.email} onClick={remove}>
                {busy ? 'Deleting…' : 'Delete everything'}
              </button>
              <button className="btn-ghost" onClick={() => { setConfirming(false); setTyped('') }}>Cancel</button>
            </div>
            {error && <p role="alert" className="text-sm text-persona-doom">{error}</p>}
          </div>
        )}
      </section>
    </main>
  )
}
