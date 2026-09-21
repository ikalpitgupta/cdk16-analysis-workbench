import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight, FlaskConical, Dna, Box, AlertTriangle, BookOpen, BarChart3,
  Link2, Sun, FileText, Clock, ArrowUpRight, Wrench,
  Boxes, HelpCircle, Dna as DnaMark, Target, Database, ShieldCheck, Sparkles,
} from 'lucide-react'
import { api } from '../api/client'
import type { AnalysisSession, Overview } from '../api/client'
import { useTheme } from '../theme'

/* Small self-contained 3Dmol hero canvas (loads library lazily once). */
declare global { interface Window { $3Dmol?: any; __molLibPromise?: Promise<void> } }
function loadMolLib(): Promise<void> {
  if (window.$3Dmol) return Promise.resolve()
  if (!window.__molLibPromise) {
    window.__molLibPromise = new Promise((resolve, reject) => {
      const s = document.createElement('script')
      s.src = 'https://3Dmol.org/build/3Dmol-min.js'
      s.onload = () => resolve()
      s.onerror = () => reject(new Error('3Dmol failed to load'))
      document.head.appendChild(s)
    })
  }
  return window.__molLibPromise
}

function HeroProtein() {
  const { theme } = useTheme()
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    let viewer: any = null
    let cancelled = false
    loadMolLib()
      .then(() => fetch('/api/structures/file/AF-Q00536-F1.cif'))
      .then(r => { if (!r.ok) throw new Error('structure unavailable'); return r.text() })
      .then(data => {
        if (cancelled || !window.$3Dmol || !box.current) return
        // Solid per-theme background: WebGL transparency is unreliable in 3Dmol.
        // The elliptical CSS mask on .mol-float fades the edges into the hero.
        const bg = theme === 'light' ? '#eaf0fc' : '#0d1726'
        viewer = window.$3Dmol.createViewer(box.current, { backgroundColor: bg })
        viewer.addModel(data, 'cif')
        // Reference look: blue → violet → teal across the sequence.
        const stops: [number, number, number][] = [[37, 99, 235], [139, 92, 246], [45, 212, 191]]
        const resColor = (resi: number) => {
          const t = Math.min(1, Math.max(0, (resi - 1) / 495))
          const seg = t < 0.5 ? 0 : 1
          const lt = t < 0.5 ? t * 2 : (t - 0.5) * 2
          const c0 = stops[seg], c1 = stops[seg + 1]
          const ch = (i: number) => Math.round(c0[i] + (c1[i] - c0[i]) * lt).toString(16).padStart(2, '0')
          return `#${ch(0)}${ch(1)}${ch(2)}`
        }
        viewer.setStyle({}, { cartoon: { colorfunc: (a: any) => resColor(a.resi || 1), opacity: 0.95, thickness: 1.1 } })
        viewer.setViewStyle({ style: 'outline' })
        viewer.zoomTo()
        viewer.zoom(1.9)
        // Respect the in-app Animations toggle for the auto-spin.
        const motionOff = document.documentElement.getAttribute('data-motion') === 'off'
        if (!motionOff) viewer.spin('y', 0.5)
        viewer.render()
      })
      .catch(() => {})
    return () => { cancelled = true; try { viewer?.clear(); } catch { /* noop */ } }
  }, [theme])
  return <div ref={box} className="hero-protein" aria-hidden />
}

/* Tiny inline sparkline — pure SVG polyline, no chart library. */
function Spark({ data, up = true, color }: { data?: number[]; up?: boolean; color?: string }) {
  const path = useMemo(() => {
    if (!data || data.length < 2) return null
    const w = 64, h = 20, pad = 1
    const min = Math.min(...data), max = Math.max(...data)
    const span = max - min || 1
    const pts = data.map((v, i) => {
      const x = pad + (i / (data.length - 1)) * (w - 2 * pad)
      const y = pad + (1 - (v - min) / span) * (h - 2 * pad)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    return pts.join(' ')
  }, [data])
  if (!path) return <span className="spark spark-empty" />
  const stroke = color ?? (up ? '#10b981' : '#f87171')
  return (
    <svg className="spark" width="64" height="20" viewBox="0 0 64 20" aria-hidden>
      <polyline points={path} fill="none" stroke={stroke} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

/* Delta label computed from the real spark series (first → last), or a
   neutral static note when no series exists. Never a fabricated %. */
function Delta({ data, neutral }: { data?: number[]; neutral?: string }) {
  if (neutral) return <span className="m-delta neutral">{neutral}</span>
  if (!data || data.length < 2) return <span className="m-delta neutral">—</span>
  const first = data[0], last = data[data.length - 1]
  if (first === last) return <span className="m-delta neutral">stable</span>
  const pct = Math.round(((last - first) / (first || 1)) * 100)
  const up = last > first
  return (
    <span className={`m-delta ${up ? 'up' : 'down'}`}>
      {up ? '↑' : '↓'} {Math.abs(pct)}%
    </span>
  )
}

const METRICS = [
  { key: 'total', label: 'Total Variants', tint: 'tint-blue', icon: DnaMark },
  { key: 'missense', label: 'Missense', tint: 'tint-emerald', icon: BarChart3 },
  { key: 'pred', label: 'With Predictions', tint: 'tint-violet', icon: Sun },
  { key: 'homologs', label: 'Homologs', tint: 'tint-amber', icon: Link2 },
  { key: 'pdb', label: 'PDB Structures', tint: 'tint-coral', icon: Box },
  { key: 'lit', label: 'Literature', tint: 'tint-cyan', icon: BookOpen },
] as const

/* Trust chips under the hero CTAs (reference: Trusted Databases / Reproducible Reports / …) */
const TRUST = [
  { icon: Database, label: 'Trusted Databases', tint: 'c-emerald' },
  { icon: FileText, label: 'Reproducible Reports', tint: 'c-blue' },
  { icon: Sparkles, label: 'Multi-evidence Insights', tint: 'c-violet' },
  { icon: ShieldCheck, label: 'Research Ready', tint: 'c-cyan' },
] as const

const TOOLS = [
  { to: '/variants', title: 'Variant Effect Prediction', sub: 'AlphaMissense scores', tint: 'tint-blue', icon: FileText },
  { to: '/structure', title: '3D Structure Visualization', sub: 'PDB & AlphaFold', tint: 'tint-violet', icon: Boxes },
  { to: '/analysis-charts', title: 'Evolutionary Conservation', sub: 'Multi-species alignment', tint: 'tint-emerald', icon: HelpCircle },
  { to: '/literature', title: 'Literature Mining', sub: 'PubMed integration', tint: 'tint-amber', icon: BookOpen },
]

function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime()
  const m = Math.floor(ms / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m} minute${m === 1 ? '' : 's'} ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} hour${h === 1 ? '' : 's'} ago`
  const d = Math.floor(h / 24)
  return `${d} day${d === 1 ? '' : 's'} ago`
}

interface LiteArticle { pmid: string; title: string; journal: string; pubdate: string }

export default function Dashboard() {
  const [ov, setOv] = useState<Overview | null>(null)
  const [sessions, setSessions] = useState<AnalysisSession[]>([])
  const [lits, setLits] = useState<LiteArticle[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    api.get<Overview>('/overview').then(setOv).catch(e => setError(String(e)))
    api.get<AnalysisSession[]>('/analyses').then(s => setSessions(s.slice(0, 3))).catch(() => {})
    api.get<{ count: number; articles: LiteArticle[] }>('/literature?page=1&page_size=3')
      .then(r => setLits(r.articles.slice(0, 3))).catch(() => {})
  }, [])

  const vals: Record<string, { v: string; sub?: string; neutral?: boolean; spark?: number[] }> = ov ? {
    total: { v: ov.variants.total.toLocaleString(), sub: `${ov.variants.by_class['other'] ?? 0} annotated as other`, spark: ov.spark?.total },
    missense: { v: ov.variants.missense.toLocaleString(), sub: `${ov.variants.with_predictions} scored by AM`, spark: ov.spark?.missense },
    pred: { v: ov.variants.with_predictions.toLocaleString(), sub: 'AlphaMissense coverage', spark: ov.spark?.pred },
    homologs: { v: String(ov.conservation.n_homologs), sub: 'orthologs aligned', neutral: true, spark: ov.spark?.homologs },
    pdb: { v: String(ov.structures.experimental.length), sub: `+ ${ov.structures.alphafold} predicted`, neutral: true, spark: ov.spark?.pdb },
    lit: { v: String(ov.literature_count), sub: 'PubMed articles', spark: ov.spark?.lit },
  } : {}

  return (
    <div>
      <div className="hero">
        <div className="hero-copy">
          <div className="hero-eyebrow">Explore · Analyze · Visualize · Discover</div>
          <h1>
            <span>CDK16 Analysis</span>
            <span className="grad">Workbench</span>
          </h1>
          <p className="lead">
            Integrates genetic, protein, clinical, computational, evolutionary and
            structural evidence for CDK16 variants — define an analysis, run it on real
            retrieved data, and generate a reproducible scientific report.
          </p>
          <div className="row" style={{ flexWrap: 'wrap', gap: 12 }}>
            <Link className="btn btn-cta" to="/analysis/new" style={{ textDecoration: 'none' }}>
              <FlaskConical size={16} /> Start New Analysis <ArrowRight size={15} />
            </Link>
            <Link className="btn btn-light" to="/variants" style={{ textDecoration: 'none' }}>
              <Dna size={15} /> Explore Variants
            </Link>
          </div>
          <div className="trust-row">
            {TRUST.map(({ icon: Icon, label, tint }) => (
              <span className="trust-chip" key={label}>
                <span className={`hf-ic ${tint}`}><Icon size={14} /></span>
                {label}
              </span>
            ))}
          </div>
        </div>

        <div className="hero-stage" aria-hidden>
          <div className="mol-float"><HeroProtein /></div>
          <span className="bokeh b1" />
          <span className="bokeh b2" />
          <span className="bokeh b3" />
          <div className="fact-card fc-id">
            <div className="fc-name"><span className="dot" /> CDK16</div>
            <div className="fc-sub mono">496 aa</div>
          </div>
          <div className="fact-card fc-struct">
            <span className="fc-ic c-blue"><Box size={15} /></span>
            <span><span className="fc-t1">3D Structure</span><br /><span className="fc-t2">Available</span></span>
          </div>
          <div className="fact-card fc-site">
            <span className="fc-ic c-coral"><Target size={15} /></span>
            <span><span className="fc-t1">Active Site</span><br /><span className="fc-t2">Predicted</span></span>
          </div>
          <div className="hero-script">Proteins<br /><em>Power</em><br />Progress</div>
        </div>
      </div>

      {error && (
        <div className="notice notice-coral mt-2">
          <div className="row"><AlertTriangle size={15} /> Backend data unavailable: {error}</div>
        </div>
      )}

      {ov && (
        <>
          <div className="metric-row mt-3">
            {METRICS.map(({ key, label, tint, icon: Icon }, i) => (
              <div className={`metric reveal ${tint}`} key={key} style={{ '--rd': `${0.05 + i * 0.06}s` } as React.CSSProperties}>
                <div className={`ic ${tint}`}><Icon size={18} /></div>
                <div className="metric-body">
                  <div className="v">{vals[key]?.v}</div>
                  <div className="l">{label}</div>
                  <div className="metric-foot">
                    <Delta data={vals[key]?.spark} neutral={vals[key]?.neutral ? 'static' : undefined} />
                    <Spark data={vals[key]?.spark} color={
                      key === 'pdb' ? '#ef4444' : key === 'lit' ? '#3b82f6' : undefined
                    } />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="dash-three mt-3">
            <div className="card platform-card span-2 reveal" style={{ '--rd': '0.42s' } as React.CSSProperties}>
              <div className="row" style={{ gap: 10 }}>
                <FileText size={18} style={{ color: 'var(--primary)' }} />
                <div className="section-title" style={{ fontSize: 16, margin: 0 }}>What does this platform do?</div>
              </div>
              <p className="muted mt-2" style={{ lineHeight: 1.75, fontSize: 13 }}>
                A user starts with the CDK16 gene. The platform collects information from public
                biological databases (UniProt, NCBI, Ensembl, dbSNP, RCSB PDB, AlphaFold, PubMed),
                finds reported genetic variants, and for each relevant variant asks: where is it in
                the protein? does it change it? is the change likely to affect function? — and
                generates a comprehensive, reproducible scientific report.
              </p>
              <Link className="btn btn-tint mt-2" to="/methodology" style={{ textDecoration: 'none' }}>
                Learn More <ArrowRight size={14} />
              </Link>
              <Dna className="watermark" size={120} strokeWidth={1} aria-hidden />
            </div>

            <div className="card quote-panel reveal" style={{ '--rd': '0.5s' } as React.CSSProperties}>
              <div className="quote-mark">“</div>
              <div className="quote-line">Data</div>
              <div className="quote-line">drives biological</div>
              <div className="quote-line">discovery.</div>
            </div>

            <div className="card span-2 reveal" style={{ '--rd': '0.58s' } as React.CSSProperties}>
              <div className="row-between">
                <div className="row" style={{ gap: 10 }}>
                  <Box size={18} style={{ color: 'var(--violet)' }} />
                  <div className="section-title" style={{ fontSize: 16, margin: 0 }}>Reference Protein</div>
                </div>
                <a className="btn btn-tint" style={{ fontSize: 12, padding: '6px 12px' }}
                  href={`https://www.uniprot.org/uniprotkb/${ov.protein.accession}`} target="_blank" rel="noreferrer">
                  View on UniProt <ArrowUpRight size={12} />
                </a>
              </div>
              <table className="kv mt-2">
                <tbody>
                  <tr><td>UniProt ID</td><td><a className="mono" style={{ color: 'var(--primary)', fontWeight: 600 }} href={`https://www.uniprot.org/uniprotkb/${ov.protein.accession}`} target="_blank" rel="noreferrer">{ov.protein.accession}</a> <span className="muted">({ov.protein.name})</span></td></tr>
                  <tr><td>Gene</td><td style={{ fontWeight: 600 }}>{ov.protein.gene}</td></tr>
                  <tr><td>Organism</td><td>{ov.protein.organism}</td></tr>
                  <tr><td>Length</td><td>{ov.protein.length} aa</td></tr>
                  <tr><td>Features</td><td>{ov.protein.n_features}</td></tr>
                  <tr><td>Domains</td><td>{ov.protein.family ?? 'CMGC kinase family'} <span className="muted">· {ov.protein.n_domains} annotated</span></td></tr>
                  <tr><td>Function</td><td>{ov.protein.function ?? '—'}</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="dash-bottom mt-3">
            <div className="card reveal" style={{ '--rd': '0.66s' } as React.CSSProperties}>
              <div className="panel-head">
                <div className="panel-title"><Clock size={17} style={{ color: 'var(--primary)' }} /> Recent Analyses</div>
                <Link className="viewall" to="/analysis">View All <ArrowRight size={13} /></Link>
              </div>
              {sessions.length === 0 && (
                <p className="muted mt-1" style={{ fontSize: 12.5 }}>
                  No analyses yet — <Link to="/analysis/new">start your first analysis</Link>.
                </p>
              )}
              {sessions.map(s => (
                <div className="ra-row" key={s.id}>
                  <span className="ra-ic"><FlaskConical size={15} /></span>
                  <div className="ra-main">
                    <div className="ra-name" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.name}</div>
                    <div className="ra-id">{s.id}</div>
                  </div>
                  <span className="ra-when">{timeAgo(s.created_at)}</span>
                  <span className={`badge ${s.status === 'COMPLETED' ? 'badge-emerald' : s.status === 'FAILED' ? 'badge-coral' : s.status === 'OUTDATED' ? 'badge-amber' : 'badge-cyan'}`}>{s.status}</span>
                  <Link className="viewall" to={s.has_results ? `/analysis/${s.id}/results` : `/analysis/${s.id}/run`}>
                    View <ArrowRight size={13} />
                  </Link>
                </div>
              ))}
            </div>

            <div className="card reveal" style={{ '--rd': '0.74s' } as React.CSSProperties}>
              <div className="panel-head">
                <div className="panel-title"><Wrench size={16} style={{ color: 'var(--violet)' }} /> Quick Tools</div>
              </div>
              <div className="tools-grid cols-4">
                {TOOLS.map(({ to, title, sub, tint, icon: Icon }) => (
                  <Link key={to + title} className="tool-card tall" to={to} style={{ textDecoration: 'none' }}>
                    <span className={`ti big ${tint}`}><Icon size={20} /></span>
                    <span className="tt center">{title}</span>
                    <span className="ts center">{sub}</span>
                  </Link>
                ))}
              </div>
            </div>

            <div className="card reveal" style={{ '--rd': '0.82s' } as React.CSSProperties}>
              <div className="panel-head">
                <div className="panel-title"><BookOpen size={16} style={{ color: 'var(--emerald)' }} /> Latest Literature</div>
                <Link className="viewall" to="/literature">View All <ArrowRight size={13} /></Link>
              </div>
              {lits.length === 0 && (
                <p className="muted mt-1" style={{ fontSize: 12.5 }}>No cached PubMed articles.</p>
              )}
              {lits.map(a => (
                <a className="lit-row" key={a.pmid}
                  href={`https://pubmed.ncbi.nlm.nih.gov/${a.pmid}/`} target="_blank" rel="noreferrer">
                  <span className="lit-ic"><BookOpen size={13} /></span>
                  <span className="lit-main">
                    <span className="lit-title">{a.title}</span>
                    <span className="lit-src">{a.journal} · {a.pubdate}</span>
                  </span>
                  <ArrowRight size={13} className="lit-go" />
                </a>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
