import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Play, RotateCcw, SlidersHorizontal } from 'lucide-react'
import { api } from '../api/client'
import type { AnalysisSession } from '../api/client'

interface Draft {
  name: string
  description: string
  variant_type: string
  domain: string
  min_conservation: number
  am_class: string
  min_am_score: number
  landmark: string
  limit: number
}

const DEFAULT: Draft = {
  name: 'CDK16 variant analysis',
  description: '',
  variant_type: 'all',
  domain: 'all',
  min_conservation: 0,
  am_class: 'all',
  min_am_score: 0,
  landmark: 'all',
  limit: 5000,
}

function toConstraints(d: Draft): Record<string, unknown> {
  const c: Record<string, unknown> = { limit: d.limit }
  if (d.variant_type !== 'all') c.variant_type = [d.variant_type]
  if (d.domain !== 'all') c.domain = [d.domain]
  if (d.am_class !== 'all') c.am_class = [d.am_class]
  if (d.landmark !== 'all') c.landmark = [d.landmark]
  if (d.min_conservation > 0) c.min_conservation = d.min_conservation
  if (d.min_am_score > 0) c.min_am_score = d.min_am_score
  return c
}

export default function AnalysisBuilder() {
  const [d, setD] = useState<Draft>(DEFAULT)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const nav = useNavigate()
  const set = (k: keyof Draft) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setD(p => ({ ...p, [k]: e.target.type === 'number' ? Number(e.target.value) : e.target.value }))

  const constraints = useMemo(() => toConstraints(d), [d])

  const chips = useMemo(() => {
    const out: [string, string][] = []
    if (d.variant_type !== 'all') out.push(['Variant type', d.variant_type])
    if (d.domain !== 'all') out.push(['Domain', d.domain])
    if (d.am_class !== 'all') out.push(['Prediction class', d.am_class])
    if (d.landmark !== 'all') out.push(['Functional site', d.landmark])
    if (d.min_conservation > 0) out.push(['Conservation ≥', String(d.min_conservation)])
    if (d.min_am_score > 0) out.push(['AM score ≥', String(d.min_am_score)])
    out.push(['Result cap', String(d.limit)])
    return out
  }, [d])

  const run = async () => {
    setBusy(true)
    setError('')
    try {
      const s = await api.post<AnalysisSession>('/analyses', {
        name: d.name || 'CDK16 variant analysis',
        description: d.description,
        constraints,
      })
      await api.post(`/analyses/${s.id}/run`)
      nav(`/analysis/${s.id}/run`)
    } catch (e) {
      setError(String(e))
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="page-head">
        <div className="ph-ic tint-violet"><SlidersHorizontal size={22} /></div>
        <div>
          <h1 className="section-title">Analysis Builder</h1>
          <p className="section-sub">
            Configure the analysis. All constraints are validated and executed server-side on the processed CDK16 dataset.
          </p>
        </div>
      </div>

      <div className="grid-2" style={{ gridTemplateColumns: 'minmax(0, 1.15fr) minmax(300px, 0.85fr)', alignItems: 'start' }}>
        <div className="card">
          <label className="lbl">Analysis name</label>
          <input className="input" value={d.name} onChange={set('name')} maxLength={120} />
          <label className="lbl mt-2">Description (optional)</label>
          <input className="input" value={d.description} onChange={set('description')} placeholder="e.g. Kinase-domain variants under strong conservation" />

          <div className="form-grid mt-3">
            <div>
              <label className="lbl">Variant type</label>
              <select className="select" value={d.variant_type} onChange={set('variant_type')}>
                {['all', 'missense', 'synonymous', 'nonsense', 'frameshift', 'splice', 'start_lost', 'stop_lost', 'other'].map(v => (
                  <option key={v} value={v}>{v === 'all' ? 'All types' : v.replace('_', ' ')}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="lbl">Protein domain</label>
              <select className="select" value={d.domain} onChange={set('domain')}>
                <option value="all">All domains</option>
                <option value="kinase">Kinase domain</option>
                <option value="none">Outside annotated domains</option>
              </select>
            </div>
            <div>
              <label className="lbl">Min conservation (0–1)</label>
              <input className="input" type="number" min={0} max={1} step={0.05} value={d.min_conservation} onChange={set('min_conservation')} />
            </div>
            <div>
              <label className="lbl">Prediction class</label>
              <select className="select" value={d.am_class} onChange={set('am_class')}>
                {['all', 'pathogenic', 'likely_pathogenic', 'ambiguous', 'likely_benign', 'benign'].map(v => (
                  <option key={v} value={v}>{v === 'all' ? 'Any prediction' : v.replace('_', ' ')}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="lbl">Min AM score (0–1)</label>
              <input className="input" type="number" min={0} max={1} step={0.05} value={d.min_am_score} onChange={set('min_am_score')} />
            </div>
            <div>
              <label className="lbl">Functional site</label>
              <select className="select" value={d.landmark} onChange={set('landmark')}>
                {['all', 'active_site', 'binding_site', 'modified_residue', 'none'].map(v => (
                  <option key={v} value={v}>{v === 'all' ? 'Any location' : v.replace('_', ' ')}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="lbl">Result cap</label>
              <input className="input" type="number" min={1} max={20000} value={d.limit} onChange={set('limit')} />
            </div>
          </div>
        </div>

        <div>
          <div className="card">
            <div className="section-title" style={{ fontSize: 15 }}>Current Analysis Definition</div>
            <p className="muted mt-1">
              {d.variant_type === 'all' ? 'All' : d.variant_type.replace('_', ' ')} variants
              {d.domain !== 'all' && <> in the {d.domain} domain</>}
              {d.min_conservation > 0 && <> with conservation ≥ {d.min_conservation}</>}
              {d.am_class !== 'all' && <> predicted {d.am_class.replace('_', ' ')}</>}
              {d.landmark !== 'all' && <> at a {d.landmark.replace('_', ' ')}</>}
              {d.min_am_score > 0 && <> with AM score ≥ {d.min_am_score}</>}
              {d.variant_type === 'all' && d.domain === 'all' && d.min_conservation === 0 && d.am_class === 'all' && d.landmark === 'all' && d.min_am_score === 0 && <> (no filters)</>}.
            </p>
            <div className="row" style={{ flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
              {chips.map(([k, v]) => (
                <span className="chip" key={k}>{k}: {v}</span>
              ))}
            </div>
            <div className="row mt-3">
              <button className="btn btn-grad" onClick={run} disabled={busy}>
                <Play size={15} /> {busy ? 'Creating analysis…' : 'Run Analysis'}
              </button>
              <button className="btn" onClick={() => setD(DEFAULT)} disabled={busy}>
                <RotateCcw size={14} /> Reset
              </button>
            </div>
            {error && <div className="notice notice-coral mt-2">{error}</div>}
            <p className="muted mt-2">
              The analysis runs on the backend against the processed dataset; this page only submits the configuration.
            </p>
          </div>
          <div className="notice notice-info mt-2">
            Constraint changes always create a new analysis run — previous runs and reports are preserved for comparison.
          </div>
        </div>
      </div>
    </div>
  )
}
