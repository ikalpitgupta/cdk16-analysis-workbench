import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react'
import { api } from '../api/client'
import type { AnalysisSession } from '../api/client'

const STAGE_ORDER = [
  'validating', 'loading_data', 'filtering_variants', 'clinical', 'conservation',
  'predictions', 'structure', 'evidence', 'ranking', 'storing_results', 'completed',
]

const STAGE_LABEL: Record<string, string> = {
  validating: 'Validating configuration',
  loading_data: 'Loading CDK16 dataset',
  filtering_variants: 'Filtering variants',
  clinical: 'Processing clinical annotations',
  conservation: 'Applying conservation thresholds',
  predictions: 'Filtering computational predictions',
  structure: 'Processing structural mappings',
  evidence: 'Integrating evidence dimensions',
  ranking: 'Ranking variants',
  storing_results: 'Storing results',
  completed: 'Analysis complete',
}

export default function AnalysisRun() {
  const { sid } = useParams()
  const [sess, setSess] = useState<AnalysisSession | null>(null)
  const [error, setError] = useState('')
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!sid) return
    let cancelled = false

    const poll = async () => {
      try {
        const s = await api.get<AnalysisSession>(`/analyses/${sid}`)
        if (cancelled) return
        setSess(s)
        const st = s.status
        if (st === 'RUNNING' || st === 'CREATED') {
          timer.current = setTimeout(poll, 1200)
        }
      } catch (e) {
        if (!cancelled) setError(String(e))
      }
    }
    poll()
    return () => {
      cancelled = true
      if (timer.current) clearTimeout(timer.current)
    }
  }, [sid])

  if (error) {
    const offline = /failed to fetch|networkerror|load failed/i.test(error)
    return (
      <div>
        <div className="notice notice-amber">
          {offline
            ? 'Backend unreachable — the analysis API did not respond. Start it with: python -m uvicorn api.server:app --port 8000, then retry.'
            : `Failed to load analysis: ${error}`}
        </div>
        <div className="row mt-2">
          <Link className="btn" to="/analysis">← All Analyses</Link>
          {offline && <button className="btn btn-primary" onClick={() => location.reload()}>Retry</button>}
        </div>
      </div>
    )
  }
  if (!sess) return <div className="state"><div className="spinner" /> Loading analysis…</div>

  const run = sess.runs[sess.runs.length - 1]
  const stage = run?.stage ?? ''
  const status = run?.status ?? sess.status
  const idx = STAGE_ORDER.indexOf(stage)

  return (
    <div>
      <div className="page-head">
        <div className="ph-ic tint-cyan"><Loader2 size={22} className="spin" /></div>
        <div>
          <h1 className="section-title">{sess.name}</h1>
          <p className="section-sub mono">{sess.id} · run {run?.run_number ?? 1}</p>
        </div>
      </div>

      <div className="card" style={{ maxWidth: 640 }}>
        <div className="row-between mb-2">
          <span className={`badge ${status === 'COMPLETED' ? 'badge-emerald' : status === 'FAILED' ? 'badge-coral' : 'badge-cyan'}`}>
            {status}
          </span>
          <span className="muted">{run?.message || STAGE_LABEL[stage] || 'Queued'}</span>
        </div>

        {STAGE_ORDER.map((s, i) => {
          const done = status === 'COMPLETED' || (idx >= 0 && i < idx)
          const active = status === 'RUNNING' && i === idx
          return (
            <div key={s} className={`stage ${done ? 'done' : active ? 'active' : ''}`}>
              <span className="icon">
                {done ? <CheckCircle2 size={15} /> : active ? <Loader2 size={15} className="spin" /> : '○'}
              </span>
              {STAGE_LABEL[s]}
            </div>
          )
        })}

        {status === 'FAILED' && (
          <div className="notice notice-coral mt-2">
            <div className="row"><AlertTriangle size={15} /> Analysis failed</div>
            <pre className="mono mt-1" style={{ whiteSpace: 'pre-wrap', fontSize: 11.5 }}>{run?.error}</pre>
            <Link className="btn mt-2" to={`/analysis/${sess.id}/results`}>Back to configuration</Link>
          </div>
        )}

        {status === 'COMPLETED' && (
          <div className="mt-3">
            <div className="notice notice-info">
              Analysis completed successfully — {run?.message}.
            </div>
            <Link className="btn btn-primary mt-2" to={`/analysis/${sess.id}/results`} style={{ textDecoration: 'none' }}>
              View Results →
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
