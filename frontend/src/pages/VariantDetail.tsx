import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'

const fmt = (v: unknown, d = 3) =>
  v === null || v === undefined || v === '' ? '—' : typeof v === 'number' ? v.toFixed(d) : String(v)

export default function VariantDetail() {
  const { uid } = useParams()
  const [v, setV] = useState<Record<string, any> | null>(null)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/variants/${encodeURIComponent(uid ?? '')}`)
      .then(async r => {
        if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `HTTP ${r.status}`)
        return r.json()
      })
      .then(d => setV(d.variant))
      .catch(e => setErr(String(e.message ?? e)))
      .finally(() => setLoading(false))
  }, [uid])

  if (loading)
    return (
      <div className="page flex items-center gap-2 muted">
        <Loader2 size={18} className="spin" /> Retrieving variant evidence…
      </div>
    )

  if (err || !v)
    return (
      <div className="page">
        <div className="notice notice-amber">
          Variant “{uid}” could not be retrieved. {err}
        </div>
        <Link className="btn mt-2" to="/variants"><ArrowLeft size={14} /> Back to Variant Explorer</Link>
      </div>
    )

  const ev: Array<[string, number | null]> = [
    ['Clinical', v.ev_clinical],
    ['Computational', v.ev_computational],
    ['Conservation', v.ev_conservation],
    ['Structural', v.ev_structural],
    ['Domain', v.ev_domain],
    ['Literature', v.ev_literature],
    ['Cross-database', v.ev_cross_db],
  ]

  return (
    <div className="page">
      <Link className="btn mb-2" to="/variants"><ArrowLeft size={14} /> Variant Explorer</Link>

      <div className="card">
        <div className="row-between">
          <div>
            <h1 className="mono" style={{ fontSize: 26, margin: 0 }}>
              {v.aa_change ? `p.${v.aa_change}` : v.variant_uid}
            </h1>
            <div className="muted" style={{ fontSize: 13 }}>
              {v.hgvs_protein || '—'} · {v.hgvs_transcript || 'transcript unknown'}
            </div>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <span className="badge badge-cyan">{v.variant_class}</span>
            <span className="badge badge-violet">priority {fmt(v.priority_score, 1)}</span>
            {v.am_pathogenicity_class && (
              <span className={`badge ${v.am_pathogenicity_class === 'PATHOGENIC' ? 'badge-amber' : ''}`}>
                AM {v.am_pathogenicity_class.toLowerCase()} {fmt(v.am_pathogenicity_score, 2)}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="grid-2 mt-2">
        <div className="card">
          <div className="section-title">Identity</div>
          <table className="kv">
            <tbody>
              <tr><td className="muted">Variant UID</td><td className="mono">{v.variant_uid}</td></tr>
              <tr><td className="muted">Source</td><td>{v.source}</td></tr>
              <tr><td className="muted">dbSNP</td><td className="mono">{v.rsid ?? '—'}</td></tr>
              <tr><td className="muted">ClinVar</td><td className="mono">{v.clinvar_id ? `VCV${String(v.clinvar_id).split('.')[0]}` : '—'}</td></tr>
              <tr><td className="muted">Transcript</td><td className="mono">{v.transcript_id || '—'}</td></tr>
              <tr><td className="muted">Protein position</td><td className="mono">{fmt(v.protein_position, 0)}</td></tr>
              <tr><td className="muted">Amino-acid change</td><td className="mono">{v.aa_change || '—'}</td></tr>
              <tr><td className="muted">Location (GRCh38)</td><td className="mono">{v.chromosome ? `${v.chromosome}:${fmt(v.genomic_position, 0)}` : '—'}</td></tr>
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="section-title">Clinical evidence <span className="muted" style={{ fontWeight: 400 }}>(reported classification)</span></div>
          {v.clinical_significance ? (
            <table className="kv">
              <tbody>
                <tr><td className="muted">Significance</td><td>{v.clinical_significance}</td></tr>
                <tr><td className="muted">Review status</td><td>{v.review_status || '—'}</td></tr>
                <tr><td className="muted">Condition</td><td>{v.condition || '—'}</td></tr>
              </tbody>
            </table>
          ) : (
            <p className="muted">No ClinVar record matched this variant.</p>
          )}
          <div className="section-title mt-2">Computational evidence</div>
          <table className="kv">
            <tbody>
              <tr><td className="muted">AlphaMissense</td><td className="mono">{fmt(v.am_pathogenicity_score, 3)} ({v.am_pathogenicity_class ?? 'n/a'})</td></tr>
              <tr><td className="muted">SIFT</td><td className="mono">{fmt(v.sift_score, 3)} ({v.sift_prediction ?? 'n/a'})</td></tr>
              <tr><td className="muted">PolyPhen</td><td className="mono">{fmt(v.polyphen_score, 3)} ({v.polyphen_prediction ?? 'n/a'})</td></tr>
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="section-title">Conservation &amp; protein context</div>
          <table className="kv">
            <tbody>
              <tr><td className="muted">Conservation score</td><td className="mono">{fmt(v.conservation_score, 2)}</td></tr>
              <tr><td className="muted">Species sharing residue</td><td className="mono">{fmt(v.n_species_shared, 0)}</td></tr>
              <tr><td className="muted">Domain</td><td>{v.domain_name ?? '—'}</td></tr>
              <tr><td className="muted">Functional site</td><td>{v.landmark_type === 'none' ? '—' : v.landmark_type ?? '—'}</td></tr>
            </tbody>
          </table>
          <Link className="btn mt-2" to={`/structure?variant=${encodeURIComponent(v.variant_uid)}`}>
            View residue in 3D structure
          </Link>
        </div>

        <div className="card">
          <div className="section-title">Evidence profile <span className="muted" style={{ fontWeight: 400 }}>(0–1 per category)</span></div>
          {ev.map(([k, val]) => (
            <div key={k} className="mb-1">
              <div className="row-between" style={{ fontSize: 12.5 }}>
                <span>{k}</span><span className="mono">{fmt(val, 2)}</span>
              </div>
              <div className="meter"><div className="meter-fill" style={{ width: `${Math.round((Number(val) || 0) * 100)}%` }} /></div>
            </div>
          ))}
          <p className="muted mt-2" style={{ fontSize: 12 }}>
            Heuristic evidence-availability summary used for prioritization — not a probability of pathogenicity.
          </p>
        </div>
      </div>
    </div>
  )
}
