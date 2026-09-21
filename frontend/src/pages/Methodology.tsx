import { useEffect, useState } from 'react'
import { api } from '../api/client'

interface Meta {
  manifest: Record<string, unknown>
  provenance: { source_database: string; source_url: string; retrieval_timestamp: string; database_version: string; record_id: string; status: string; n_records: string | number }[]
}

const STEPS = [
  { n: '01', t: 'Data Acquisition', i: 'UniProt, NCBI, Ensembl, dbSNP, RCSB PDB, AlphaFold, PubMed', p: 'HTTP retrieval with retries, caching, timestamps, provenance records', o: 'data/raw/* verbatim responses', w: 'Every downstream result is traceable to its source and retrieval time.' },
  { n: '02', t: 'Protein Reference', i: 'UniProt Q00536 record', p: 'Parse features, domains, functional residues, interactions', o: 'cdk16_protein.json (496 aa reference)', w: 'A single canonical reference keeps all positions comparable.' },
  { n: '03', t: 'Variant Retrieval', i: 'dbSNP rsIDs (gene-tagged) + Ensembl VEP', p: 'Batch consequence calculation on the canonical transcript', o: 'Variant rows with HGVS, class, protein position', w: 'Consequences come from Ensembl VEP, not manual curation.' },
  { n: '04', t: 'Normalization', i: 'Raw variant rows', p: 'Deduplicate by stable UID, verify reference residues against sequence', o: 'Master variant table', w: 'Prevents double-counting across sources.' },
  { n: '05', t: 'Domain & Landmark Mapping', i: 'Protein positions', p: 'Intersect positions with domains and UniProt functional residues', o: 'domain_name, landmark_type per variant', w: 'Locates each variant in protein context.' },
  { n: '06', t: 'Conservation', i: 'Reviewed orthologs (mouse, rat, dog, chicken, fish, frog)', p: 'Pairwise BLOSUM62 alignment; similarity-weighted identity fraction per human residue', o: 'conservation_score ∈ [0,1]', w: 'High conservation suggests constraint — not proof of essentiality.' },
  { n: '07', t: 'Computational Predictions', i: 'AlphaMissense per-protein scores; SIFT/PolyPhen via VEP', p: 'Join by protein position and alternate amino acid', o: 'per-variant prediction scores and classes', w: 'Predictions are probabilistic evidence, never clinical proof.' },
  { n: '08', t: 'Evidence Integration', i: 'All annotations', p: 'Documented weighted heuristic (CEPS): clinical, computational, conservation, structural, domain, literature, cross-database', o: 'priority_score 0–100', w: 'Transparent, configurable research prioritization — not a diagnostic model.' },
  { n: '09', t: 'Structural Context', i: 'AlphaFold AF-Q00536-F1 + experimental PDB entries', p: 'Serve mmCIF; residue-level highlighting in 3D viewer', o: 'Interactive structure with variant mapping', w: 'Predicted vs experimental structures are clearly distinguished.' },
  { n: '10', t: 'Analysis & Reporting', i: 'User constraints', p: 'Server-side filtering, statistics, figures, HTML+PDF reports with versioning', o: 'Reproducible analysis runs and reports', w: 'Every number in a report is computed from the stored analysis result.' },
]

const LIMITATIONS = [
  'No ClinVar clinical submissions were available for CDK16 at retrieval time — clinical evidence columns are empty by absence of data, not by negative evidence.',
  'AlphaMissense per-protein coverage may be partial; variants without scores are missing data, not benign.',
  'Conservation is computed from six reviewed orthologs; broader alignments could shift scores.',
  'Structural context relies on the AlphaFold model where experimental structures lack coverage; pLDDT confidence is not experimental validation.',
  'The prioritization score is a transparent heuristic with fixed weights; it is not a validated clinical model.',
  'Consequence annotations reflect Ensembl VEP and dbSNP at retrieval time and may change as sources update.',
]

export default function Methodology() {
  const [meta, setMeta] = useState<Meta | null>(null)
  useEffect(() => { api.get<Meta>('/metadata').then(setMeta).catch(() => {}) }, [])

  return (
    <div>
      <h1 className="section-title">Methodology</h1>
      <p className="section-sub">How the CDK16 Analysis Workbench turns public data into integrated evidence.</p>

      {STEPS.map(s => (
        <div key={s.n} className="card mb-2" style={{ display: 'grid', gridTemplateColumns: '60px 1fr', gap: 14 }}>
          <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--primary)', opacity: 0.75 }}>{s.n}</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15 }}>{s.t}</div>
            <div style={{ fontSize: 13, lineHeight: 1.7, marginTop: 6 }}>
              <div><span className="muted">Input:</span> {s.i}</div>
              <div><span className="muted">Process:</span> {s.p}</div>
              <div><span className="muted">Output:</span> {s.o}</div>
              <div><span className="muted">Why it matters:</span> {s.w}</div>
            </div>
          </div>
        </div>
      ))}

      <div className="card mt-3">
        <div className="section-title" style={{ fontSize: 15 }}>Data sources &amp; provenance</div>
        {meta?.provenance?.length ? (
          <div className="tbl-wrap mt-2">
            <table className="tbl">
              <thead><tr><th>Source</th><th>Record</th><th>Version</th><th>Retrieved</th><th>Status</th><th>Records</th></tr></thead>
              <tbody>
                {meta.provenance.map((r, i) => (
                  <tr key={i}>
                    <td>{r.source_database}</td>
                    <td className="mono">{r.record_id}</td>
                    <td className="muted">{r.database_version}</td>
                    <td className="muted">{r.retrieval_timestamp}</td>
                    <td><span className={`badge ${r.status === 'OK' ? 'badge-emerald' : r.status === 'OK_EMPTY' ? 'badge-amber' : 'badge-coral'}`}>{r.status}</span></td>
                    <td>{r.n_records}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="muted">Provenance records appear after the acquisition pipeline runs.</p>}
      </div>

      <div className="notice notice-amber mt-3">
        <b>Scientific limitations.</b>
        <ul style={{ margin: '8px 0 0', paddingLeft: 20, lineHeight: 1.7 }}>
          {LIMITATIONS.map(l => <li key={l}>{l}</li>)}
        </ul>
      </div>
    </div>
  )
}
