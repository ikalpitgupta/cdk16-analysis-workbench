import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Download, Eye, FileText } from 'lucide-react'
import { api } from '../api/client'
import type { ReportMeta } from '../api/client'

export default function ReportsCenter() {
  const [reports, setReports] = useState<ReportMeta[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get<ReportMeta[]>('/reports').then(setReports).catch(e => setError(String(e)))
  }, [])

  return (
    <div>
      <div className="page-head">
        <div className="ph-ic tint-emerald"><FileText size={22} /></div>
        <div>
          <h1 className="section-title">Report Center</h1>
          <p className="section-sub">
            Every generated report is versioned and preserved. Reports marked <i>Outdated</i> were built from a previous analysis configuration.
          </p>
        </div>
      </div>

      {error && <div className="notice notice-coral">{error}</div>}
      {!reports && !error && <div className="state"><div className="spinner" /> Loading reports…</div>}
      {reports && reports.length === 0 && (
        <div className="card">
          <p className="muted" style={{ margin: 0 }}>
            No reports yet. Open an <Link to="/analysis">analysis</Link> and generate one from its Results page.
          </p>
        </div>
      )}
      {reports && reports.length > 0 && (
        <div className="card table-card">
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th style={{ minWidth: 160 }}>Report</th>
                  <th style={{ minWidth: 180 }}>Analysis</th>
                  <th style={{ minWidth: 100 }}>Section</th>
                  <th style={{ minWidth: 80 }}>Version</th>
                  <th style={{ minWidth: 100 }}>Status</th>
                  <th style={{ minWidth: 170, whiteSpace: 'nowrap' }}>Created</th>
                  <th style={{ minWidth: 260, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
            <tbody>
              {reports.map(r => (
                <tr key={r.id}>
                  <td className="mono">{r.id}</td>
                  <td>{r.analysis_name ?? r.session_id}</td>
                  <td>{r.section}</td>
                  <td>v{r.version}</td>
                  <td>
                    <span className={`badge ${r.status === 'CURRENT' ? 'badge-emerald' : r.status === 'OUTDATED' ? 'badge-amber' : 'badge-gray'}`}>
                      {r.status}
                    </span>
                  </td>
                  <td className="muted">{new Date(r.created_at).toLocaleString()}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <div className="row" style={{ gap: 6 }}>
                      <Link className="btn btn-primary" to={`/reports/${r.id}`} style={{ textDecoration: 'none', padding: '5px 10px' }} title="View interactive report">
                        <Eye size={14} /> View
                      </Link>
                      <a className="btn" href={`/api/reports/${r.id}/download?format=html`} download={`CDK16_report_${r.id}.html`} style={{ textDecoration: 'none', padding: '5px 10px' }} title="Download HTML report">
                        <Download size={14} /> HTML
                      </a>
                      <a className="btn" href={`/api/reports/${r.id}/download?format=pdf`} download={`CDK16_report_${r.id}.pdf`} style={{ textDecoration: 'none', padding: '5px 10px' }} title="Download PDF document">
                        <Download size={14} /> PDF
                      </a>
                      <a className="btn" href={`/api/reports/${r.id}/download?format=json`} download={`CDK16_report_${r.id}.json`} style={{ textDecoration: 'none', padding: '5px 10px' }} title="Download JSON metadata">
                        JSON
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      )}
    </div>
  )
}
