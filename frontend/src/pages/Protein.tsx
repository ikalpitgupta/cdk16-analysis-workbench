import { useEffect, useState } from 'react'
import { api } from '../api/client'

interface ProteinData {
  accession: string; name: string; gene: string; organism: string; length: number
  sequence: string; mw_kda: number
  domains: { type: string; start: number; end: number; description: string }[]
  landmarks: { type: string; position: number; residue: string; description: string }[]
  interactions: { partner: string; partner_accession: string; experiments: number; evidence_type: string }[]
  features: { type: string; start: number; end: number; description: string }[]
  uniprot_version: string
}

const LM_COLOR: Record<string, string> = {
  active_site: 'var(--coral)', binding_site: 'var(--amber)', modified_residue: 'var(--violet)',
}

export default function Protein() {
  const [p, setP] = useState<ProteinData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get<ProteinData>('/protein').then(setP).catch(e => setError(String(e)))
  }, [])

  if (error) return <div className="notice notice-coral">{error}</div>
  if (!p) return <div className="state"><div className="spinner" /> Loading protein reference…</div>

  const len = p.length
  const posStyle = (s: number, e: number) => ({
    left: `${(s / len) * 100}%`,
    width: `${Math.max(0.4, ((e - s + 1) / len) * 100)}%`,
  })

  return (
    <div>
      <h1 className="section-title">CDK16 Protein Reference</h1>
      <p className="section-sub">
        UniProt {p.accession} · {p.name} · {p.organism} · {p.length} aa · entry v{p.uniprot_version}
      </p>

      <div className="metric-row">
        <div className="metric"><div className="v">{p.length}</div><div className="l">Amino acids</div></div>
        <div className="metric"><div className="v">{p.mw_kda}</div><div className="l">Mass (kDa)</div></div>
        <div className="metric"><div className="v">{p.domains.length}</div><div className="l">Domains/regions</div></div>
        <div className="metric"><div className="v">{p.landmarks.length}</div><div className="l">Functional residues</div></div>
        <div className="metric"><div className="v">{p.interactions.length}</div><div className="l">Interactors</div></div>
      </div>

      <div className="card mt-3">
        <div className="section-title" style={{ fontSize: 15 }}>Domain architecture (1 – {len} aa)</div>
        <div style={{ position: 'relative', height: 44, background: 'var(--surface-2)', borderRadius: 8, marginTop: 14, border: '1px solid var(--border)' }}>
          {p.domains.map((d, i) => (
            <div key={i} title={`${d.description} (${d.start}–${d.end})`}
              style={{
                ...posStyle(d.start, d.end), top: 6, height: 32,
                background: 'linear-gradient(180deg, rgba(34,211,238,.55), rgba(14,165,233,.45))',
                borderRadius: 5, position: 'absolute', border: '1px solid rgba(34,211,238,.5)',
              }} />
          ))}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-3)', marginTop: 4 }}>
          <span>1</span><span>125</span><span>250</span><span>375</span><span>{len}</span>
        </div>
        <div className="mt-2">
          {p.domains.map((d, i) => (
            <div key={i} className="row" style={{ gap: 8, fontSize: 12.5, padding: '3px 0' }}>
              <span className="badge badge-cyan">{d.type}</span>
              <span className="mono">{d.start}–{d.end}</span>
              <span className="muted">{d.description}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card mt-3">
        <div className="section-title" style={{ fontSize: 15 }}>Functional landmark residues (UniProt-annotated)</div>
        <p className="muted mt-1">Positions used for structural distance context and the evidence model. Hover for details.</p>
        <div style={{ position: 'relative', height: 40, background: 'var(--surface-2)', borderRadius: 8, marginTop: 10, border: '1px solid var(--border)' }}>
          {p.landmarks.map((l, i) => (
            <div key={i} title={`${l.type.replace('_', ' ')} · ${l.residue}${l.position}`}
              style={{
                position: 'absolute', left: `${(l.position / len) * 100}%`, top: 8,
                width: 8, height: 24, borderRadius: 2,
                background: LM_COLOR[l.type] ?? 'var(--text-3)',
                transform: 'translateX(-50%)',
              }} />
          ))}
        </div>
        <div className="row mt-2" style={{ gap: 12, fontSize: 12 }}>
          <span><span style={{ color: 'var(--coral)' }}>■</span> active site</span>
          <span><span style={{ color: 'var(--amber)' }}>■</span> binding site</span>
          <span><span style={{ color: 'var(--violet)' }}>■</span> modified residue</span>
        </div>
        <div className="tbl-wrap mt-2" style={{ maxHeight: 260, overflowY: 'auto' }}>
          <table className="tbl">
            <thead><tr><th>Position</th><th>Residue</th><th>Type</th><th>Annotation</th></tr></thead>
            <tbody>
              {p.landmarks.map((l, i) => (
                <tr key={i}>
                  <td className="mono">{l.position}</td>
                  <td className="mono">{l.residue}</td>
                  <td><span className="badge badge-gray">{l.type.replace('_', ' ')}</span></td>
                  <td className="muted">{l.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card mt-3">
        <div className="section-title" style={{ fontSize: 15 }}>Interaction partners (UniProt)</div>
        {p.interactions.length === 0 ? <p className="muted">No interaction annotations retrieved.</p> : (
          <div className="tbl-wrap mt-2">
            <table className="tbl">
              <thead><tr><th>Partner</th><th>Accession</th><th>Experiments</th><th>Evidence</th></tr></thead>
              <tbody>
                {p.interactions.map((it, i) => (
                  <tr key={i}>
                    <td style={{ color: 'var(--text)' }}>{it.partner}</td>
                    <td className="mono">{it.partner_accession}</td>
                    <td>{it.experiments}</td>
                    <td><span className={`badge ${it.evidence_type === 'experimental' ? 'badge-emerald' : 'badge-gray'}`}>{it.evidence_type.replace('_', ' ')}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
