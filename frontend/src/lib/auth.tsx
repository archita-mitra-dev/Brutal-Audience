import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, setUnauthorizedHandler, tokenStore, type User } from './api'

interface AuthState {
  user: User | null
  loading: boolean               // true while we check a saved token on first load
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName: string) => Promise<void>
  logout: () => void
  deleteAccount: () => Promise<void>
}

const Ctx = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(() => tokenStore.get() !== null)

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
    return () => setUnauthorizedHandler(null)
  }, [])

  // Restore the session from a saved token.
  useEffect(() => {
    if (!tokenStore.get()) return
    let alive = true
    api.me()
      .then((u) => alive && setUser(u))
      .catch(() => { /* 401 already cleared the token; a network error just leaves us logged out */ })
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const r = await api.login(email, password)
    tokenStore.set(r.access_token); setUser(r.user)
  }, [])

  const register = useCallback(async (email: string, password: string, displayName: string) => {
    const r = await api.register(email, password, displayName)
    tokenStore.set(r.access_token); setUser(r.user)
  }, [])

  const logout = useCallback(() => { tokenStore.clear(); setUser(null) }, [])

  const deleteAccount = useCallback(async () => {
    await api.deleteAccount()
    tokenStore.clear(); setUser(null)
  }, [])

  const value = useMemo(() => ({ user, loading, login, register, logout, deleteAccount }), [user, loading, login, register, logout, deleteAccount])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth(): AuthState {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAuth must be used inside <AuthProvider>')
  return v
}
