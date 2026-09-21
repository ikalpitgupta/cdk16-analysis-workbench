import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { BarChart3, FileBarChart, FileText, Loader2 } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { api } from '../api/client'
import type { AnalysisResult, ReportMeta, Variant } from '../api/client'

const COLORS = ['#22d3ee', '#a78bfa', '#34d399', '#fbbf24', '#f87171', '#0ea5e9', '#94a3b8']

const SECTION_LABELS: { key: string; label: string }[] = [
  { key: 'full', label: 'Full report' },
  { key: 'variants', label: 'Variants' },
  { key: 'predictions', label: 'Predictions' },
  { key: 'conservation', label: 'Conservation' },
  { key: 'structure', label: 'Structure' },
  { key: 'ranking', label: 'Ranking' },
]

function fmt(v: unknown, digits = 3): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(digits)
  return String(v)
}

export default function AnalysisResults() {
  const { sid } = useParams()
  const nav = useNavigate()
  const [res, setRes] = useState<AnalysisResult | null>(null)
  const [tab, setTab] = useState<'overview' | 'variants' | 'ranking' | 'reports'>('overview')
  const [reports, setReports] = useState<ReportMeta[]>([])
  const [generating, setGenerating] = useState('')
  const [error, setError] = useState('')

  const loadReports = () => api.get<ReportMeta[]>(`/analyses/${sid}/reports`).then(setReports).catch(() => {})

  useEffect(() => {
    if (!sid) return
    api.get<AnalysisResult>(`/analyses/${sid}/results`)
      .then(r => {
        if (!r.available) { setError('No results yet — run the analysis first'); return }
        setRes(r)
      })
      .catch(e => setError(String(e)))
    loadReports()
  }, [sid])

  const genReport = async (section: string) => {
    setGenerating(section)
    setError('')
    try {
      await api.post<ReportMeta>(`/analyses/${sid}/reports`, { section })
      await loadReports()
    } catch (e) {
      setError(String(e))
    }
    setGenerating('')
  }

  if (error && !res) {
    const offline = /failed to fetch|networkerror|load failed/i.test(error)
    return (
      <div>
        <div className="notice notice-amber">
          {offline
            ? 'Backend unreachable — the analysis API did not respond. Start it with: python -m uvicorn api.server:app --port 8000, then retry.'
            : error}
        </div>
        <div className="row mt-2">
          <Link className="btn" to="/analysis">← All Analyses</Link>
          {offline && <button className="btn btn-primary" onClick={() => location.reload()}>Retry</button>}
        </div>
      </div>
    )
  }
  if (!res) return <div className="state"><div className="spinner" /> Loading analysis results…</div>

  const s = res.summary
  const byClass = Object.entries(res.statistics.by_class || {}).map(([k, v]) => ({ name: k, value: v }))
  const byDomain = Object.entries(res.statistics.by_domain || {}).map(([k, v]) => ({ name: k, value: v }))
  const ctxChips: string[] = [
    `${s.n_matched.toLocaleString()} variants selected`,
    String(res.constraints.variant_type ?? 'all types'),
    String(res.constraints.domain ?? 'all domains'),
    res.constraints.min_conservation ? `conservation ≥ ${res.constraints.min_conservation}` : 'no conservation filter',
  ]

  return (
    <div>
      <div className="results-header">
        <div className="rh-title">
          <div className="page-head" style={{ marginBottom: 0 }}>
            <div className="ph-ic tint-violet"><BarChart3 size={22} /></div>
            <div>
              <h1 className="section-title">{res.analysis_name}</h1>
              <p className="section-sub mono">{res.analysis_id} · run {res.run_number} · status {res.session_status}</p>
            </div>
          </div>
        </div>
        <div className="rh-actions">
          <Link className="btn" to="/analysis/new">Edit Constraints (new run)</Link>
          <button className="btn btn-grad" onClick={() => genReport('full')} disabled={generating !== ''}>
            {generating === 'full' ? <Loader2 size={15} className="spin" /> : <FileBarChart size={15} />}
            Generate Complete Report
          </button>
        </div>
      </div>

      <div className="chip-row">
        {ctxChips.map(c => <span className="chip" key={c}>{c}</span>)}
      </div>

      {res.warnings?.length > 0 && (
        <div className="notice notice-amber mb-2">
          {res.warnings.map(w => <div key={w}>⚠ {w}</div>)}
        </div>
      )}

      <div className="tabbar">
        {(['overview', 'variants', 'ranking', 'reports'] as const).map(t => (
          <button key={t} className={`tabbar-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <>
          <div className="metric-row cols-4">
            <div className="metric"><div className="v">{s.n_available.toLocaleString()}</div><div className="l">Available</div></div>
            <div className="metric"><div className="v">{s.n_matched.toLocaleString()}</div><div className="l">Matched constraints</div></div>
            <div className="metric"><div className="v">{s.n_returned.toLocaleString()}</div><div className="l">Returned</div></div>
            <div className="metric"><div className="v">{Object.keys(res.statistics.by_am_class || {}).length}</div><div className="l">Prediction classes</div></div>
          </div>

          {s.zero_results && (
            <div className="notice notice-info mt-2">
              No variants matched the current analysis constraints. Relax a filter and run a new analysis.
            </div>
          )}

          <div className="grid-2 mt-3">
            <div className="card">
              <div className="section-title" style={{ fontSize: 14 }}>Consequence classes</div>
              {byClass.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie data={byClass} dataKey="value" nameKey="name" outerRadius={90} label={false}>
                      {byClass.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Tooltip contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)' }} />
                  </PieChart>
                </ResponsiveContainer>
              ) : <p className="muted">No data for this selection.</p>}
            </div>
            <div className="card">
              <div className="section-title" style={{ fontSize: 14 }}>Domain distribution</div>
              {byDomain.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={byDomain.slice(0, 8)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                    <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--text-3)' }} />
                    <YAxis tick={{ fontSize: 10, fill: 'var(--text-3)' }} allowDecimals={false} />
                    <Tooltip contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)' }} />
                    <Bar dataKey="value" fill="#22d3ee" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <p className="muted">No domain annotations in this selection.</p>}
            </div>
          </div>
        </>
      )}

      {tab === 'variants' && (
        <div className="tbl-wrap wide">
          <table className="tbl">
            <thead>
              <tr><th>Variant</th><th>AA</th><th>Pos.</th><th>Class</th><th>Domain</th><th>Site</th><th>AM</th><th>Cons.</th><th>Priority</th></tr>
            </thead>
            <tbody>
              {res.variants.slice(0, 100).map((v: Variant) => (
                <tr key={v.variant_uid} className="row-click" style={{ cursor: 'pointer' }}
                  onClick={() => nav(`/variants/${v.variant_uid}`)}>
                  <td className="mono">{v.variant_uid}</td>
                  <td className="mono">{v.aa_change ?? '—'}</td>
                  <td>{fmt(v.protein_position)}</td>
                  <td><span className="badge badge-cyan">{v.variant_class}</span></td>
                  <td className="muted">{v.domain_name ?? '—'}</td>
                  <td className="muted">{v.landmark_type === 'none' ? '—' : v.landmark_type ?? '—'}</td>
                  <td className="mono">{fmt(v.am_pathogenicity_score)}</td>
                  <td className="mono">{fmt(v.conservation_score, 2)}</td>
                  <td className="mono">{fmt(v.priority_score, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'ranking' && (
        <div className="tbl-wrap wide">
          <table className="tbl">
            <thead>
              <tr><th>#</th><th>Variant</th><th>Position</th><th>Domain</th><th>Site</th><th>AM class</th><th>Cons.</th><th>Priority</th></tr>
            </thead>
            <tbody>
              {res.top_variants.map((v, i) => (
                <tr key={v.variant_uid}>
                  <td>{i + 1}</td>
                  <td className="mono">{v.aa_change || v.variant_uid}</td>
                  <td>{fmt(v.protein_position)}</td>
                  <td className="muted">{v.domain_name ?? '—'}</td>
                  <td className="muted">{v.landmark_type === 'none' ? '—' : v.landmark_type ?? '—'}</td>
                  <td><span className={`badge ${v.am_pathogenicity_class?.includes('pathogenic') ? 'badge-coral' : 'badge-gray'}`}>{v.am_pathogenicity_class ?? 'n/a'}</span></td>
                  <td className="mono">{fmt(v.conservation_score, 2)}</td>
                  <td className="mono">{fmt(v.priority_score, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted mt-1">Ranking uses the documented CEPS evidence heuristic — a research prioritization, not a clinical score.</p>
        </div>
      )}

      {tab === 'reports' && (
        <div>
          <div className="card mb-2">
            <div className="section-title" style={{ fontSize: 14 }}>Section reports</div>
            <p className="muted">Each section report is generated from this exact analysis result and stored as a new version.</p>
            <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
              {SECTION_LABELS.map(sec => {
                const existing = reports.filter(r => r.section === sec.key)
                const latest = existing[existing.length - 1]
                return (
                  <div key={sec.key} className="row" style={{ gap: 6 }}>
                    <button className="btn" onClick={() => genReport(sec.key)} disabled={generating !== ''}>
                      {generating === sec.key ? <Loader2 size={14} className="spin" /> : <FileText size={14} />}
                      {sec.label}
                    </button>
                    {latest && (
                      <Link className="btn" to={`/reports/${latest.id}`} style={{ textDecoration: 'none' }}>
                        v{latest.version} ↗
                      </Link>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
          {reports.length > 0 && (
            <div className="tbl-wrap wide">
              <table className="tbl">
                <thead><tr><th>Report</th><th>Section</th><th>Version</th><th>Status</th><th>Created</th><th></th></tr></thead>
                <tbody>
                  {reports.map(r => (
                    <tr key={r.id}>
                      <td className="mono">{r.id}</td>
                      <td>{r.section}</td>
                      <td>v{r.version}</td>
                      <td><span className={`badge ${r.status === 'CURRENT' ? 'badge-emerald' : 'badge-amber'}`}>{r.status}</span></td>
                      <td className="muted">{new Date(r.created_at).toLocaleString()}</td>
                      <td><Link to={`/reports/${r.id}`}>View</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {error && <div className="notice notice-coral mt-2">{error}</div>}
    </div>
  )
}
