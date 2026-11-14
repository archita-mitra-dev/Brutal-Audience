// Thin API client. In dev the Vite proxy handles /api; in production set VITE_API_URL.
const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''

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

export const TERMINAL: RunStatus[] = ['completed', 'failed', 'cancelled']

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, init)
  } catch {
    throw new ApiError('Cannot reach the server. Is the backend running on port 8000?', 0)
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch { /* non-JSON error body */ }
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
  startRun: (submissionId: string, mode: 'auto' | 'live' | 'demo' = 'auto') =>
    request<Run>(`/api/submissions/${submissionId}/runs`, json({ mode })),
  getRun: (runId: string) => request<RunDetail>(`/api/runs/${runId}`),
  getAnalysis: (runId: string) => request<Analysis>(`/api/runs/${runId}/analysis`),
  getVerdict: (runId: string) => request<Verdict>(`/api/runs/${runId}/verdict`),
  createVerdict: (runId: string) => request<Verdict>(`/api/runs/${runId}/verdict`, { method: 'POST' }),
  cancelRun: (runId: string) => request<Run>(`/api/runs/${runId}/cancel`, { method: 'POST' }),
}
