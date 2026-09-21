import { useEffect, useRef, useState } from 'react'
import { Box } from 'lucide-react'
import { api } from '../api/client'
import { useTheme } from '../theme'

declare global {
  interface Window { $3Dmol?: any; __molLibPromise?: Promise<void> }
}

/* Shared lazy loader for the 3Dmol library (single injection, promise-cached). */
function loadMolLib(): Promise<void> {
  if (window.$3Dmol) return Promise.resolve()
  if (!window.__molLibPromise) {
    window.__molLibPromise = new Promise((resolve, reject) => {
      const s = document.createElement('script')
      s.src = 'https://3Dmol.org/build/3Dmol-min.js'
      s.onload = () => resolve()
      s.onerror = () => reject(new Error('3Dmol library failed to load'))
      document.head.appendChild(s)
    })
  }
  return window.__molLibPromise
}

interface StructMeta {
  experimental: { pdb_id: string; method: string; resolution_A: number | null; title: string; chains: string[] }[]
  predicted: { alphafold_id: string; file: string; version: string }
}

interface VariantLite {
  variant_uid: string
  aa_change?: string | null
  protein_position?: number | null
  am_pathogenicity_score?: number | null
}

const CARTOON = '#14b8a6'

/* AlphaMissense score tiers — shared by marker styling and the legend.
   Tiers are a visualization grouping of the continuous AM score, not a clinical call. */
const AM_TIERS = [
  { id: 'high', label: 'High AM (≥ 0.9)', color: '#f87171', min: 0.9, max: 1.01 },
  { id: 'mid', label: 'Moderate (0.5–0.9)', color: '#fbbf24', min: 0.5, max: 0.9 },
  { id: 'low', label: 'Low (< 0.5)', color: '#34d399', min: 0, max: 0.5 },
  { id: 'none', label: 'No AM score', color: '#94a3b8', min: -1, max: 0 },
] as const

type TierId = (typeof AM_TIERS)[number]['id']

function amTier(v: VariantLite): TierId {
  const s = v.am_pathogenicity_score
  if (s === null || s === undefined) return 'none'
  if (s >= 0.9) return 'high'
  if (s >= 0.5) return 'mid'
  return 'low'
}

function tierColor(v: VariantLite): string {
  return AM_TIERS.find(t => t.id === amTier(v))!.color
}

export default function Structure() {
  const { theme } = useTheme()
  const [meta, setMeta] = useState<StructMeta | null>(null)
  const [sel, setSel] = useState('AF-Q00536-F1')
  const [highlight, setHighlight] = useState('286')
  const [showSurface, setShowSurface] = useState(false)
  const [showMarkers, setShowMarkers] = useState(true)
  const [tierFilter, setTierFilter] = useState<Set<TierId>>(new Set(AM_TIERS.map(t => t.id)))
  const [topVariants, setTopVariants] = useState<VariantLite[]>([])
  const [molReady, setMolReady] = useState(Boolean(window.$3Dmol))
  const [molError, setMolError] = useState('')
  const [modelLoaded, setModelLoaded] = useState(false)
  const viewer = useRef<any>(null)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.get<StructMeta>('/structures').then(setMeta).catch(e => setMolError(String(e)))
    api.get<{ variants: VariantLite[] }>('/variants?page=1&page_size=15&sort_by=priority_score&sort_desc=true')
      .then(r => setTopVariants(r.variants.filter(v => v.protein_position)))
      .catch(() => {})
    loadMolLib().then(() => setMolReady(true)).catch(e => setMolError(String(e.message || e)))
  }, [])

  /* Load (or reload) the selected model whenever the library, selection or theme changes. */
  useEffect(() => {
    if (!molReady || !box.current) return
    const cfg: Record<string, string> = {
      'AF-Q00536-F1': '/api/structures/file/AF-Q00536-F1.cif',
      ...(meta?.experimental ?? []).reduce((acc, s) => ({ ...acc, [s.pdb_id]: `/api/structures/file/${s.pdb_id}.cif` }), {}),
    }
    const url = cfg[sel]
    if (!url) return
    const bg = theme === 'light' ? '#f2f5fa' : '#07111f'
    let cancelled = false
    setModelLoaded(false)
    fetch(url)
      .then(r => { if (!r.ok) throw new Error(`structure file unavailable (${r.status})`); return r.text() })
      .then(txt => {
        if (cancelled || !window.$3Dmol || !box.current) return
        viewer.current?.clear?.()
        viewer.current = window.$3Dmol.createViewer(box.current, { backgroundColor: bg })
        const v = viewer.current
        v.addModel(txt, 'cif')
        v.setStyle({}, { cartoon: { color: CARTOON, opacity: 0.95 } })
        const pos = parseInt(highlight, 10)
        if (!Number.isNaN(pos) && pos > 0) {
          v.setStyle({ resi: pos }, { cartoon: { color: '#f87171' }, stick: { colorscheme: 'redCarbon', radius: 0.3 } })
          v.addStyle({ resi: pos }, { sphere: { radius: 1.4, color: '#f87171' } })
        }
        drawVariantMarkers(v)
        v.zoomTo()
        v.render()
        if (showSurface) v.addSurface({}, { opacity: 0.75 })
        setModelLoaded(true)
      })
      .catch(e => { if (!cancelled) setMolError(`Structure load failed: ${e}`) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [molReady, sel, meta, theme])

  /* Live re-style on highlight/surface/marker changes (no model reload). */
  useEffect(() => {
    const v = viewer.current
    if (!v || !modelLoaded) return
    v.removeAllSurfaces()
    v.setStyle({}, { cartoon: { color: CARTOON, opacity: 0.95 } })
    const pos = parseInt(highlight, 10)
    if (!Number.isNaN(pos) && pos > 0) {
      v.setStyle({ resi: pos }, { cartoon: { color: '#f87171' }, stick: { colorscheme: 'redCarbon', radius: 0.3 } })
      v.addStyle({ resi: pos }, { sphere: { radius: 1.4, color: '#f87171' } })
    }
    drawVariantMarkers(v)
    if (showSurface) v.addSurface({}, { opacity: 0.75 })
    v.render()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlight, showSurface, showMarkers, tierFilter, topVariants, modelLoaded])

  /* Variant residue markers: spheres on prioritized variants, colored by AM tier,
     respecting the tier-filter chips and the show/hide markers toggle.
     No explicit removal needed: the setStyle({}, ...) call above resets all atom styles. */
  function drawVariantMarkers(v: any) {
    if (!showMarkers) return
    for (const vt of topVariants) {
      const pos = vt.protein_position
      if (!pos) continue
      if (!tierFilter.has(amTier(vt))) continue
      const col = tierColor(vt)
      v.addStyle({ resi: pos }, { sphere: { radius: 1.1, color: col, opacity: 0.9 } })
    }
  }

  const focusVariant = (v: VariantLite) => {
    if (v.protein_position) setHighlight(String(v.protein_position))
  }

  return (
    <div>
      <div className="page-head">
        <div className="ph-ic tint-violet"><Box size={22} /></div>
        <div>
          <h1 className="section-title">3D Structure Explorer</h1>
          <p className="section-sub">
            AlphaFold predicted model and experimental PDB entries mapped to UniProt Q00536.
            Highlight any residue; quick-select prioritized variants.
          </p>
        </div>
      </div>

      {molError && <div className="notice notice-coral mb-2">{molError}</div>}
      {!molReady && !molError && (
        <div className="notice notice-info mb-2">
          <span className="row" style={{ gap: 8 }}><span className="spinner" style={{ width: 16, height: 16, margin: 0 }} />
          Loading 3D molecular viewer library…</span>
        </div>
      )}

      <div className="structure-grid">
        <div className="card table-card" style={{ padding: 14 }}>
          <div className="viewer-shell">
            <div ref={box} className="viewer-box" aria-label="3D molecular viewer" />
            {!modelLoaded && !molError && molReady && (
              <div className="viewer-overlay"><span className="spinner" /> Rendering structure…</div>
            )}
          </div>
          <div className="row mt-2" style={{ flexWrap: 'wrap', gap: 10 }}>
            <select className="select" style={{ maxWidth: 300 }} value={sel} onChange={e => setSel(e.target.value)}
              aria-label="Structure selection">
              <option value="AF-Q00536-F1">AlphaFold AF-Q00536-F1 (predicted)</option>
              {meta?.experimental.map(s => (
                <option key={s.pdb_id} value={s.pdb_id}>
                  {s.pdb_id} · {s.method}{s.resolution_A ? ` ${s.resolution_A}Å` : ''} (experimental)
                </option>
              ))}
            </select>
            <input className="input" style={{ maxWidth: 170 }} placeholder="Residue # e.g. 286"
              aria-label="Residue to highlight"
              value={highlight} onChange={e => setHighlight(e.target.value)} />
            <button className="btn" onClick={() => setShowSurface(s => !s)}>
              {showSurface ? 'Hide surface' : 'Show surface'}
            </button>
            <button className="btn" onClick={() => setShowMarkers(s => !s)}
              aria-pressed={showMarkers}>
              {showMarkers ? 'Hide variant markers' : 'Show variant markers'}
            </button>
          </div>

          <div className="mol-legend" role="group" aria-label="Variant marker legend">
            <span className="legend-title">Variant markers ·</span>
            {AM_TIERS.map(t => {
              const active = tierFilter.has(t.id)
              const count = topVariants.filter(v => amTier(v) === t.id).length
              return (
                <button key={t.id} className={`legend-chip ${active ? '' : 'off'}`}
                  onClick={() => setTierFilter(prev => {
                    const next = new Set(prev)
                    if (next.has(t.id)) next.delete(t.id)
                    else next.add(t.id)
                    return next
                  })}
                  aria-pressed={active}
                  title={`Show/hide ${t.label.toLowerCase()} markers`}>
                  <span className="legend-dot" style={{ background: t.color, opacity: active ? 1 : 0.3 }} />
                  {t.label}
                  <span className="legend-count">{count}</span>
                </button>
              )
            })}
          </div>
          <p className="muted mt-1">
            Rotate: drag · Zoom: scroll · The predicted model is clearly labelled; experimental
            structures are X-ray/cryo-EM observations deposited in RCSB PDB.
          </p>
        </div>

        <div className="card side-panel">
          <div className="section-title" style={{ fontSize: 14 }}>Prioritized variants</div>
          <p className="muted" style={{ marginBottom: 10 }}>Click to highlight the residue in the structure.</p>
          {topVariants.map(v => (
            <div key={v.variant_uid} onClick={() => focusVariant(v)}
              className={`side-item ${highlight === String(v.protein_position) ? 'selected' : ''}`}
              role="button" tabIndex={0}
              onKeyDown={e => e.key === 'Enter' && focusVariant(v)}>
              <div className="row-between">
                <span className="mono" style={{ fontWeight: 600 }}>{v.aa_change || v.variant_uid}</span>
                <span className="badge badge-gray">pos {v.protein_position}</span>
              </div>
              {v.am_pathogenicity_score !== null && v.am_pathogenicity_score !== undefined && (
                <div className="muted" style={{ fontSize: 11 }}>AM {v.am_pathogenicity_score.toFixed(2)}</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {meta && (
        <div className="card table-card mt-3">
          <table className="tbl">
            <thead><tr><th>Structure</th><th>Method</th><th>Resolution (Å)</th><th>Chains</th><th>Title</th></tr></thead>
            <tbody>
              <tr>
                <td className="mono">AF-Q00536-F1</td><td>Predicted (AlphaFold)</td><td>—</td><td>A</td>
                <td className="muted">AlphaFold DB monomer model for Q00536 (pLDDT per residue)</td>
              </tr>
              {meta.experimental.map(s => (
                <tr key={s.pdb_id}>
                  <td className="mono">{s.pdb_id}</td><td>{s.method}</td>
                  <td>{s.resolution_A ?? '—'}</td><td>{s.chains?.join(', ') || '—'}</td>
                  <td className="muted">{s.title}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
