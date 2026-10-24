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
        <div className="row" style={{ marginLeft: 'auto', flexWrap: 'wrap', gap: 8 }}>
          <a className="btn" href={`/api/reports/${rid}/download?format=html`} download={`CDK16_report_${rid}.html`} title="Download HTML report">
            <Download size={14} /> Download HTML
          </a>
          <a className="btn" href={`/api/reports/${rid}/download?format=pdf`} download={`CDK16_report_${rid}.pdf`} title="Download PDF document">
            <Download size={14} /> Download PDF
          </a>
          <a className="btn" href={`/api/reports/${rid}/download?format=json`} download={`CDK16_report_${rid}.json`} title="Download JSON metadata">
            <Download size={14} /> Download JSON
          </a>
          <a className="btn btn-grad" href={`/api/reports/${rid}/html`} target="_blank" rel="noreferrer" title="Open report in standalone browser tab">
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
          <div className="mt-3 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
            <div className="section-title" style={{ fontSize: 13, marginBottom: 8 }}>Download report</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <a className="btn" style={{ justifyContent: 'center' }} href={`/api/reports/${rid}/download?format=html`} download={`CDK16_report_${rid}.html`}>
                <Download size={13} /> HTML Report
              </a>
              <a className="btn" style={{ justifyContent: 'center' }} href={`/api/reports/${rid}/download?format=pdf`} download={`CDK16_report_${rid}.pdf`}>
                <Download size={13} /> PDF Document
              </a>
              <a className="btn" style={{ justifyContent: 'center' }} href={`/api/reports/${rid}/download?format=json`} download={`CDK16_report_${rid}.json`}>
                <Download size={13} /> JSON Metadata
              </a>
            </div>
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
