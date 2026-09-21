import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Download, ExternalLink, FileText } from 'lucide-react'
import { api } from '../api/client'
import type { ReportMeta } from '../api/client'

export default function ReportViewer() {
  const { rid } = useParams()
  const [meta, setMeta] = useState<ReportMeta | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!rid) return
    api.get<ReportMeta>(`/reports/${rid}`).then(setMeta).catch(e => setError(String(e)))
  }, [rid])

  if (error) return <div className="notice notice-coral">{error}</div>
  if (!meta) return <div className="state"><div className="spinner" /> Loading report…</div>

  return (
    <div>
      <div className="page-head">
        <div className="ph-ic tint-emerald"><FileText size={22} /></div>
        <div style={{ minWidth: 0 }}>
          <h1 className="section-title">{meta.title}</h1>
          <p className="section-sub mono">{meta.id} · {meta.section} · v{meta.version}</p>
        </div>
        <div className="row" style={{ marginLeft: 'auto' }}>
          <a className="btn" href={`/api/reports/${rid}/download?format=html`}>
            <Download size={14} /> HTML
          </a>
          {meta.section === 'full' && (
            <a className="btn" href={`/api/reports/${rid}/download?format=pdf`}>
              <Download size={14} /> PDF
            </a>
          )}
          <a className="btn btn-grad" href={`/api/reports/${rid}/html`} target="_blank" rel="noreferrer">
            <ExternalLink size={14} /> Open standalone
          </a>
        </div>
      </div>

      {meta.status === 'OUTDATED' && (
        <div className="notice notice-amber mb-2">
          This report was generated from a previous analysis configuration. Generate an updated report from the analysis results page.
        </div>
      )}

      <div className="row" style={{ alignItems: 'stretch', gap: 16, flexWrap: 'wrap' }}>
        <div className="card" style={{ width: 260, maxWidth: '100%', flexShrink: 0 }}>
          <div className="section-title" style={{ fontSize: 13 }}>Analysis metadata</div>
          <div className="mt-2" style={{ fontSize: 12.5, lineHeight: 1.8 }}>
            <div><span className="muted">Analysis:</span> <Link to={`/analysis/${meta.session_id}/results`}>{meta.analysis_name ?? meta.session_id}</Link></div>
            <div><span className="muted">Report ID:</span> <span className="mono">{meta.id}</span></div>
            <div><span className="muted">Run:</span> {meta.run_number}</div>
            <div><span className="muted">Constraint hash:</span> <span className="mono">{meta.constraint_hash}</span></div>
            <div><span className="muted">Generated:</span> {new Date(meta.created_at).toLocaleString()}</div>
            <div><span className="muted">Status:</span> <span className={`badge ${meta.status === 'CURRENT' ? 'badge-emerald' : 'badge-amber'}`}>{meta.status}</span></div>
          </div>
        </div>
        <div className="card" style={{ flex: '1 1 320px', minWidth: 'min(100%, 320px)', padding: 0, overflow: 'hidden' }}>
          <iframe
            src={`/api/reports/${rid}/html`}
            title="Report content"
            style={{ width: '100%', height: 'calc(100vh - 230px)', border: 'none', background: '#f4f6fa' }}
          />
        </div>
      </div>
    </div>
  )
}
