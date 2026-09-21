import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Sun, Moon, Database, Info, Sparkles } from 'lucide-react'
import { useTheme } from '../theme'
import { api } from '../api/client'
import type { Overview } from '../api/client'

export default function Settings() {
  const { theme, toggleTheme, motion, toggleMotion } = useTheme()
  const [ov, setOv] = useState<Overview | null>(null)

  useEffect(() => {
    api.get<Overview>('/overview').then(setOv).catch(() => {})
  }, [])

  return (
    <div>
      <h1 className="section-title">Settings</h1>
      <p className="section-sub">Workbench preferences and session information.</p>

      <div className="grid-2" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
        <div className="card">
          <div className="row" style={{ gap: 10 }}>
            {theme === 'dark' ? <Moon size={17} style={{ color: 'var(--violet)' }} /> : <Sun size={17} style={{ color: 'var(--amber)' }} />}
            <div className="section-title" style={{ fontSize: 15, margin: 0 }}>Appearance</div>
          </div>
          <p className="muted mt-2">
            Light/Dark mode affects the whole workbench — tables, charts, the report viewer and the
            3D viewer. Your choice is remembered per browser.
          </p>
          <button className="btn mt-2" onClick={toggleTheme}>
            Switch to {theme === 'dark' ? 'light' : 'dark'} mode
          </button>
        </div>

        <div className="card">
          <div className="row" style={{ gap: 10 }}>
            <Sparkles size={17} style={{ color: 'var(--violet)' }} />
            <div className="section-title" style={{ fontSize: 15, margin: 0 }}>Animations</div>
          </div>
          <p className="muted mt-2">
            Card entrance, floating labels and the rotating hero molecule. Animations are on by
            default; turn them off for a fully static interface.
          </p>
          <button className="btn mt-2" onClick={toggleMotion}>
            {motion === 'on' ? 'Turn animations off' : 'Turn animations on'}
          </button>
        </div>

        <div className="card">
          <div className="row" style={{ gap: 10 }}>
            <Database size={17} style={{ color: 'var(--primary)' }} />
            <div className="section-title" style={{ fontSize: 15, margin: 0 }}>Data</div>
          </div>
          {ov ? (
            <table className="kv mt-2">
              <tbody>
                <tr><td className="muted">Dataset version</td><td className="mono">{ov.dataset_version}</td></tr>
                <tr><td className="muted">Pipeline</td><td className="mono">{ov.pipeline_version}</td></tr>
                <tr><td className="muted">UniProt entry</td><td className="mono">Q00536 v{ov.protein.uniprot_version ?? '—'}</td></tr>
                <tr><td className="muted">Variants</td><td>{ov.variants.total.toLocaleString()} ({ov.variants.missense} missense)</td></tr>
              </tbody>
            </table>
          ) : <p className="muted mt-2">Backend unavailable.</p>}
        </div>

        <div className="card">
          <div className="row" style={{ gap: 10 }}>
            <Info size={17} style={{ color: 'var(--emerald)' }} />
            <div className="section-title" style={{ fontSize: 15, margin: 0 }}>About</div>
          </div>
          <p className="muted mt-2" style={{ lineHeight: 1.7 }}>
            CDK16 Analysis Workbench — integrative structural &amp; functional bioinformatics.
            Research and educational use only; computational evidence does not establish clinical
            pathogenicity. See <Link to="/methodology">Methodology</Link> for the full pipeline.
          </p>
        </div>
      </div>
    </div>
  )
}
