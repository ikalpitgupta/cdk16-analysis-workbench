import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { api, type AnalysisSession } from '../api/client'
import {
  LayoutDashboard, FlaskConical, Dna, Boxes, Box, BarChart3, BookOpen,
  FileText, Lightbulb, Settings, Moon, Sun, Menu, Search, Bell, Dna as DnaMark,
  ChevronDown, Database, PanelLeftClose, PanelLeftOpen,
} from 'lucide-react'
import { useTheme } from '../theme'

const NAV: Array<{ to: string; label: string; icon: any; end?: boolean; section?: string }> = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/analysis', label: 'Analysis', icon: FlaskConical, section: 'Research' },
  { to: '/variants', label: 'Variants', icon: Dna },
  { to: '/protein', label: 'Protein', icon: Boxes },
  { to: '/structure', label: '3D Structure', icon: Box },
  { to: '/analysis-charts', label: 'Analysis Charts', icon: BarChart3 },
  { to: '/reports', label: 'Reports', icon: FileText, section: 'Resources' },
  { to: '/literature', label: 'Literature', icon: BookOpen },
  { to: '/methodology', label: 'Methodology', icon: Lightbulb },
]

export default function Layout() {
  const { theme, toggleTheme, motion, toggleMotion } = useTheme()
  const [open, setOpen] = useState(false)
  /* Desktop: collapsible icon-rail sidebar, persisted across sessions. */
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('cdk16-sidebar') === 'collapsed')
  useEffect(() => { localStorage.setItem('cdk16-sidebar', collapsed ? 'collapsed' : 'open') }, [collapsed])
  const [q, setQ] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  /* Notifications: real activity feed (recent analyses + latest report versions). */
  const [notifOpen, setNotifOpen] = useState(false)
  const [notifItems, setNotifItems] = useState<Array<{ kind: string; label: string; when: string; to: string }>>([])
  const notifRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    let alive = true
    api.get<AnalysisSession[]>('/analyses').then(ss => {
      if (!alive) return
      const items: Array<{ kind: string; label: string; when: string; to: string }> = []
      for (const s of ss.slice(0, 5)) {
        const lastRun = s.runs?.length ? s.runs[s.runs.length - 1] : null
        items.push({
          kind: lastRun?.status === 'COMPLETED' ? 'completed' : lastRun?.status === 'FAILED' ? 'failed' : 'running',
          label: lastRun?.status === 'COMPLETED'
            ? `Analysis "${s.name}" completed`
            : lastRun?.status === 'FAILED'
              ? `Analysis "${s.name}" failed`
              : `Analysis "${s.name}" ${lastRun ? (lastRun.stage || lastRun.status) : 'created'}`,
          when: new Date(s.updated_at).toLocaleString(),
          to: `/analysis/${s.id}/results`,
        })
        for (const r of (s.reports || []).slice(0, 2)) {
          items.push({ kind: 'report', label: `${r.section} report v${r.version} generated`, when: new Date(r.created_at).toLocaleString(), to: `/reports/${r.id}` })
        }
      }
      setNotifItems(items.slice(0, 8))
    }).catch(() => { if (alive) setNotifItems([]) })
    return () => { alive = false }
  }, [])
  useEffect(() => {
    if (!notifOpen) return
    const h = (e: MouseEvent) => { if (!notifRef.current?.contains(e.target as Node)) setNotifOpen(false) }
    window.addEventListener('mousedown', h)
    return () => window.removeEventListener('mousedown', h)
  }, [notifOpen])
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const location = useLocation()

  // Ctrl+K focuses the global search
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setSearchOpen(true)
        inputRef.current?.focus()
      }
      if (e.key === 'Escape') setSearchOpen(false)
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])

  const submitSearch = (e?: React.FormEvent) => {
    e?.preventDefault()
    const s = q.trim()
    if (!s) return
    // route the query like the reference app: variants by default
    navigate(`/variants?q=${encodeURIComponent(s)}`)
    setSearchOpen(false)
    setQ('')
  }

  let lastSection = ''
  return (
    <div className="shell">
      <aside className={`sidebar ${open ? 'open' : ''} ${collapsed ? 'collapsed' : ''}`}>
        <div className="brand">
          <div className="logo"><DnaMark size={20} strokeWidth={2.2} /></div>
          <div className="brand-txt">
            <div className="brand-name">CDK16 <span className="brand-sub">WORKBENCH</span></div>
            <div className="brand-tag">Genomics · Structure · Impact</div>
          </div>
          <button className="sb-collapse inside" onClick={() => setCollapsed(c => !c)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!collapsed} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            <PanelLeftClose size={15} />
          </button>
        </div>

        {NAV.map(({ to, label, icon: Icon, end, section }) => {
          const sectionEl = section && section !== lastSection
            ? <div className="nav-section" key={section}>{(lastSection = section, section)}</div>
            : null
          return (
            <div key={to} style={{ display: 'contents' }}>
              {sectionEl}
              <NavLink to={to} end={end}
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                onClick={() => setOpen(false)}
                title={collapsed ? label : undefined}>
                <Icon size={16} strokeWidth={2.1} /> <span className="nl-label">{label}</span>
              </NavLink>
            </div>
          )
        })}

        <NavLink to="/settings" className={({ isActive }) => `nav-link settings-link ${isActive ? 'active' : ''}`} onClick={() => setOpen(false)}
          title={collapsed ? 'Settings' : undefined}>
          <Settings size={16} /> <span className="nl-label">Settings</span>
        </NavLink>

        <div className="promo-card">
          <div className="promo-title">Small variants.<br />Big insights.</div>
          <div className="promo-sub">Advancing understanding of CDK16 for a healthier tomorrow.</div>
          <NavLink to="/methodology" className="promo-btn" aria-label="Learn more">
            →
          </NavLink>
        </div>

        <div className="theme-row">
          <div className={`motion-toggle ${motion === 'off' ? 'off' : ''}`} onClick={toggleMotion} role="button" tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && toggleMotion()}
            aria-label={motion === 'on' ? 'Disable animations' : 'Enable animations'}
            title="Card entrance & float animations">
            <span className="knob" />
            <Database size={12} className="mt-ic" />
          </div>
          <span className="nl-label" style={{ fontSize: 12, fontWeight: 600 }}>Animations {motion === 'on' ? 'on' : 'off'}</span>
        </div>
      </aside>

      {open && (
        <button aria-label="Close menu" onClick={() => setOpen(false)}
          style={{ position: 'fixed', inset: 0, zIndex: 30, background: 'rgba(0,0,0,.4)', border: 'none' }} />
      )}

      <div className="main">
        <div className="topbar">
          <button className="btn mobile-menu" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu size={16} />
          </button>
          {/* Expand control when the sidebar is collapsed (icon rail) */}
          <button className="btn sb-collapse topbar-only" onClick={() => setCollapsed(false)}
            aria-label="Expand sidebar" title="Expand sidebar" style={{ display: collapsed ? undefined : 'none' }}>
            <PanelLeftOpen size={16} />
          </button>
          <form className={`topsearch ${searchOpen ? 'focus' : ''}`} onSubmit={submitSearch} role="search">
            <Search size={15} className="ts-ic" />
            <input ref={inputRef} value={q} onChange={e => setQ(e.target.value)}
              placeholder="Search variants, proteins, literature, or keywords..."
              aria-label="Global search" />
            <kbd className="ts-kbd">Ctrl + K</kbd>
          </form>
          <div className="topbar-right">
            {/* reference-style segmented light/dark pill */}
            <div className="seg-theme" role="group" aria-label="Color theme">
              <button className={`seg-opt ${theme === 'light' ? 'on' : ''}`} onClick={() => theme !== 'light' && toggleTheme()}
                aria-pressed={theme === 'light'} aria-label="Light mode"><Sun size={13} /></button>
              <button className={`seg-opt ${theme === 'dark' ? 'on' : ''}`} onClick={() => theme !== 'dark' && toggleTheme()}
                aria-pressed={theme === 'dark'} aria-label="Dark mode"><Moon size={13} /></button>
            </div>
            <div style={{ position: 'relative' }} ref={notifRef}>
              <button className="icon-btn" aria-label="Notifications" aria-expanded={notifOpen}
                title="Recent analysis & report activity" onClick={() => setNotifOpen(o => !o)}>
                <Bell size={17} />
                {notifItems.length > 0 && <span className="bell-dot" />}
              </button>
              {notifOpen && (
                <div className="notif-panel" role="dialog" aria-label="Notifications">
                  <div className="notif-head">Activity</div>
                  {notifItems.length === 0
                    ? <div className="notif-empty">No recent analysis or report activity.</div>
                    : notifItems.map((n, i) => (
                      <button key={i} className={`notif-item kind-${n.kind}`}
                        onClick={() => { setNotifOpen(false); navigate(n.to) }}>
                        <span className="notif-dot" aria-hidden />
                        <span className="notif-body">
                          <span className="notif-label">{n.label}</span>
                          <span className="notif-when">{n.when}</span>
                        </span>
                      </button>
                    ))}
                </div>
              )}
            </div>
            <div className="user-chip" title="Local analysis session">
              <div className="avatar"><Dna size={15} /></div>
              <div className="uc-meta">
                <div className="uc-role-top">Researcher</div>
                <div className="uc-name">Kalpit Gupta &amp; Drashi Manoria</div>
              </div>
              <ChevronDown size={14} className="uc-chev" />
            </div>
          </div>
        </div>
        {/* Keyed on the history entry so every navigation (incl. back/forward
            and new searches) restarts the page-in animation. The animation
            itself is gated by [data-motion] — see index.css. */}
        <div className="page-anim" key={location.key}>
          <Outlet />
        </div>
      </div>
    </div>
  )
}
