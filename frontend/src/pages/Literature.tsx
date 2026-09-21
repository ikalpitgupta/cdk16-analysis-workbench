import { useEffect, useMemo, useState } from 'react'
import { ExternalLink, Search } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '../api/client'

interface Article {
  pmid: string; title: string; journal: string; pubdate: string; authors: string[]
}

export default function Literature() {
  const [arts, setArts] = useState<Article[] | null>(null)
  const [q, setQ] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api.get<{ articles: Article[] }>('/literature').then(r => setArts(r.articles)).catch(e => setError(String(e)))
  }, [])

  const filtered = useMemo(() => {
    if (!arts) return []
    if (!q) return arts
    const s = q.toLowerCase()
    return arts.filter(a => a.title.toLowerCase().includes(s) || a.pmid.includes(s))
  }, [arts, q])

  const timeline = useMemo(() => {
    if (!arts) return []
    const years: Record<string, number> = {}
    arts.forEach(a => {
      const y = a.pubdate.match(/\d{4}/)?.[0]
      if (y) years[y] = (years[y] ?? 0) + 1
    })
    return Object.entries(years).sort().map(([year, count]) => ({ year, count }))
  }, [arts])

  if (error) return <div className="notice notice-coral">{error}</div>
  if (!arts) return <div className="state"><div className="spinner" /> Loading literature…</div>

  return (
    <div>
      <h1 className="section-title">CDK16 Literature</h1>
      <p className="section-sub">{arts.length} PubMed articles retrieved via E-utilities for CDK16/PCTAIRE1/PCTK1 queries.</p>

      {timeline.length > 0 && (
        <div className="card mb-2">
          <div className="section-title" style={{ fontSize: 14 }}>Publication timeline</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={timeline}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
              <XAxis dataKey="year" tick={{ fontSize: 9, fill: 'var(--text-3)' }} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-3)' }} allowDecimals={false} />
              <Tooltip contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)' }} />
              <Bar dataKey="count" fill="#22d3ee" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div style={{ position: 'relative', maxWidth: 420, marginBottom: 14 }}>
        <Search size={14} style={{ position: 'absolute', left: 11, top: 11, color: 'var(--text-3)' }} />
        <input className="input" placeholder="Search title or PMID…" value={q} onChange={e => setQ(e.target.value)} style={{ paddingLeft: 32 }} />
      </div>

      {filtered.length === 0 && <div className="state">No articles match the search.</div>}
      {filtered.slice(0, 50).map(a => (
        <div key={a.pmid} className="card card-hover mb-2" style={{ padding: '12px 16px' }}>
          <div className="row-between">
            <div style={{ fontSize: 13.5, fontWeight: 600 }}>{a.title}</div>
            <a href={`https://pubmed.ncbi.nlm.nih.gov/${a.pmid}/`} target="_blank" rel="noreferrer" className="btn" style={{ padding: '4px 8px', flexShrink: 0 }}>
              <ExternalLink size={13} /> PMID {a.pmid}
            </a>
          </div>
          <div className="muted mt-1">{a.authors.slice(0, 3).join(', ')}{a.authors.length > 3 ? ' et al.' : ''} · {a.journal} · {a.pubdate}</div>
        </div>
      ))}
    </div>
  )
}
