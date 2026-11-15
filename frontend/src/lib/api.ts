// Thin API client. In dev the Vite proxy handles /api; in production set VITE_API_URL.
const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''

// --- session token (kept in localStorage; see README for the trade-off) ---------------
const TOKEN_KEY = 'ba_token'
export const tokenStore = {
  get: () => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } },
  set: (t: string) => { try { localStorage.setItem(TOKEN_KEY, t) } catch { /* storage blocked */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY) } catch { /* storage blocked */ } },
}
let onUnauthorized: (() => void) | null = null
/** Called when the server rejects our token (expired, account deleted). */
export const setUnauthorizedHandler = (fn: (() => void) | null) => { onUnauthorized = fn }

export interface User { id: string; email: string; display_name: string; created_at: string }
export interface AuthResponse { access_token: string; token_type: string; user: User }

export type ContentType = 'story' | 'screenplay' | 'lyrics' | 'article' | 'other'

export interface Segment {
  id: number
  label: string
  text: string
  char_start: number
  char_end: number
  word_count: number
}

export interface SegmentResponse {
  content_type: ContentType
  segments: Segment[]
  total_words: number
  truncated: boolean
}

export interface Submission {
  id: string
  title: string
  content_type: ContentType
  content: string
  created_at: string
  segments: Segment[]
}

export type RunStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
export type RunMode = 'live' | 'demo'

export interface Reaction {
  persona: 'doom' | 'critic' | 'fan' | 'newbie'
  persona_name: string
  segment_id: number
  status: 'ok' | 'failed'
  engagement_score: number | null
  emotion: string | null
  inner_thought: string | null
  would_continue: boolean | null
  evidence: string | null
  evidence_verified: boolean
  reason: string | null
  error: string | null
  attempts: number
  seq: number | null      // arrival order within the run (1 = first reaction stored)
}

export interface Run {
  id: string
  submission_id: string
  mode: RunMode
  model: string
  status: RunStatus
  total_steps: number
  done_steps: number
  error: string | null
  blind: boolean
  baseline_run_id: string | null   // set on revisions and what-if experiments
  kind: 'standard' | 'revision' | 'whatif'
  label: string | null             // the hypothesis, for a what-if
  created_at: string
  finished_at: string | null
}

export interface RunDetail extends Run {
  title: string
  content_type: ContentType
  segments: Segment[]
  reactions: Reaction[]
}

export interface Participant {
  persona: Reaction['persona']
  persona_name: string
  score: number
  emotion: string | null
  inner_thought: string | null
  reason: string | null
  evidence: string | null
  would_continue: boolean | null
}

export interface SegmentStat {
  segment_id: number
  label: string
  read_by: number
  mean: number | null
  min: number | null
  max: number | null
  spread: number | null
  scores: Record<string, number>
  stopped: string[]
}

export interface PersonaStat {
  persona: Reaction['persona']
  persona_name: string
  avg: number | null
  n_ok: number
  n_failed: number
  first_stop_segment: number | null
}

export interface DropOff {
  segment_id: number
  label: string
  personas: string[]
  persona_names: string[]
  consensus: boolean
}

export interface Collision {
  segment_id: number
  label: string
  kind: 'score_gap' | 'continue_split'
  spread: number
  high: Participant
  low: Participant
  others: Participant[]
  explanation: string
}

export interface Agreement {
  segment_id: number
  label: string
  kind: 'shared_high' | 'shared_low'
  mean: number
}

export type SegmentLevel = 'strong' | 'curious' | 'declining' | 'multi_stop'
export type DocumentLevel = 'holds' | 'mixed' | 'shaky' | 'brutal'

export interface SegmentMeter {
  segment_id: number
  label: string
  level: SegmentLevel
  name: string
  rule: string
  mean: number
}

export interface DocumentMeter {
  level: DocumentLevel
  name: string
  rule: string
  counts: Record<SegmentLevel, number>
  never_stopped: string[]
  persona_count: number
}

export interface Meter {
  segments: SegmentMeter[]
  document: DocumentMeter | null
  thresholds: Record<string, number>
}

export type DropState = 'continue' | 'drop_off' | 'already_left' | 'unread'
export interface DropoffRow { segment_id: number; label: string; states: Record<string, DropState> }
export interface CurvePoint { segment_id: number; label: string; still_reading: number; pct: number }
export interface Trigger {
  persona: Reaction['persona']; persona_name: string; segment_id: number; label: string
  sentence: string | null; score: number; inner_thought: string | null; reason: string | null
}
export interface DropoffPrediction {
  reader_count: number; rows: DropoffRow[]; curve: CurvePoint[]; triggers: Trigger[]
  steepest_segment_id: number | null; reached_end: string[]
}

export interface SplitReader { persona: Reaction['persona']; persona_name: string; audience: string; score: number; reason: string | null }
export interface SplitSegment {
  segment_id: number; label: string; gap: number; headline: string; why: string
  appeals_to: SplitReader[]; loses: SplitReader[]
}
export interface PersonaFit { persona: Reaction['persona']; persona_name: string; audience: string; avg: number; rank: number }
export interface SplitReport {
  segments: SplitSegment[]; fit: PersonaFit[]; work_note: string
  divides: { high: string; low: string; count: number }[]; thresholds: Record<string, number>
}

export interface Analysis {
  run_id: string
  status: RunStatus
  partial: boolean
  overall_mean: number | null
  strongest_segment_id: number | null
  weakest_segment_id: number | null
  segments: SegmentStat[]
  personas: PersonaStat[]
  drop_offs: DropOff[]
  lost_attention: number[]
  collisions: Collision[]
  agreements: Agreement[]
  meter: Meter
  dropoff: DropoffPrediction
  split: SplitReport
}

export interface SegmentNote { segment_id: number; label: string; mean: number | null; why: string }
export interface PersonaTake { persona: Reaction['persona']; persona_name: string; liked: string; disliked: string }
export interface Suggestion {
  title: string
  segment_ids: number[]
  problem: string
  action: string
  evidence: string | null
}
export interface Verdict {
  run_id: string
  mode: RunMode
  model: string
  generated_at: string
  overall: string
  strongest: SegmentNote | null
  weakest: SegmentNote | null
  drop_offs: DropOff[]
  persona_takes: PersonaTake[]
  polarising_note: string | null
  suggestions: Suggestion[]
}

export interface Health {
  status: string
  phase: number
  llm_configured: boolean
  mode_default: RunMode
  provider: string | null
  model: string | null
}

// --- Phase 8: revisions and what-if experiments -------------------------------------------
export interface ChildRun { id: string; kind: 'revision' | 'whatif'; label: string | null; status: RunStatus; created_at: string; finished_at: string | null }
export interface PersonaScore { before: number; after: number; delta: number }
export interface SegmentDelta {
  base_segment_id: number | null
  rev_segment_id: number | null
  base_label: string | null
  rev_label: string | null
  change: 'unchanged' | 'edited' | 'new' | 'removed'
  status: 'improved' | 'weakened' | 'unchanged' | 'new' | 'removed' | 'unrated'
  base_mean: number | null
  rev_mean: number | null
  delta: number | null
  personas: Record<string, PersonaScore>
  collateral: boolean
}
export interface PersonaDelta {
  persona: Reaction['persona']; persona_name: string
  before: number | null; after: number | null; delta: number | null
  status: 'improved' | 'weakened' | 'unchanged' | 'unrated'
}
export interface DropoffOutcome {
  persona: Reaction['persona']; persona_name: string
  status: 'resolved' | 'still' | 'moved' | 'new'
  before_label: string | null; after_label: string | null; text: string
}
export interface Comparison {
  baseline_run_id: string; run_id: string; kind: 'revision' | 'whatif'; label: string | null
  overall_before: number | null; overall_after: number | null; overall_delta: number | null
  verdict: 'better' | 'worse' | 'mixed' | 'about_the_same' | 'unrated'
  meter_before: string | null; meter_after: string | null
  retention_before: number | null; retention_after: number | null
  improved: number; weakened: number; collateral: number
  segments: SegmentDelta[]; personas: PersonaDelta[]; dropoffs: DropoffOutcome[]
  highlights: string[]; noise_note: string
}

export const TERMINAL: RunStatus[] = ['completed', 'failed', 'cancelled']

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  const headers = new Headers(init?.headers)
  const token = tokenStore.get()
  if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers })
  } catch {
    throw new ApiError('Cannot reach the server. Is the backend running on port 8000?', 0)
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
        detail = String(body.detail[0].msg).replace(/^Value error, /, '')   // validation errors
      }
    } catch { /* non-JSON error body */ }
    const isLoginAttempt = path === '/api/auth/login' || path === '/api/auth/register'
    if (res.status === 401 && !isLoginAttempt) { tokenStore.clear(); onUnauthorized?.() }
    throw new ApiError(detail, res.status)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  register: (email: string, password: string, display_name: string) =>
    request<AuthResponse>('/api/auth/register', json({ email, password, display_name })),
  login: (email: string, password: string) =>
    request<AuthResponse>('/api/auth/login', json({ email, password })),
  me: () => request<User>('/api/auth/me'),
  deleteAccount: () => request<void>('/api/auth/me', { method: 'DELETE' }),
  health: () => request<Health>('/api/health'),
  segment: (content: string, content_type: ContentType, signal?: AbortSignal) =>
    request<SegmentResponse>('/api/segment', { ...json({ content, content_type }), signal }),
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<{ filename: string; text: string }>('/api/upload', { method: 'POST', body: form })
  },
  createSubmission: (title: string, content_type: ContentType, content: string) =>
    request<Submission>('/api/submissions', json({ title, content_type, content })),
  startRun: (submissionId: string, mode: 'auto' | 'live' | 'demo' = 'auto', blind = true) =>
    request<Run>(`/api/submissions/${submissionId}/runs`, json({ mode, blind })),
  getRun: (runId: string) => request<RunDetail>(`/api/runs/${runId}`),
  getAnalysis: (runId: string) => request<Analysis>(`/api/runs/${runId}/analysis`),
  getVerdict: (runId: string) => request<Verdict>(`/api/runs/${runId}/verdict`),
  createVerdict: (runId: string) => request<Verdict>(`/api/runs/${runId}/verdict`, { method: 'POST' }),
  getSubmission: (id: string) => request<Submission>(`/api/submissions/${id}`),
  startRevision: (runId: string, content: string, title?: string) =>
    request<Run>(`/api/runs/${runId}/revisions`, json({ content, title })),
  startWhatIf: (runId: string, hypothesis: string, content: string) =>
    request<Run>(`/api/runs/${runId}/whatif`, json({ hypothesis, content })),
  getChildren: (runId: string) => request<ChildRun[]>(`/api/runs/${runId}/children`),
  getComparison: (runId: string) => request<Comparison>(`/api/runs/${runId}/compare`),
  cancelRun: (runId: string) => request<Run>(`/api/runs/${runId}/cancel`, { method: 'POST' }),
}
