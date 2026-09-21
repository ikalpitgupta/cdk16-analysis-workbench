import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Download, Search, Dna } from 'lucide-react'
import { api } from '../api/client'
import type { VariantPage } from '../api/client'

function fmt(v: unknown, d = 3): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(d)
  return String(v)
}

export default function Variants() {
  const [searchParams] = useSearchParams()
  const nav = useNavigate()
  const [data, setData] = useState<VariantPage | null>(null)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState(() => searchParams.get('q') ?? '')
  const [vclass, setVclass] = useState('all')
  const [amClass, setAmClass] = useState('all')
  const [minCons, setMinCons] = useState(0)
  const [sortBy, setSortBy] = useState('priority_score')
  const [sortDesc, setSortDesc] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    const q = new URLSearchParams({
      page: String(page), page_size: '50', search,
      variant_class: vclass, am_class: amClass,
      min_conservation: String(minCons), sort_by: sortBy,
      sort_desc: String(sortDesc),
    })
    api.get<VariantPage>(`/variants?${q}`).then(setData).catch(e => setError(String(e)))
  }, [page, search, vclass, amClass, minCons, sortBy, sortDesc])

  useEffect(() => {
    const t = setTimeout(load, 250)
    return () => clearTimeout(t)
  }, [load])

  const th = (label: string, key?: string, wrap = false) => (
    <th className={wrap ? 'wrap' : undefined}
      onClick={key ? () => { setSortBy(key); setSortDesc(sortBy === key ? !sortDesc : true) } : undefined}>
      {label}{key && sortBy === key ? <span className="th-sort">{sortDesc ? ' ↓' : ' ↑'}</span> : ''}
    </th>
  )

  const csv = () => {
    if (!data) return
    const head = 'variant_uid,aa_change,protein_position,variant_class,domain,landmark,am_score,am_class,conservation,priority'
    const lines = data.variants.map(v =>
      [v.variant_uid, v.aa_change, v.protein_position, v.variant_class, v.domain_name,
       v.landmark_type, v.am_pathogenicity_score, v.am_pathogenicity_class,
       v.conservation_score, v.priority_score].join(','))
    const blob = new Blob([[head, ...lines].join('\n')], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'cdk16_variants.csv'
    a.click()
  }

  return (
    <div>
      <div className="page-head">
        <div className="ph-ic"><Dna size={22} /></div>
        <div>
          <h1 className="section-title">Variant Explorer</h1>
          <p className="section-sub">
            {data ? `${data.total.toLocaleString()} variants match the current filters` : 'Loading…'} ·
            search by rsID, amino-acid change or variant UID.
          </p>
        </div>
      </div>

      <div className="card mb-2">
        <div className="filter-bar">
          <div className="f-search" style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 11, top: 11, color: 'var(--text-3)' }} />
            <input className="input" placeholder="Search rsID / aa change / UID…" value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }} style={{ paddingLeft: 32 }} />
          </div>
          <select className="select" value={vclass} onChange={e => { setVclass(e.target.value); setPage(1) }}>
            <option value="all">All consequences</option>
            {['missense', 'synonymous', 'nonsense', 'frameshift', 'splice', 'other'].map(v => <option key={v} value={v}>{v}</option>)}
          </select>
          <select className="select" value={amClass} onChange={e => { setAmClass(e.target.value); setPage(1) }}>
            <option value="all">Any prediction</option>
            {['pathogenic', 'likely_pathogenic', 'ambiguous', 'likely_benign', 'benign'].map(v => <option key={v} value={v}>{v.replace('_', ' ')}</option>)}
          </select>
          <input className="input" type="number" min={0} max={1} step={0.05}
            placeholder="Min conservation" value={minCons || ''} onChange={e => { setMinCons(Number(e.target.value) || 0); setPage(1) }} />
          <button className="btn f-csv" onClick={csv}><Download size={14} /> CSV</button>
        </div>
      </div>

      {error && <div className="notice notice-coral">{error}</div>}
      {!data && !error && <div className="state"><div className="spinner" /> Loading variants…</div>}
      {data && data.variants.length === 0 && (
        <div className="state">No variants match the current filters. Clear a filter to widen the search.</div>
      )}
      {data && data.variants.length > 0 && (
        <>
          <div className="card table-card">
            <table className="tbl">
              <thead>
                <tr>
                  {th('Variant', 'variant_uid')}{th('AA change', 'aa_change')}{th('Pos.', 'protein_position')}
                  {th('Class', 'variant_class')}{th('Domain', 'domain_name', true)}{th('Site', 'landmark_type')}
                  {th('AM score', 'am_pathogenicity_score')}{th('AM class', 'am_pathogenicity_class')}
                  {th('Conservation', 'conservation_score')}{th('Priority', 'priority_score')}
                </tr>
              </thead>
              <tbody>
                {data.variants.map(v => (
                  <tr key={v.variant_uid} className="row-click" onClick={() => nav(`/variants/${v.variant_uid}`)} style={{ cursor: 'pointer' }}>
                    <td className="mono">{v.variant_uid}</td>
                    <td className="mono">{v.aa_change ?? '—'}</td>
                    <td>{fmt(v.protein_position)}</td>
                    <td><span className="badge badge-cyan">{v.variant_class}</span></td>
                    <td className="muted wrap" style={{ minWidth: 88 }}>{v.domain_name ?? '—'}</td>
                    <td className="muted">{v.landmark_type === 'none' ? '—' : v.landmark_type ?? '—'}</td>
                    <td className="mono">{fmt(v.am_pathogenicity_score)}</td>
                    <td className="muted">{v.am_pathogenicity_class ?? 'n/a'}</td>
                    <td className="mono">{fmt(v.conservation_score, 2)}</td>
                    <td className="mono">{fmt(v.priority_score, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="row-between mt-2">
            <span className="muted">Page {data.page} of {data.pages}</span>
            <div className="row">
              <button className="btn" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
              <button className="btn" disabled={page >= data.pages} onClick={() => setPage(p => p + 1)}>Next →</button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
