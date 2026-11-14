import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import SegmentInspector from '../components/SegmentInspector'
import { api, ApiError, type ContentType, type Health, type Segment } from '../lib/api'

const TYPES: { value: ContentType; label: string; hint: string }[] = [
  { value: 'story', label: 'Story', hint: 'Split by paragraph' },
  { value: 'screenplay', label: 'Screenplay', hint: 'Split by scene (INT./EXT.)' },
  { value: 'lyrics', label: 'Lyrics', hint: 'Split by stanza' },
  { value: 'article', label: 'Article', hint: 'Split by paragraph' },
  { value: 'other', label: 'Other', hint: 'Split by section' },
]

export default function Workspace() {
  const [title, setTitle] = useState('')
  const [type, setType] = useState<ContentType>('story')
  const [content, setContent] = useState('')
  const [segments, setSegments] = useState<Segment[]>([])
  const [truncated, setTruncated] = useState(false)
  const [words, setWords] = useState(0)
  const [segLoading, setSegLoading] = useState(false)
  const [segError, setSegError] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const navigate = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)) }, [])

  // Live segmentation: debounce typing, cancel stale requests.
  useEffect(() => {
    if (!content.trim()) {
      setSegments([]); setWords(0); setTruncated(false); setSegError(null); setSegLoading(false)
      return
    }
    const ctrl = new AbortController()
    setSegLoading(true)
    const t = setTimeout(async () => {
      try {
        const res = await api.segment(content, type, ctrl.signal)
        setSegments(res.segments); setWords(res.total_words); setTruncated(res.truncated); setSegError(null)
      } catch (e) {
        if ((e as Error).name === 'AbortError') return
        setSegError(e instanceof ApiError ? e.message : 'Could not segment this text.')
        setSegments([])
      } finally {
        if (!ctrl.signal.aborted) setSegLoading(false)
      }
    }, 450)
    return () => { clearTimeout(t); ctrl.abort() }
  }, [content, type])

  async function onFile(file: File | undefined) {
    if (!file) return
    setUploadError(null)
    try {
      const res = await api.upload(file)
      setContent(res.text)
      if (!title.trim()) setTitle(file.name.replace(/\.[^.]+$/, ''))
    } catch (e) {
      setUploadError(e instanceof ApiError ? e.message : 'Upload failed.')
    } finally {
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function start() {
    setSaving(true); setSaveError(null)
    try {
      const sub = await api.createSubmission(title.trim(), type, content)
      const run = await api.startRun(sub.id, 'auto')
      navigate(`/run/${run.id}`)
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : 'Could not start the simulation.')
      setSaving(false)
    }
  }

  const canStart = title.trim().length > 0 && segments.length > 0 && !segLoading && !segError

  return (
    <main className="mx-auto max-w-6xl px-5 py-10">
      <p className="eyebrow">Step 1 of 3 · Creative workspace</p>
      <h1 className="mt-2 font-display text-3xl sm:text-4xl">Put your work on the table.</h1>
      <p className="mt-2 max-w-2xl text-bone-500">
        Your text is kept exactly as you write it. Nothing here edits, rewrites or “improves” it.
      </p>

      <div className="mt-8 grid gap-8 lg:grid-cols-2">
        {/* LEFT: input */}
        <section aria-labelledby="draft-h" className="space-y-5">
          <h2 id="draft-h" className="sr-only">Your draft</h2>

          <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
            <label className="block">
              <span className="eyebrow">Title</span>
              <input className="field mt-1.5" value={title} maxLength={200} placeholder="e.g. The Dark Lighthouse"
                onChange={(e) => setTitle(e.target.value)} />
            </label>
            <label className="block">
              <span className="eyebrow">Type</span>
              <select className="field mt-1.5 sm:w-44" value={type} onChange={(e) => setType(e.target.value as ContentType)}>
                {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </label>
          </div>
          <p className="-mt-2 font-mono text-[11px] text-bone-700">{TYPES.find((t) => t.value === type)?.hint}</p>

          <div>
            <div className="flex items-end justify-between">
              <label htmlFor="draft" className="eyebrow">Draft</label>
              <div className="flex items-center gap-3">
                <input ref={fileRef} type="file" accept=".txt,.md,.docx" className="sr-only" id="file"
                  onChange={(e) => onFile(e.target.files?.[0])} />
                <label htmlFor="file" className="btn-ghost cursor-pointer">Upload .txt / .docx</label>
                {content && <button type="button" className="btn-ghost" onClick={() => setContent('')}>Clear</button>}
              </div>
            </div>
            <textarea
              id="draft"
              className="field mt-1.5 h-[420px] resize-y font-mono text-[13px] leading-relaxed"
              placeholder="Paste your story, screenplay, lyrics or essay here…"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              spellCheck={false}
            />
            {uploadError && <p role="alert" className="mt-2 text-sm text-persona-doom">{uploadError}</p>}
            <p className="mt-1.5 font-mono text-[11px] text-bone-700">
              {content.length.toLocaleString()} characters · {words.toLocaleString()} words
            </p>
          </div>
        </section>

        {/* RIGHT: segments */}
        <section aria-labelledby="seg-h">
          <div className="mb-3 flex items-baseline justify-between">
            <h2 id="seg-h" className="eyebrow">Step 2 · Segment inspector</h2>
            <span className="font-mono text-xs text-bone-500" aria-live="polite">
              {segLoading ? 'segmenting…' : segments.length ? `${segments.length} segments` : ''}
            </span>
          </div>
          <SegmentInspector segments={segments} loading={segLoading} truncated={truncated} error={segError} />
        </section>
      </div>

      {/* ACTION BAR */}
      <div className="mt-10 border-t border-ink-700 pt-6">
        <div className="flex flex-wrap items-center gap-4">
          <button className="btn-primary" disabled={!canStart || saving} onClick={start}>
            {saving ? 'Seating the audience…' : 'Lock in & start audience →'}
          </button>
          {!title.trim() && segments.length > 0 && <span className="text-sm text-bone-500">Add a title to continue.</span>}
          {saveError && <span role="alert" className="text-sm text-persona-doom">{saveError}</span>}
        </div>
        {health && (
          <p className="mt-3 font-mono text-[11px] uppercase tracking-wider text-bone-700">
            {health.mode_default === 'live'
              ? `Live AI audience · ${health.model}`
              : 'Demo mode · no LLM key configured, reactions will come from text statistics, not AI'}
          </p>
        )}
      </div>
    </main>
  )
}
