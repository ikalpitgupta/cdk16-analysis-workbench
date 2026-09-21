import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { api } from '../api/client'
import type { Overview } from '../api/client'

const COLORS = ['#22d3ee', '#a78bfa', '#34d399', '#fbbf24', '#f87171', '#0ea5e9', '#94a3b8']

interface PredData {
  available: boolean
  n_scored?: number
  mean?: number
  median?: number
  by_class?: Record<string, number>
  histogram?: { bin: number; count: number }[]
  source?: string
}

export default function AnalysisCharts() {
  const [ov, setOv] = useState<Overview | null>(null)
  const [pred, setPred] = useState<PredData | null>(null)
  const [cons, setCons] = useState<{ scores: (number | null)[] } | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get<Overview>('/overview').then(setOv).catch(e => setError(String(e)))
    api.get<PredData>('/predictions').then(setPred).catch(() => {})
    api.get<{ scores: (number | null)[] }>('/conservation').then(setCons).catch(() => {})
  }, [])

  if (error) return <div className="notice notice-coral">{error}</div>
  if (!ov) return <div className="state"><div className="spinner" /> Loading analytics…</div>

  const byClass = Object.entries(ov.variants.by_class).map(([k, v]) => ({ name: k, value: v }))
  const tipStyle = { background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)' }

  const consHist = (() => {
    if (!cons?.scores) return []
    const vals = cons.scores.filter((x): x is number => x !== null)
    const bins = new Array(10).fill(0)
    vals.forEach(v => bins[Math.min(9, Math.floor(v * 10))]++)
    return bins.map((count, i) => ({ bin: (i / 10).toFixed(1), count }))
  })()

  return (
    <div>
      <h1 className="section-title">Analysis Charts</h1>
      <p className="section-sub">Distributions computed from the full processed dataset ({ov.variants.total.toLocaleString()} variants).</p>

      <div className="grid-2">
        <div className="card">
          <div className="section-title" style={{ fontSize: 14 }}>Variant consequence classes</div>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={byClass}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--text-3)' }} />
              <YAxis scale="log" domain={['auto', 'auto']} tick={{ fontSize: 10, fill: 'var(--text-3)' }} allowDecimals={false} />
              <Tooltip contentStyle={tipStyle} />
              <Bar dataKey="value" fill="#22d3ee" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <p className="muted">Log scale — dbSNP contributes mostly intronic/regulatory variants.</p>
        </div>

        <div className="card">
          <div className="section-title" style={{ fontSize: 14 }}>Prediction classes (AlphaMissense)</div>
          {pred?.available && pred.by_class ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={Object.entries(pred.by_class).map(([k, v]) => ({ name: k, value: v }))}
                  dataKey="value" nameKey="name" outerRadius={95}>
                  {Object.keys(pred.by_class).map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Tooltip contentStyle={tipStyle} />
              </PieChart>
            </ResponsiveContainer>
          ) : <p className="muted">AlphaMissense predictions not available — documented gap.</p>}
        </div>

        <div className="card">
          <div className="section-title" style={{ fontSize: 14 }}>AlphaMissense score distribution</div>
          {pred?.available && pred.histogram ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={pred.histogram}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis dataKey="bin" tick={{ fontSize: 10, fill: 'var(--text-3)' }} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-3)' }} allowDecimals={false} />
                <Tooltip contentStyle={tipStyle} />
                <Bar dataKey="count" fill="#a78bfa" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="muted">No prediction histogram available.</p>}
          {pred?.available && (
            <p className="muted">n={pred.n_scored?.toLocaleString()} scored · mean {pred.mean} · median {pred.median} · source: {pred.source}</p>
          )}
        </div>

        <div className="card">
          <div className="section-title" style={{ fontSize: 14 }}>Residue conservation distribution</div>
          {consHist.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={consHist}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis dataKey="bin" tick={{ fontSize: 10, fill: 'var(--text-3)' }} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-3)' }} allowDecimals={false} />
                <Tooltip contentStyle={tipStyle} />
                <Bar dataKey="count" fill="#34d399" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="muted">Conservation not computed yet.</p>}
          <p className="muted">{ov.conservation.method}</p>
        </div>
      </div>
    </div>
  )
}
