import { useEffect, useState } from 'react'
import { api, ApiError, TERMINAL, type RunDetail } from './api'

/** Polls a run until it reaches a terminal state. Reactions stream in as they are stored. */
export function useRun(runId: string | undefined) {
  const [run, setRun] = useState<RunDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) return
    let alive = true
    let timer: ReturnType<typeof setTimeout> | undefined

    const tick = async () => {
      try {
        const r = await api.getRun(runId)
        if (!alive) return
        setRun(r)
        setError(null)
        if (!TERMINAL.includes(r.status)) timer = setTimeout(tick, 900)
      } catch (e) {
        if (!alive) return
        if (e instanceof ApiError && e.status === 404) {
          setError('This run no longer exists.')
          return // don't keep polling a missing run
        }
        setError(e instanceof ApiError ? e.message : 'Lost contact with the server.')
        timer = setTimeout(tick, 2500)
      }
    }
    tick()
    return () => { alive = false; if (timer) clearTimeout(timer) }
  }, [runId])

  return { run, error }
}
