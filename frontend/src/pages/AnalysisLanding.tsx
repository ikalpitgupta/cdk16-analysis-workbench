import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FlaskConical, Plus, Clock, ChevronRight, Activity, CheckCircle2, FileText, Boxes } from 'lucide-react'
import { api } from '../api/client'
import type { AnalysisSession } from '../api/client'

const STATUS_BADGE: Record<string, string> = {
  COMPLETED: 'badge-emerald', RUNNING: 'badge-cyan', FAILED: 'badge-coral',
  OUTDATED: 'badge-amber', CREATED: 'badge-gray',
}

/* Compact human-readable constraint summary, e.g. "missense · kinase · AM ≥ 0.9" */
function constraintSummary(c: Record<string, unknown> | undefined): string {
  if (!c || Object.keys(c).length === 0) return 'no filters'
  const parts: string[] = []
  const vt = c.variant_type as string[] | undefined
  if (vt?.length) parts.push(vt.join(', '))
  const dom = c.domain as string[] | undefined
  if (dom?.length) parts.push(dom.join(', ') + ' domain')
  if (typeof c.min_conservation === 'number') parts.push(`conservation ≥ ${c.min_conservation}`)
  const am = c.am_class as string[] | undefined
  if (am?.length) parts.push(`AM: ${am.join(', ')}`)
  if (typeof c.min_am_score === 'number') parts.push(`AM score ≥ ${c.min_am_score}`)
  const lm = c.landmark as string[] | undefined
  if (lm?.length) parts.push(`site: ${lm.join(', ')}`)
  if (typeof c.limit === 'number') parts.push(`cap ${c.limit.toLocaleString()}`)
  return parts.length ? parts.join(' · ') : 'no filters'
}

export default function AnalysisLanding() {
  const [sessions, setSessions] = useState<AnalysisSession[] | null>(null)
  const [reportsCount, setReportsCount] = useState<number | null>(null)
  const [error, setError] = useState('')
  const nav = useNavigate()

  useEffect(() => {
    api.get<AnalysisSession[]>('/analyses').then(setSessions).catch(e => setError(String(e)))
    api.get<unknown[]>('/reports').then(r => setReportsCount(r.length)).catch(() => {})
  }, [])

  const constraintTypes = new Set<string>()
  for (const s of sessions ?? []) {
    for (const k of Object.keys(s.constraints ?? {})) constraintTypes.add(k)
  }
  const constraintVariants = sessions ? constraintTypes.size : null

  const completed = sessions?.filter(s => s.status === 'COMPLETED').length ?? 0
  const running = sessions?.filter(s => s.status === 'RUNNING').length ?? 0

  return (
    <div>
      <div className="page-head">
        <div className="ph-ic tint-violet"><FlaskConical size={22} /></div>
        <div>
          <h1 className="section-title">CDK16 Analysis Workbench</h1>
          <p className="section-sub">
            Define constraints, run a reproducible CDK16 variant analysis, and generate a complete scientific report.
          </p>
        </div>
      </div>

      <div className="stat-row">
        <div className="stat">
          <span className="ic tint-violet"><Activity size={18} /></span>
          <span><div className="sv">{sessions?.length ?? '—'}</div><div className="sl">Analyses created</div></span>
        </div>
        <div className="stat">
          <span className="ic tint-emerald"><CheckCircle2 size={18} /></span>
          <span><div className="sv">{completed}</div><div className="sl">Completed</div></span>
        </div>
        <div className="stat">
          <span className="ic tint-blue"><Clock size={18} /></span>
          <span><div className="sv">{running}</div><div className="sl">Running</div></span>
        </div>
        <div className="stat">
          <span className="ic tint-cyan"><FileText size={18} /></span>
          <span><div className="sv">{reportsCount ?? '—'}</div><div className="sl">Reports generated</div></span>
        </div>
        <div className="stat">
          <span className="ic tint-violet"><Boxes size={18} /></span>
          <span><div className="sv">{constraintVariants ?? '—'}</div><div className="sl">Constraint types</div></span>
        </div>
      </div>

      <div className="row" style={{ flexWrap: 'wrap', gap: 10 }}>
        <Link to="/analysis/new" className="btn btn-grad" style={{ textDecoration: 'none' }}>
          <Plus size={16} /> New Analysis
        </Link>
        <a className="btn" href="#history" onClick={e => { e.preventDefault(); document.getElementById('history')?.scrollIntoView({ behavior: 'smooth' }) }}>
          <Clock size={15} /> Previous Analyses
        </a>
        <Link className="btn" to="/reports" style={{ textDecoration: 'none' }}>
          <FlaskConical size={15} /> View Reports
        </Link>
      </div>

      <h2 className="section-title mt-4" style={{ fontSize: 15 }} id="history">Previous Analyses</h2>
      {error && <div className="notice notice-coral">{error}</div>}
      {!sessions && !error && (
        <div className="state"><div className="spinner" /> Loading analyses…</div>
      )}
      {sessions && sessions.length === 0 && (
        <div className="card">
          <p className="muted" style={{ margin: 0 }}>
            No analyses yet. Click <b>New Analysis</b> to configure and run your first CDK16 analysis.
          </p>
        </div>
      )}
      {sessions && sessions.length > 0 && (
        <div className="card table-card">
          <table className="tbl">
            <thead>
              <tr>
                <th>Analysis</th><th>Status</th><th>Constraints</th><th>Created</th><th></th>
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => (
                <tr key={s.id} className="clickable" onClick={() => nav(s.has_results ? `/analysis/${s.id}/results` : `/analysis/${s.id}/run`)}>
                  <td>
                    <div style={{ color: 'var(--text)', fontWeight: 600 }}>{s.name}</div>
                    <div className="mono muted">{s.id}</div>
                  </td>
                  <td><span className={`badge ${STATUS_BADGE[s.status] ?? 'badge-gray'}`}>{s.status}</span></td>
                  <td className="muted" style={{ maxWidth: 260 }}>{constraintSummary(s.constraints)}</td>
                  <td className="muted">{new Date(s.created_at).toLocaleString()}</td>
                  <td><ChevronRight size={15} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
